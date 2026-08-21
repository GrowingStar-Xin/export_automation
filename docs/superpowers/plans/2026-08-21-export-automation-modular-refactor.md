# 通用导出自动化 · 模块化重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「通用导出自动化操作台」重构为 Python/FastAPI 后端 + React/Vite/TS 前端，支持多 URL 任务列表批量点击导出、按任务落盘、可选 MySQL 入库，并彻底清理遗留代码与硬编码凭据。

**Architecture:** 单进程 Python 后端（FastAPI + Playwright async API + mysql.connector），浏览器引擎与入库均为同进程模块调用；任务持久化到 `tasks.json`；`/api/run` 用 NDJSON 流式返回逐任务日志。前端 React + Vite + TS 在开发期独立运行、构建后由 FastAPI 托管静态产物。

**Tech Stack:** Python 3.11+ / FastAPI / pydantic v2 + pydantic-settings / Playwright(Python, `channel="chrome"`) / mysql-connector-python；React 18 + Vite + TypeScript；pytest。

**Spec:** [docs/superpowers/specs/2026-08-21-export-automation-modular-refactor-design.md](../specs/2026-08-21-export-automation-modular-refactor-design.md)

## Global Constraints

- Python ≥ 3.11；pydantic v2；`from __future__ import annotations` 可选。
- JSON 字段名统一 **snake_case**（`button_text`、`import_after`…），前端 TS 类型直接用同名 snake_case 字段，不做 camelCase 转换。
- 浏览器启动固定 `channel="chrome"`（复用本机 Chrome，不下载 chromium）。
- `DB_NAME` 默认 `export_data`；任何地方不得出现 `peptide` / `peptide_orders` 字样（除 spec 引用外）。
- 不得提交任何真实凭据或数据：`.env`、`tasks.json`、`downloads/` 均在 `.gitignore`。
- 每个任务结束都 commit；commit message 结尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`。
- 后端代码在 `app/` 包内，测试在 `tests/`，前端在 `frontend/`。

---

### Task 1: 仓库初始化 + 清理遗留 + 基础配置

**Files:**
- Create: `.gitignore`、`.env.example`、`tasks.example.json`、`requirements.txt`、`requirements-dev.txt`
- Delete: `browser_click_generate.mjs`、`click_export.mjs`、`generate_order.mjs`、`import_orders.py`、`方案.html`、`订单自动化逆向结果.html`、`server.mjs`、`web/`、`package.json`、`package-lock.json`、`node_modules/`、`downloads/`、`orders_extracted/`、`__pycache__/`、`.DS_Store`、`server.log`
- Keep（暂留作移植源，后续任务再删）: `auto_export.mjs`、`import_generic.py`

**Interfaces:**
- Produces: 一个干净的 git 仓库骨架，供后续所有任务使用。

- [ ] **Step 1: 初始化 git 仓库**

```bash
cd /Users/wulinxin/Desktop/export-automation
git init
# 确认身份已配置（若为空，先 git config user.name/email 或询问用户）
git config user.name || echo "NEED_IDENTITY"
git config user.email || echo "NEED_IDENTITY"
```
Expected: `git init` 成功；若输出 `NEED_IDENTITY` 则暂停并向用户确认要用的身份，再继续。

- [ ] **Step 2: 写 .gitignore**

```gitignore
node_modules/
frontend/dist/
.env
tasks.json
downloads/
__pycache__/
*.pyc
.DS_Store
*.log
.venv/
venv/
```

- [ ] **Step 3: 写 .env.example**

```
HOST=127.0.0.1
PORT=8787
DB_HOST=127.0.0.1
DB_PORT=3307
DB_USER=root
DB_PASS=
DB_NAME=export_data
TABLE_PREFIX=
```

- [ ] **Step 4: 写 tasks.example.json**

```json
[
  {
    "id": "t_example",
    "name": "示例任务",
    "url": "https://example.com/report",
    "button_text": "导出",
    "button_selector": "",
    "username": "",
    "password": "",
    "login_url": "",
    "captcha_mode": "auto",
    "output_dir": "",
    "import_after": false,
    "enabled": true,
    "headless": false
  }
]
```

- [ ] **Step 5: 写 requirements.txt 与 requirements-dev.txt**

`requirements.txt`:
```
fastapi>=0.110
uvicorn[standard]>=0.29
pydantic>=2.6
pydantic-settings>=2.2
playwright>=1.44
mysql-connector-python>=8.3
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.0
httpx>=0.27
openpyxl>=3.1
```

- [ ] **Step 6: 删除遗留文件与真实数据**

```bash
cd /Users/wulinxin/Desktop/export-automation
rm -f browser_click_generate.mjs click_export.mjs generate_order.mjs import_orders.py \
      "方案.html" "订单自动化逆向结果.html" server.mjs package.json package-lock.json server.log
rm -rf web node_modules downloads orders_extracted __pycache__ .DS_Store
find . -name '.DS_Store' -delete
```
Expected: 目录下只剩 `README.md`、`auto_export.mjs`、`import_generic.py`、`docs/`、`.gitignore`、`.env.example`、`tasks.example.json`、`requirements*.txt`、`.git/`。

- [ ] **Step 7: 首次提交**

```bash
git add -A
git commit -m "chore: 初始化仓库、清理遗留、搭建配置骨架

Co-Authored-By: Claude <noreply@anthropic.com>"
```
Expected: commit 成功，`git status` 干净。

---

### Task 2: config.py — 配置加载

**Files:**
- Create: `app/__init__.py`、`app/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings`（pydantic-settings，字段见下）、`settings` 单例、`resolve_output_dir(output_dir, name, root="downloads") -> str`。

- [ ] **Step 1: 写失败测试** `tests/test_config.py`

```python
from app.config import Settings, resolve_output_dir


