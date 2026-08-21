import asyncio
import json
import os
import socket
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import import_data
from .browser import classify, run_task
from .config import settings
from .tasks import Task, TaskStore

running = False  # 运行互斥标志（避免并发拉起多个浏览器）


def _port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_site(url: str, timeout: float = 2.0) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        req = Request(f"{p.scheme}://{p.netloc}/", headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=timeout) as r:
            r.read(1024)
        return True
    except Exception:
        return False


def _ndjson(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


def create_app(store: TaskStore | None = None) -> FastAPI:
    app = FastAPI(title="通用导出自动化")
    ts = store or TaskStore(settings.tasks_file)

    @app.get("/api/status")
    async def status(url: str = ""):
        db = await asyncio.to_thread(_port_open, settings.db_host, settings.db_port)
        site = await asyncio.to_thread(_check_site, url)
        return {"db": db, "site": site}

    @app.get("/api/tasks")
    async def list_tasks():
        return {"tasks": [t.model_dump() for t in ts.list()]}

    @app.post("/api/tasks")
    async def create_task(task: Task):
        return {"task": ts.create(task.model_dump()).model_dump()}

    @app.put("/api/tasks/{task_id}")
    async def update_task(task_id: str, data: dict):
        t = ts.update(task_id, data)
        if t is None:
            raise HTTPException(404, "任务不存在")
        return {"task": t.model_dump()}

    @app.delete("/api/tasks/{task_id}")
    async def delete_task(task_id: str):
        if not ts.delete(task_id):
            raise HTTPException(404, "任务不存在")
        return {"ok": True}

    @app.post("/api/run")
    async def run(body: dict):
        global running
        if running:
            raise HTTPException(409, "已有运行进行中")
        running = True
        ids = (body or {}).get("ids") or []
        tasks = ts.list()
        selected = [t for t in tasks if t.id in ids] if ids else [t for t in tasks if t.enabled]

        async def gen():
            global running
            try:
                summary = {"total": len(selected), "ok": 0, "failed": 0}
                for idx, t in enumerate(selected, 1):
                    yield _ndjson({"type": "task_start", "task_id": t.id, "name": t.name, "index": idx, "total": len(selected)})
                    q: asyncio.Queue = asyncio.Queue()

                    def emit(line: str) -> None:
                        q.put_nowait(line)

                    fut = asyncio.create_task(run_task(t, emit))
                    while not fut.done():
                        while not q.empty():
                            line = q.get_nowait()
                            yield _ndjson({"type": "log", "task_id": t.id, "line": line, "level": classify(line)})
                        await asyncio.sleep(0.05)
                    while not q.empty():
                        line = q.get_nowait()
                        yield _ndjson({"type": "log", "task_id": t.id, "line": line, "level": classify(line)})
                    result = fut.result()
                    imported = None
                    if result.ok and t.import_after and result.files:
                        imported = import_data.import_files(result.files)
                    if result.ok:
                        summary["ok"] += 1
                    else:
                        summary["failed"] += 1
                    yield _ndjson({"type": "task_end", "task_id": t.id, "ok": result.ok,
                                   "files": result.files, "imported": imported, "error": result.error})
                yield _ndjson({"type": "done", "summary": summary})
            finally:
                running = False

        return StreamingResponse(gen(), media_type="application/x-ndjson")

    # 静态托管（生产构建后）
    dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
    if os.path.isdir(dist):
        app.mount("/", StaticFiles(directory=dist, html=True), name="static")

    return app


app = create_app()
