import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8787
    db_host: str = "127.0.0.1"
    db_port: int = 3307
    db_user: str = "root"
    db_pass: str = ""
    db_name: str = "export_data"
    table_prefix: str = ""
    downloads_root: str = "downloads"
    tasks_file: str = "tasks.json"


settings = Settings()


def resolve_output_dir(output_dir: str, name: str, root: str = "downloads") -> str:
    if output_dir:
        return output_dir
    return os.path.join(root, name)