def test_settings_defaults():
    s = Settings(_env_file=None)  # 不读 .env，纯默认值
    assert s.host == "127.0.0.1"
    assert s.port == 8787
    assert s.db_name == "export_data"
    assert s.db_pass == ""
    assert s.tasks_file == "tasks.json"
    assert s.downloads_root == "downloads"


def test_resolve_output_dir_uses_explicit():
    assert resolve_output_dir("/tmp/out", "x") == "/tmp/out"


def test_resolve_output_dir_falls_back_to_name():
    import os
    assert resolve_output_dir("", "客户A", root="downloads") == os.path.join("downloads", "客户A")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/wulinxin/Desktop/export-automation && python3 -m pytest tests/test_config.py -v`
Expected: FAIL（`ModuleNotFoundError: app.config`）

- [ ] **Step 3: 实现** `app/config.py`

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add app/__init__.py app/config.py tests/test_config.py
git commit -m "feat: 配置加载模块 config.py

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: tasks.py — 任务模型与持久化

**Files:**
- Create: `app/tasks.py`
- Test: `tests/test_tasks.py`

**Interfaces:**
- Produces: `Task(BaseModel)`（字段见 spec §6，含 `model_validator` 校验）、`new_task_id() -> str`、`TaskStore(path)`（`list/create/update/delete/get`）。
- Consumes: 无（依赖 pydantic）。

- [ ] **Step 1: 写失败测试** `tests/test_tasks.py`

```python
import json
import pytest
from pydantic import ValidationError
from app.tasks import Task, TaskStore, new_task_id


def test_valid_task():
    t = Task(name="a", url="https://x.com/report", button_text="导出")
    assert t.captcha_mode == "auto"
    assert t.import_after is False


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
    store.update(t.id, {"import_after": True})
    assert store.get(t.id).import_after is True
    # 删除
    assert store.delete(t.id) is True
    assert store.delete(t.id) is False


def test_create_ignores_client_id():
    store = TaskStore(str(tmp_path) + "/t.json")
    t = store.create({"id": "should_be_overridden", "name": "a", "url": "https://x.com", "button_text": "导出"})
    assert t.id != "should_be_overridden"
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_tasks.py -v`
Expected: FAIL（`ModuleNotFoundError: app.tasks`）

- [ ] **Step 3: 实现** `app/tasks.py`

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_tasks.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add app/tasks.py tests/test_tasks.py
git commit -m "feat: 任务模型与 tasks.json 持久化

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: browser.py — 纯函数（验证码解析 / 扩展名推断）

**Files:**
- Create: `app/browser.py`（本任务只加两个纯函数；引擎在 Task 6）
- Test: `tests/test_browser_utils.py`

**Interfaces:**
- Produces: `solve_captcha_svg(svg: str) -> str`、`guess_ext(content_type: str, content_disposition: str) -> str`。
- Consumes: 无。

- [ ] **Step 1: 写失败测试** `tests/test_browser_utils.py`

```python
from app.browser import solve_captcha_svg, guess_ext


def test_solve_captcha_sorts_by_x():
    svg = '<svg><text x="30" y="0">B</text><text x="10" y="0">A</text><text x="20" y="0">C</text></svg>'
    assert solve_captcha_svg(svg) == "ACB"


def test_solve_captcha_fallback_document_order():
    svg = '<svg><tspan>A</tspan><tspan>B</tspan></svg>'
    assert solve_captcha_svg(svg) == "AB"


