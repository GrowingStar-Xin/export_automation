from app.config import Settings, resolve_output_dir


def test_settings_defaults():
    s = Settings(_env_file=None)  # 不读 .env，纯默认值
    assert s.host == "127.0.0.1"
    assert s.port == 8788
    assert s.db_name == "export_data"
    assert s.db_pass == ""
    assert s.tasks_file == "tasks.json"
    assert s.downloads_root == "downloads"


def test_resolve_output_dir_uses_explicit():
    assert resolve_output_dir("/tmp/out", "x") == "/tmp/out"


def test_resolve_output_dir_falls_back_to_name():
    import os
    assert resolve_output_dir("", "客户A", root="downloads") == os.path.join("downloads", "客户A")
