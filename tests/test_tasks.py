import pytest
from pydantic import ValidationError
from app.tasks import Task, TaskStore


def test_valid_task():
    t = Task(name="a", url="https://x.com/report", button_text="导出")
    assert t.captcha_mode == "auto"
    assert t.system == ""


def test_url_must_be_http():
    with pytest.raises(ValidationError):
        Task(name="a", url="ftp://x.com", button_text="导出")


def test_requires_button():
    with pytest.raises(ValidationError):
        Task(name="a", url="https://x.com")


def test_store_roundtrip(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    t = store.create({"name": "客户A", "url": "https://x.com", "button_text": "导出"})
    assert t.id.startswith("t_")
    # 读回
    loaded = TaskStore(str(tmp_path / "tasks.json")).list()
    assert len(loaded) == 1
    assert loaded[0].name == "客户A"
    # 更新（id 不可改）
    store.update(t.id, {"system": "customer_a"})
    assert store.get(t.id).system == "customer_a"
    # 删除
    assert store.delete(t.id) is True
    assert store.delete(t.id) is False


def test_create_ignores_client_id(tmp_path):
    store = TaskStore(str(tmp_path / "t.json"))
    t = store.create({"id": "should_be_overridden", "name": "a", "url": "https://x.com", "button_text": "导出"})
    assert t.id != "should_be_overridden"


def test_trims_whitespace():
    t = Task(name="  客户A  ", url="  https://x.com  ", button_text=" 导出 ",
             output_dir=" /tmp/out ", system=" customer_a ")
    assert t.name == "客户A"
    assert t.url == "https://x.com"
    assert t.button_text == "导出"
    assert t.output_dir == "/tmp/out"
    assert t.system == "customer_a"