def test_guess_ext_from_content_type():
    assert guess_ext("application/zip", "") == "zip"
    assert guess_ext("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "") == "xlsx"
    assert guess_ext("text/csv", "") == "csv"
    assert guess_ext("application/pdf", "") == "pdf"
    assert guess_ext("application/octet-stream", "") == "bin"


def test_guess_ext_from_disposition():
    cd = "attachment; filename*=UTF-8''%E8%AE%A2%E5%8D%95.zip"
    assert guess_ext("application/octet-stream", cd) == "zip"
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_browser_utils.py -v`
Expected: FAIL（`ModuleNotFoundError: app.browser`）

- [ ] **Step 3: 实现** `app/browser.py`（纯函数部分）

```python
import re
from pathlib import Path


def solve_captcha_svg(svg: str) -> str:
    items = []
    rx = re.compile(r'<(?:text|tspan)\b[^>]*\bx="([\d.]+)"[^>]*>([^<]*)</(?:text|tspan)>', re.I)
    for m in rx.finditer(svg):
        items.append((float(m.group(1) or 0), m.group(2)))
    if not items:
        rs = re.compile(r'<(?:text|tspan)\b[^>]*>([^<]*)</(?:text|tspan)>', re.I)
        for i, m in enumerate(rs.finditer(svg)):
            items.append((i, m.group(1)))
    return "".join(ch for _, ch in sorted(items, key=lambda p: p[0])).strip()


def guess_ext(content_type: str, content_disposition: str) -> str:
    m = (re.search(r'filename\*?=(?:UTF-8\'\'|"?)([^";]+)', content_disposition, re.I)
         or re.search(r'filename="?([^";]+)"?', content_disposition, re.I))
    if m:
        ext = Path(m.group(1)).suffix
        if ext:
            return ext.lstrip(".")
    ct = (content_type or "").lower()
    if "zip" in ct:
        return "zip"
    if "spreadsheetml" in ct or "xlsx" in ct or "excel" in ct:
        return "xlsx"
    if "csv" in ct:
        return "csv"
    if "pdf" in ct:
        return "pdf"
    return "bin"
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_browser_utils.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add app/browser.py tests/test_browser_utils.py
git commit -m "feat: 验证码解析与扩展名推断纯函数

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: import_data.py — 纯函数（表头识别 / 类型推断）

**Files:**
- Create: `app/import_data.py`（本任务只加纯函数与 xlsx/csv 读取；入库函数在 Task 7）
- Test: `tests/test_import_types.py`

**Interfaces:**
- Produces: `detect_header(grid) -> tuple[int | None, list[str]]`、`infer_type(vals: list[str]) -> str`、`sanitize(name, used) -> str`、`table_name(file_stem, sheet, total_sheets, prefix="") -> str`、`read_csv_sheets(path)`、`read_xlsx_sheets(path)`、`col_to_num`、`col_letter`。
- Consumes: 无（用 openpyxl 在测试里生成 xlsx 夹具）。

- [ ] **Step 1: 写失败测试** `tests/test_import_types.py`

```python
import csv
import openpyxl
from app.import_data import infer_type, detect_header, sanitize, table_name, read_csv_sheets, read_xlsx_sheets


def test_infer_type():
    assert infer_type(["1", "2", "-3"]) == "BIGINT"
    assert infer_type(["1", "2.5", "3"]) == "DOUBLE"
    assert infer_type(["2026-08-20", "2026-08-21"]) == "DATE"
    assert infer_type(["2026-08-20 10:00:00"]) == "DATETIME"
    assert infer_type(["hello"]) == "VARCHAR(255)"
    assert infer_type(["x" * 300]) == "TEXT"
    assert infer_type([]) == "VARCHAR(255)"


def test_detect_header_skips_title_row():
    grid = {
        (1, "A"): "多肽合成清单", (1, "B"): "",
        (2, "A"): "序列", (2, "B"): "数量",
        (3, "A"): "AAAA", (3, "B"): "5",
        (4, "A"): "BBBB", (4, "B"): "7",
    }
    header_row, headers = detect_header(grid)
    assert header_row == 2
    assert headers == ["序列", "数量"]


def test_sanitize_dedup_and_digit_prefix():
    used = set()
    assert sanitize("序列 号", used) == "序列_号"
    assert sanitize("序列 号", used) == "序列_号_2"
    assert sanitize("2024年", used) == "c_2024年"


def test_table_name():
    assert table_name("订单", "Sheet1", 1) == "订单"
    assert table_name("订单", "明细", 2) == "订单_明细"
    assert table_name("订单", "明细", 2, prefix="exp") == "exp_订单_明细"


def test_read_csv_sheets(tmp_path):
    p = tmp_path / "a.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([["a", "b"], ["1", "2"]])
    sheets = read_csv_sheets(str(p))
    assert sheets[0][0] == "data"
    assert sheets[0][1][(1, "A")] == "a"


def test_read_xlsx_sheets(tmp_path):
    p = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "明细"
    ws.append(["a", "b"])
    ws.append(["1", "2"])
    wb.save(p)
    sheets = read_xlsx_sheets(str(p))
    assert sheets[0][0] == "明细"
    assert sheets[0][1][(1, "A")] == "a"
    assert sheets[0][1][(2, "B")] == "2"
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_import_types.py -v`
Expected: FAIL（`ModuleNotFoundError: app.import_data`）

- [ ] **Step 3: 实现** `app/import_data.py`（纯函数 + 读取部分）

```python
import csv
import re
import zipfile
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

INT_RE = re.compile(r"^-?\d+$")
FLOAT_RE = re.compile(r"^-?(\d+\.\d*|\.\d+|\d+[eE][+-]?\d+|\d+\.\d+[eE][+-]?\d+)$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")


def col_to_num(s: str) -> int:
    n = 0
    for ch in s.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def col_letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def read_xlsx_sheets(path: str) -> list[tuple[str, dict]]:
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    sheets = []
    if "xl/workbook.xml" in z.namelist():
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        for s in wb.findall(f"{NS}sheets"):
            for sh in s.findall(f"{NS}sheet"):
                sheets.append((sh.get("name"), sh.get(f"{REL_NS}id")))
    rels = {}
    if "xl/_rels/workbook.xml.rels" in z.namelist():
        rr = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        for rel in rr.findall(f"{REL_NS}Relationship"):
            rels[rel.get("Id")] = rel.get("Target")
    result = []
    for name, rid in sheets:
        target = rels.get(rid, "worksheets/sheet1.xml")
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        if target not in z.namelist():
            cand = "xl/worksheets/" + target.split("/")[-1]
            target = cand if cand in z.namelist() else target
        if target not in z.namelist():
            continue
        root = ET.fromstring(z.read(target))
        grid = {}
        for row in root.iter(f"{NS}row"):
            r = int(row.get("r"))
            for c in row.findall(f"{NS}c"):
                ref = c.get("r") or ""
                col = "".join(ch for ch in ref if ch.isalpha())
                t = c.get("t")
                val = ""
                if t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(f"{NS}t"))
                else:
                    v = c.find(f"{NS}v")
                    if v is not None and v.text is not None:
                        val = v.text
                        if t == "s" and val != "":
                            try:
                                val = shared[int(val)]
                            except Exception:
                                pass
                grid[(r, col)] = val
        result.append((name, grid))
    return result


def read_csv_sheets(path: str) -> list[tuple[str, dict]]:
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.reader(f))
    grid = {}
    for ri, row in enumerate(rows, start=1):
        for ci, val in enumerate(row, start=1):
            grid[(ri, col_letter(ci))] = val
    return [("data", grid)]


def detect_header(grid: dict) -> tuple[int | None, list[str]]:
    rows = sorted(set(r for (r, _c) in grid))

    def cnt(r):
        return sum(1 for (rr, _c), v in grid.items() if rr == r and str(v).strip() != "")

    best_r, best_score = None, -1
    for r in rows[:10]:
        c = cnt(r)
        following = sum(1 for rr in (r + 1, r + 2, r + 3) if cnt(rr) >= 1)
        score = c * 10 + following
        if score > best_score:
            best_r, best_score = r, score
    if best_r is None or cnt(best_r) < 2:
        return None, []
    cols = sorted(col_to_num(c) for (rr, c) in grid if rr == best_r and str(grid[(rr, c)]).strip() != "")
    maxc = max(cols)
    headers = [str(grid.get((best_r, col_letter(cn)), "")).strip() or f"col_{cn}" for cn in range(1, maxc + 1)]
    return best_r, headers


def sanitize(name: str, used: set) -> str:
    n = re.sub(r"[^\w一-鿿]+", "_", str(name).strip(), flags=re.UNICODE)
    n = re.sub(r"_+", "_", n).strip("_") or "col"
    if n[0].isdigit():
        n = "c_" + n
    n = n[:60]
    base, i = n, 2
    while n.lower() in used:
        n = f"{base}_{i}"
        i += 1
    used.add(n.lower())
    return n


def infer_type(vals: list[str]) -> str:
    if not vals:
        return "VARCHAR(255)"
    if all(INT_RE.match(v) for v in vals):
        return "BIGINT"
    if all(INT_RE.match(v) or FLOAT_RE.match(v) for v in vals):
        return "DOUBLE"
    if all(DATE_RE.match(v) for v in vals):
        return "DATE"
    if all(DT_RE.match(v) for v in vals):
        return "DATETIME"
    maxlen = max(len(v) for v in vals)
    return "TEXT" if maxlen > 255 else "VARCHAR(255)"


def table_name(file_stem: str, sheet: str, total_sheets: int, prefix: str = "") -> str:
    def clean(s):
        s = re.sub(r"[^\w一-鿿]+", "_", s, flags=re.UNICODE)
        s = re.sub(r"_+", "_", s).strip("_")
        return s or "t"
    parts = [clean(file_stem)]
    if not (total_sheets == 1 and re.match(r"^sheet\d+$", sheet, re.I)):
        parts.append(clean(sheet))
    name = "_".join(parts)
    if name[0].isdigit():
        name = "t_" + name
    name = name[:60]
    return (prefix + "_" + name) if prefix else name
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_import_types.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add app/import_data.py tests/test_import_types.py
git commit -m "feat: 入库纯函数（表头识别/类型推断/xlsx与csv读取）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: browser.py — 引擎 run_task（移植自 auto_export.mjs）

**Files:**
- Modify: `app/browser.py`（追加引擎 + 定位候选函数）
- Delete: `auto_export.mjs`（移植完成后删）

**Interfaces:**
- Produces: `@dataclass RunResult {ok: bool, files: list[str], error: str}`、`async def run_task(task, on_log: Callable[[str], None]) -> RunResult`、`classify(line) -> str`（供前端着色/测试用）。
- Consumes: `Task`（Task 3）、`solve_captcha_svg`/`guess_ext`（Task 4）、`resolve_output_dir`（Task 2）。

> 本任务依赖真实 Chrome + 目标站点，**无自动化单测**；交付验证为：`python3 -c "import app.browser"` 无语法错误 + 手动冒烟（README 记步骤）。端口时以 `auto_export.mjs` 为唯一参照。

- [ ] **Step 1: 移植定位候选函数 + 下载捕获 + 登录（追加到 app/browser.py）**

关键点（从 auto_export.mjs 逐行对应移植到 Playwright-Python async API）：
- `find_username/find_password/find_captcha_input/find_captcha_image/find_login_button/find_export_button`：候选选择器列表与 JS 版一一对应，`page.locator(s).first()`，`.count()` / `.is_visible()`。
- `do_login`：`page.goto` → `wait_for_timeout` → 找框填值 → 验证码 → 点登录 → 判定跳转。
- 下载捕获：`page.on("download", handler)` 存到 `resolve_output_dir(...)`；`page.on("response", handler)` 拦截 `content-disposition: attachment` 或文件型 content-type，读 `response.body()` 落盘。
- 验证码识别复用 Task 4 的 `solve_captcha_svg`。
- 时间戳文件名：`time.strftime("%Y%m%d_%H%M%S")`。

写出完整实现（约 200 行）。核心签名与骨架如下（实现者补齐全部候选列表与逻辑，严格对照 auto_export.mjs）：

```python
import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Callable

from playwright.async_api import async_playwright

from .config import resolve_output_dir, settings
from .tasks import Task

LOGIN_USERNAME_CANDIDATES = [
    'input[placeholder*="用户名"]', 'input[placeholder*="账号"]', 'input[placeholder*="手机"]',
    'input[placeholder*="邮箱"]', 'input[placeholder*="username"]', 'input[placeholder*="account"]',
    'input[placeholder*="user"]', 'input[name*="username"]', 'input[name*="account"]',
    'input[name*="phone"]', 'input[name*="loginName"]', 'input[type="email"]', 'input[type="text"]',
]
# ...（PASSWORD / CAPTCHA_INPUT / CAPTCHA_IMAGE / LOGIN_BUTTON 候选列表，与 auto_export.mjs 完全一致）


@dataclass
class RunResult:
    ok: bool
    files: list[str] = field(default_factory=list)
    error: str = ""


def classify(line: str) -> str:
    if line.startswith("[✓]") or "登录成功" in line or "下载完成" in line or "入库完成" in line:
        return "ok"
    if line.startswith("[!]") or line.startswith("[×]") or "失败" in line or "错误" in line or "Error" in line:
        return "err"
    if line.startswith("[net]"):
        return "net"
    if line.startswith("[验证码]"):
        return "captcha"
    if line.startswith("[warn]") or "警告" in line:
        return "warn"
    if line.startswith("[i]"):
        return "info"
    return "dim"


async def run_task(task: Task, on_log: Callable[[str], None]) -> RunResult:
    log = on_log
    if not task.url:
        return RunResult(ok=False, error="未指定目标页面 URL")
    if not task.button_text and not task.button_selector:
        return RunResult(ok=False, error="请指定导出按钮文字或 CSS 选择器")

    out_dir = resolve_output_dir(task.output_dir, task.name, settings.downloads_root)
    os.makedirs(out_dir, exist_ok=True)
    downloaded: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=task.headless)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        async def on_download(d):
            path = os.path.join(out_dir, d.suggested_filename)
            await d.save_as(path)
            if path not in downloaded:
                downloaded.append(path)
                log(f"[✓] 下载完成: {path}")

        async def on_response(res):
            headers = res.headers
            ct = (headers.get("content-type") or "").lower()
            cd = headers.get("content-disposition") or ""
            is_file = ("attachment" in cd.lower()) or any(k in ct for k in ("zip", "spreadsheetml", "excel", "csv", "octet-stream", "pdf"))
            if res.status == 200 and is_file:
                try:
                    body = await res.body()
                    if body:
                        path = os.path.join(out_dir, f"download_{time.strftime('%Y%m%d_%H%M%S')}.{guess_ext(ct, cd)}")
                        with open(path, "wb") as f:
                            f.write(body)
                        if path not in downloaded:
                            downloaded.append(path)
                            log(f"[net] 捕获接口文件: {path}")
                except Exception:
                    pass

        page.on("download", on_download)
        page.on("response", on_response)

        # 1) 登录（可选）
        if task.username or task.password:
            login_url = task.login_url or f"{task.url.rsplit('/', 1)[0]}/login" if "://" in task.url else task.login_url
            await _do_login(page, task, login_url, log)

        # 2) 进目标页
        if page.url != task.url:
            await page.goto(task.url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)

        # 3) 定位并点击导出按钮
        btn = await _find_export_button(page, task)
        if btn is None or not await btn.count():
            await browser.close()
            return RunResult(ok=False, error=f'未找到导出按钮（按钮文字="{task.button_text}" 选择器="{task.button_selector}"）')
        await btn.scroll_into_view_if_needed()
        await btn.wait_for(state="visible", timeout=15000)
        log("[i] 已找到导出按钮，点击中…")
        try:
            await btn.click()
        except Exception:
            try:
                await btn.click(force=True)
            except Exception:
                pass

        await page.wait_for_timeout(1500)
        if not downloaded:
            for s in ['button:has-text("确定")', 'button:has-text("确认")', '.el-message-box button:has-text("确定")']:
                el = page.locator(s).first()
                if await el.count() and await el.is_visible():
                    await el.click()
                    log("[i] 已点击确认弹窗")
                    break
        await page.wait_for_timeout(4500)

        await browser.close()

    if downloaded:
        for f in downloaded:
            log(f"[完成] 已产出文件: {f}")
    else:
        log("[!] 未捕获到下载文件，请检查页面是否有报错/弹窗")
    return RunResult(ok=bool(downloaded), files=downloaded,
                     error="" if downloaded else "未捕获到下载文件")
