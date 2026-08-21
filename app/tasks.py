import json
import os
import secrets
import time
from typing import Literal

from pydantic import BaseModel, model_validator


class Task(BaseModel):
    id: str = ""
    name: str
    url: str
    button_text: str = ""
    button_selector: str = ""
    username: str = ""
    password: str = ""
    login_url: str = ""
    captcha_mode: Literal["auto", "none", "manual"] = "auto"
    output_dir: str = ""
    import_after: bool = False
    enabled: bool = True
    headless: bool = False

    @model_validator(mode="after")
    def _validate(self):
        if not self.name.strip():
            raise ValueError("name 不能为空")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("url 必须是 http/https")
        if not self.button_text.strip() and not self.button_selector.strip():
            raise ValueError("button_text 与 button_selector 至少填一个")
        return self


def new_task_id() -> str:
    return f"t_{int(time.time() * 1000)}_{secrets.token_hex(3)}"


class TaskStore:
    def __init__(self, path: str):
        self.path = path

    def _load(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []

    def _save(self, tasks: list[dict]) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def list(self) -> list[Task]:
        return [Task(**d) for d in self._load()]

    def get(self, task_id: str) -> Task | None:
        for t in self.list():
            if t.id == task_id:
                return t
        return None

    def create(self, data: dict) -> Task:
        t = Task(**data)
        t.id = new_task_id()
        tasks = self._load()
        tasks.append(t.model_dump())
        self._save(tasks)
        return t

    def update(self, task_id: str, data: dict) -> Task | None:
        tasks = self._load()
        for i, d in enumerate(tasks):
            if d.get("id") == task_id:
                merged = {**d, **data, "id": task_id}
                t = Task(**merged)
                tasks[i] = t.model_dump()
                self._save(tasks)
                return t
        return None

    def delete(self, task_id: str) -> bool:
        tasks = self._load()
        new = [d for d in tasks if d.get("id") != task_id]
        if len(new) == len(tasks):
            return False
        self._save(new)
        return True
