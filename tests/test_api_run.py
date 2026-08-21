import json

from fastapi.testclient import TestClient
from app.main import create_app
from app.tasks import TaskStore
from app.browser import RunResult


def make_client(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    store.create({"name": "客户A", "url": "https://x.com", "button_text": "导出", "import_after": True})
    return TestClient(create_app(store=store))


def test_run_streams_events(tmp_path, monkeypatch):
    async def fake_run(task, on_log):
        on_log("[i] 已找到导出按钮")
        on_log("[✓] 下载完成: /tmp/a.zip")
        return RunResult(ok=True, files=["/tmp/a.zip"])

    monkeypatch.setattr("app.main.run_task", fake_run)
    monkeypatch.setattr("app.main.import_data.import_files", lambda files: {"tables": [], "total_rows": 0})

    c = make_client(tmp_path)
    with c.stream("POST", "/api/run", json={"ids": []}) as resp:
        lines = [ln for ln in resp.iter_lines() if ln.strip()]

    types = [json.loads(ln)["type"] for ln in lines]
    assert types == ["task_start", "log", "log", "task_end", "done"]
    end = json.loads(lines[3])
    assert end["ok"] is True
    assert end["files"] == ["/tmp/a.zip"]
    assert end["imported"] == {"tables": [], "total_rows": 0}


def test_run_409_when_running(tmp_path):
    from app import main as main_mod
    main_mod.running = True
    try:
        c = make_client(tmp_path)
        r = c.post("/api/run", json={})
        assert r.status_code == 409
    finally:
        main_mod.running = False