```

> 实现者需补齐 `_do_login`、`_find_export_button`、`_find_username`、`_find_password`、`_find_captcha_input`、`_find_captcha_image`、`_find_login_button`、`_solve_captcha` 等辅助函数，逻辑与 `auto_export.mjs` 完全一致（候选列表、回退顺序、判定条件照搬）。

- [ ] **Step 2: 语法/导入自检**

Run: `python3 -c "import app.browser; print('ok')"`
Expected: 输出 `ok`，无异常。

- [ ] **Step 3: 手动冒烟（可选，需真实站点）**

按 spec §13 的端点尚未存在，本步仅用临时脚本直调 `run_task` 验证；无站点则跳过并在 README 标注待验证。

- [ ] **Step 4: 删除移植源**

```bash
rm -f auto_export.mjs
```

- [ ] **Step 5: 提交**

```bash
git add app/browser.py
git rm auto_export.mjs
git commit -m "feat: Playwright 引擎 run_task 移植；删除旧 auto_export.mjs

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: import_data.py — import_files 入库（移植自 import_generic.py）

**Files:**
- Modify: `app/import_data.py`（追加 `import_files` + `collect_files`）
- Delete: `import_generic.py`（移植完成后删）

**Interfaces:**
- Produces: `import_files(paths: list[str]) -> dict`（返回 `{tables: [...], total_rows: int}`）。
- Consumes: `detect_header/infer_type/sanitize/table_name/read_xlsx_sheets/read_csv_sheets`（Task 5）、`settings`（Task 2）。

