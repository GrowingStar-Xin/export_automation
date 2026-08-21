from fastapi.testclient import TestClient
from app.main import create_app
from app.tasks import TaskStore


def make_client(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    return TestClient(create_app(store=store))


def test_task_crud(tmp_path):
    c = make_client(tmp_path)
    r = c.post("/api/tasks", json={"name": "客户A", "url": "https://x.com", "button_text": "导出"})
    assert r.status_code == 200
    task = r.json()["task"]
    assert task["id"].startswith("t_")

    r = c.get("/api/tasks")
    assert len(r.json()["tasks"]) == 1

    r = c.put(f"/api/tasks/{task['id']}", json={"import_after": True})
    assert r.json()["task"]["import_after"] is True

    r = c.delete(f"/api/tasks/{task['id']}")
    assert r.json()["ok"] is True
    assert c.get("/api/tasks").json()["tasks"] == []


def test_create_rejects_bad_task(tmp_path):
    c = make_client(tmp_path)
    r = c.post("/api/tasks", json={"name": "x", "url": "not-a-url", "button_text": "导出"})
    assert r.status_code == 422


def test_update_missing_task_404(tmp_path):
    c = make_client(tmp_path)
    r = c.put("/api/tasks/nonexistent", json={"enabled": False})
    assert r.status_code == 404