> DB 部分依赖真实 MySQL，**无自动化单测**；纯函数已由 Task 5 覆盖。交付验证：`python3 -c "import app.import_data"` 无错 + README 手动冒烟。

- [ ] **Step 1: 实现 import_files + collect_files（追加到 app/import_data.py）**

```python
import glob
import os
import shutil
import sys
import tempfile

import mysql.connector

from .config import settings


def collect_files(args: list[str]) -> list[str]:
    files = []
    for a in args:
        if os.path.isdir(a):
            files += sorted(glob.glob(os.path.join(a, "*.xlsx")) + glob.glob(os.path.join(a, "*.xls")) + glob.glob(os.path.join(a, "*.csv")))
        elif a.lower().endswith(".zip"):
            dest = tempfile.mkdtemp(prefix="xlsx_import_")
            with zipfile.ZipFile(a) as z:
                z.extractall(dest)
            files += sorted(glob.glob(os.path.join(dest, "**", "*.xlsx"), recursive=True)
                            + glob.glob(os.path.join(dest, "**", "*.xls"), recursive=True)
                            + glob.glob(os.path.join(dest, "**", "*.csv"), recursive=True))
        elif a.lower().endswith((".xlsx", ".xls", ".csv")):
            files.append(a)
    seen, out = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _extract_rows(grid, header_row, ncols):
    rows = []
    maxr = max(r for (r, _c) in grid)
    for r in range(header_row + 1, maxr + 1):
        vals = [str(grid.get((r, col_letter(cn)), "")).strip() for cn in range(1, ncols + 1)]
        if any(v != "" for v in vals):
            rows.append(vals)
    return rows


def import_files(paths: list[str]) -> dict:
    if not settings.db_pass:
        raise RuntimeError("未配置 DB_PASS，无法入库（请在 .env 中设置）")
    files = collect_files(paths)
    if not files:
        return {"tables": [], "total_rows": 0}

    conn = mysql.connector.connect(host=settings.db_host, port=settings.db_port, user=settings.db_user,
                                   password=settings.db_pass, database=settings.db_name)
    cur = conn.cursor()
    summary = []
    total_rows = 0
    try:
        for f in files:
            stem = os.path.splitext(os.path.basename(f))[0]
            sheets = read_csv_sheets(f) if f.lower().endswith(".csv") else read_xlsx_sheets(f)
            if not sheets:
                continue
            for sheet, grid in sheets:
                header_row, headers = detect_header(grid)
                if header_row is None:
                    continue
                used = set()
                cols = [sanitize(h, used) for h in headers]
                ncols = len(cols)
                rows = _extract_rows(grid, header_row, ncols)
                coltypes = []
                for ci in range(ncols):
                    sample = [r[ci] for r in rows if r[ci] != ""][:500]
                    coltypes.append(infer_type(sample))
                tname = table_name(stem, sheet, len(sheets), settings.table_prefix)
                coldefs = ", ".join(f"`{c}` {t}" for c, t in zip(cols, coltypes))
                ddl = f"CREATE TABLE `{tname}` (__pk BIGINT AUTO_INCREMENT PRIMARY KEY, {coldefs}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                cur.execute(f"DROP TABLE IF EXISTS `{tname}`")
                cur.execute(ddl)
                placeholders = ", ".join(["%s"] * ncols)
                collist = ", ".join(f"`{c}`" for c in cols)
                sql = f"INSERT INTO `{tname}` ({collist}) VALUES ({placeholders})"
                data = [[(None if v == "" else v) for v in r] for r in rows]
                if data:
                    cur.executemany(sql, data)
                conn.commit()
                summary.append({"table": tname, "rows": len(data), "columns": ncols,
                                "source": f"{os.path.basename(f)}/{sheet}"})
                total_rows += len(data)
    finally:
        cur.close()
        conn.close()
    return {"tables": summary, "total_rows": total_rows}
```

- [ ] **Step 2: 导入自检**

Run: `python3 -c "import app.import_data; print('ok')"`
Expected: 输出 `ok`。

- [ ] **Step 3: 删除移植源**

```bash
rm -f import_generic.py
```

- [ ] **Step 4: 提交**

```bash
git add app/import_data.py
git rm import_generic.py
git commit -m "feat: MySQL 入库 import_files；删除旧 import_generic.py

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: main.py — FastAPI 应用 + 任务 CRUD / status / 静态托管

**Files:**
- Create: `app/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces: `create_app(store: TaskStore | None = None) -> FastAPI`、`app = create_app()`。
- Consumes: `TaskStore/Task`（Task 3）、`Settings`（Task 2）、`browser.run_task/classify`（Task 6）、`import_data.import_files`（Task 7）。

- [ ] **Step 1: 写失败测试** `tests/test_api.py`

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_api.py -v`
Expected: FAIL（`ModuleNotFoundError: app.main`）

- [ ] **Step 3: 实现** `app/main.py`

```python
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
    async def status(url: str = "http://localhost:5173"):
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_api.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: FastAPI 应用与任务 CRUD/status 端点

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: /api/run 流式端点测试（monkeypatch 引擎）

**Files:**
- Test: `tests/test_api_run.py`

**Interfaces:**
- Consumes: `create_app`（Task 8）、`app.browser.run_task`（被 monkeypatch）、`app.import_data.import_files`（被 monkeypatch）。

- [ ] **Step 1: 写失败测试** `tests/test_api_run.py`

```python
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
        lines = [l for l in resp.iter_lines() if l.strip()]
    types = [__import__("json").loads(l)["type"] for l in lines]
    assert types == ["task_start", "log", "log", "task_end", "done"]
    end = __import__("json").loads(lines[3])
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
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest tests/test_api_run.py -v`
Expected: FAIL（`ModuleNotFoundError: app.main`）

- [ ] **Step 3: （无需额外操作）**

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest tests/test_api_run.py -v`
Expected: PASS（保留的测试全绿）

- [ ] **Step 5: 提交**

```bash
git add tests/test_api_run.py
git commit -m "test: /api/run 流式端点与运行锁

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: 前端脚手架 + Vite 代理

**Files:**
- Create: `frontend/`（`package.json`、`vite.config.ts`、`tsconfig*.json`、`index.html`、`src/main.tsx` 等，由脚手架生成后改造）

**Interfaces:**
- Produces: 可运行的 Vite + React + TS 工程，`/api` 代理到后端。

- [ ] **Step 1: 脚手架**

```bash
cd /Users/wulinxin/Desktop/export-automation
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
```

- [ ] **Step 2: 配置代理** `frontend/vite.config.ts`

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8787', changeOrigin: true },
    },
  },
})
```

- [ ] **Step 3: 验证可启动**

Run: `cd frontend && npm run build`
Expected: 构建成功（`dist/` 生成）。

- [ ] **Step 4: 提交**

```bash
cd /Users/wulinxin/Desktop/export-automation
git add frontend/
git commit -m "chore: 前端脚手架（React+Vite+TS）+ /api 代理

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: 前端 types.ts + api.ts

**Files:**
- Create: `frontend/src/types.ts`、`frontend/src/api.ts`

**Interfaces:**
- Produces: `Task`、`RunEvent`（判别联合）、`RunSummary` TS 类型；`listTasks/createTask/updateTask/deleteTask/fetchStatus/streamRun`。
- Consumes: 无（纯前端）。

- [ ] **Step 1: 实现 types.ts**

```ts
export interface Task {
  id: string
  name: string
  url: string
  button_text: string
  button_selector: string
  username: string
  password: string
  login_url: string
  captcha_mode: 'auto' | 'none' | 'manual'
  output_dir: string
  import_after: boolean
  enabled: boolean
  headless: boolean
}

export type TaskInput = Omit<Task, 'id'>

export type RunEvent =
  | { type: 'task_start'; task_id: string; name: string; index: number; total: number }
  | { type: 'log'; task_id: string; line: string; level: string }
  | { type: 'task_end'; task_id: string; ok: boolean; files: string[]; imported: unknown; error: string }
  | { type: 'done'; summary: { total: number; ok: number; failed: number } }
```

- [ ] **Step 2: 实现 api.ts**

```ts
import type { RunEvent, Task, TaskInput } from './types'

const JSON_HEADERS = { 'Content-Type': 'application/json' }

export async function fetchStatus(url: string): Promise<{ db: boolean; site: boolean }> {
  const r = await fetch('/api/status?url=' + encodeURIComponent(url))
  return r.json()
}

export async function listTasks(): Promise<Task[]> {
  const r = await fetch('/api/tasks')
  return (await r.json()).tasks
}

export async function createTask(t: TaskInput): Promise<Task> {
  const r = await fetch('/api/tasks', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(t) })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()).task
}

export async function updateTask(id: string, patch: Partial<TaskInput>): Promise<Task> {
  const r = await fetch('/api/tasks/' + id, { method: 'PUT', headers: JSON_HEADERS, body: JSON.stringify(patch) })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()).task
}

export async function deleteTask(id: string): Promise<void> {
  await fetch('/api/tasks/' + id, { method: 'DELETE' })
}

export async function streamRun(ids: string[], onEvent: (e: RunEvent) => void): Promise<void> {
  const r = await fetch('/api/run', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ ids }) })
  if (!r.ok || !r.body) throw new Error('HTTP ' + r.status)
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, idx).trim()
      buffer = buffer.slice(idx + 1)
      if (line) onEvent(JSON.parse(line) as RunEvent)
    }
  }
}
```

- [ ] **Step 3: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/types.ts frontend/src/api.ts
git commit -m "feat: 前端类型定义与 API 客户端

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 12: 前端组件与 App

**Files:**
- Create: `frontend/src/components/StatusPills.tsx`、`TaskList.tsx`、`TaskForm.tsx`、`Console.tsx`
- Modify: `frontend/src/App.tsx`、`frontend/src/main.tsx`、`frontend/src/App.css`（或删除并入 styles.css）

**Interfaces:**
- Consumes: `types.ts`、`api.ts`（Task 11）。

- [ ] **Step 1: 实现 StatusPills.tsx**

```tsx
import { useEffect, useState } from 'react'
import { fetchStatus } from '../api'

export default function StatusPills({ url }: { url: string }) {
  const [s, setS] = useState({ db: false, site: false })
  useEffect(() => {
    let alive = true
    const tick = () => fetchStatus(url).then(x => alive && setS(x)).catch(() => {})
    tick()
    const h = setInterval(tick, 15000)
    return () => { alive = false; clearInterval(h) }
  }, [url])
  return (
    <div className="status-group">
      <span className={`status-pill ${s.site ? 'ok' : 'off'}`}><span className="dot" />站点</span>
      <span className={`status-pill ${s.db ? 'ok' : 'off'}`}><span className="dot" />数据库</span>
    </div>
  )
}
```

- [ ] **Step 2: 实现 TaskForm.tsx（新增/编辑表单，字段对齐 TaskInput）**

```tsx
import { useState } from 'react'
import type { Task, TaskInput } from '../types'

const EMPTY: TaskInput = {
  name: '', url: '', button_text: '', button_selector: '', username: '', password: '',
  login_url: '', captcha_mode: 'auto', output_dir: '', import_after: false, enabled: true, headless: false,
}

export default function TaskForm({ initial, onSave, onCancel }: {
  initial?: Task | null
  onSave: (t: TaskInput) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState<TaskInput>(initial ?? EMPTY)
  const set = (k: keyof TaskInput, v: unknown) => setForm(f => ({ ...f, [k]: v }))
  const submit = () => { onSave(form) }
  return (
    <div className="task-form">
      <input placeholder="任务名称" value={form.name} onChange={e => set('name', e.target.value)} />
      <input placeholder="目标页面 URL" value={form.url} onChange={e => set('url', e.target.value)} />
      <input placeholder="导出按钮文字" value={form.button_text} onChange={e => set('button_text', e.target.value)} />
      <input placeholder="输出目录（留空 = downloads/名称）" value={form.output_dir} onChange={e => set('output_dir', e.target.value)} />
      <details>
        <summary>登录与高级选项</summary>
        <input placeholder="用户名" value={form.username} onChange={e => set('username', e.target.value)} />
        <input type="password" placeholder="密码" value={form.password} onChange={e => set('password', e.target.value)} />
        <input placeholder="CSS 选择器（优先级最高）" value={form.button_selector} onChange={e => set('button_selector', e.target.value)} />
        <input placeholder="登录页 URL" value={form.login_url} onChange={e => set('login_url', e.target.value)} />
        <select value={form.captcha_mode} onChange={e => set('captcha_mode', e.target.value)}>
          <option value="auto">自动识别验证码</option>
          <option value="none">无验证码</option>
          <option value="manual">人工截图</option>
        </select>
        <label><input type="checkbox" checked={form.import_after} onChange={e => set('import_after', e.target.checked)} /> 下载后入库</label>
        <label><input type="checkbox" checked={form.enabled} onChange={e => set('enabled', e.target.checked)} /> 启用</label>
      </details>
      <button onClick={submit}>保存</button>
      <button onClick={onCancel}>取消</button>
    </div>
  )
}
```

- [ ] **Step 3: 实现 TaskList.tsx + Console.tsx + App.tsx**

`TaskList.tsx`：用 `listTasks` 拉取，渲染表格（启用开关/名称/URL/按钮文字/输出目录/入库开关/操作：编辑、删除、单条运行）。`Console.tsx`：接收 `RunEvent` 列表，按 `task_id` 分组渲染彩色日志。`App.tsx`：组合 StatusPills + TaskList + TaskForm（弹层）+ Console，`运行全部` 调用 `streamRun([], ...)`，`单条运行` 调用 `streamRun([id], ...)`。

实现完整组件（具体 UI 布局与交互按 spec §9）。App.tsx 骨架：

```tsx
import { useState } from 'react'
import StatusPills from './components/StatusPills'
import TaskList from './components/TaskList'
import TaskForm from './components/TaskForm'
import Console from './components/Console'
import { streamRun } from './api'
import type { RunEvent, Task, TaskInput } from './types'

export default function App() {
  const [events, setEvents] = useState<RunEvent[]>([])
  const [editing, setEditing] = useState<Task | null | undefined>(undefined)
  const [running, setRunning] = useState(false)

  const run = async (ids: string[]) => {
    setEvents([]); setRunning(true)
    try { await streamRun(ids, e => setEvents(prev => [...prev, e])) }
    finally { setRunning(false) }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">通用导出自动化 · 操作台</div>
        <StatusPills url="http://localhost:5173" />
      </header>
      <main>
        <TaskList onEdit={setEditing} onRunOne={id => run([id])} />
        <button disabled={running} onClick={() => run([])}>运行全部</button>
        {editing !== undefined && <TaskForm initial={editing} onCancel={() => setEditing(undefined)}
          onSave={async t => { /* create 或 update 后关闭并刷新 */ }} />}
        <Console events={events} />
      </main>
    </div>
  )
}
```

- [ ] **Step 4: main.tsx 精简 + 移除 App.css 默认内容**

`main.tsx` 保留 `createRoot(...).render(<StrictMode><App/></StrictMode>)`，`import './styles.css'`。

- [ ] **Step 5: 构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功，无 TS 报错。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/
git commit -m "feat: 任务列表/表单/控制台前端组件

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 13: 前端样式（深色主题）

**Files:**
- Create: `frontend/src/styles.css`

**Interfaces:**
- Consumes: 组件的 className（Task 12）。

- [ ] **Step 1: 实现 styles.css**

沿用原 [web/index.html](web/index.html) 的深色主题 token（背景 `#080b10`、强调色 `#2dd4bf` 青绿、状态色 `#34d399/#fb7185`），覆盖 `.topbar`、`.brand`、`.status-pill`、`.task-table`、`.task-form`、`.console`、`.log-line`（ok/err/net/captcha/info/dim 着色）、`.run-btn` 等类。CSS 变量：

```css
:root {
  --bg:#080b10; --surface:#10151d; --surface2:#151b25;
  --line:rgba(148,163,184,.12); --line2:rgba(148,163,184,.22);
  --text:#e9eef5; --muted:#94a1b2; --dim:#5b6878;
  --accent:#2dd4bf; --accent-strong:#14b8a6; --on-accent:#052522;
  --ok:#34d399; --warn:#fbbf24; --err:#fb7185;
}
```

- [ ] **Step 2: 构建验证**

Run: `cd frontend && npm run build`
Expected: 成功。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/styles.css
git commit -m "style: 深色主题样式

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 14: README 重写 + 集成冒烟 + 收尾

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 重写 README.md**

内容覆盖：项目简介、目录结构、环境准备（Python 3.11+、本机 Chrome、可选 MySQL）、安装（`pip install -r requirements.txt` + `cd frontend && npm install`）、配置（复制 `.env.example` 为 `.env`、复制 `tasks.example.json` 为 `tasks.json`）、启动（开发：uvicorn + vite；生产：build 后单进程）、使用流程（建任务→运行全部→按任务落盘/可选入库）、接口一览、手动冒烟步骤（浏览器点击 + 入库各一段）、环境变量说明。

- [ ] **Step 2: 后端可启动**

Run: `cd /Users/wulinxin/Desktop/export-automation && python3 -c "from app.main import app; print('app ok')"`
Expected: 输出 `app ok`。

- [ ] **Step 3: 全量测试**

Run: `python3 -m pytest -q`
Expected: 全部通过（Task 2/3/4/5/8/9 的测试）。

- [ ] **Step 4: 前端构建**

Run: `cd frontend && npm run build`
Expected: 成功。

- [ ] **Step 5: 最终提交**

```bash
cd /Users/wulinxin/Desktop/export-automation
git add README.md
git commit -m "docs: 重写 README；集成自检通过

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review 记录

- **Spec 覆盖**：spec §4 目录结构→Task 1/10；§5 .env→Task 1/2；§6 数据模型→Task 3；§7 API→Task 8/9；§8 核心模块→Task 2/3/4/5/6/7/8；§9 前端→Task 10-13；§10 安全→Task 1/8；§11 清理迁移→Task 1/6/7；§12 测试→各 Task 的测试步骤；§13 开发/生产→Task 14。
- **已知留白**：Task 6 浏览器引擎与 Task 7 入库因依赖真实 Chrome/MySQL 无自动化单测，以「导入自检 + README 手动冒烟」替代，已在各自 Task 注明。
