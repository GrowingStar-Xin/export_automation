# 通用导出自动化 · 模块化重构设计

- 日期：2026-08-21
- 状态：待评审
- 方案：B 模块化重构（后端统一 Python/FastAPI，前端 React + Vite + TS）

## 1. 背景与目标

当前项目是「通用导出自动化操作台」：给任意网站配一个「导出按钮」，模拟点击触发下载，并把文件存到指定目录、可选入库 MySQL。

本次改造的目标：

1. **彻底清空遗留**：删除多肽专用脚本、逆向文档、真实患者数据。
2. **统一技术栈**：后端从「Node + Python 双语言」统一为 **Python/FastAPI**（Playwright 有官方 Python 版，入库本来就用 Python，统一后 import 变成同进程模块调用，不再跨语言 spawn 子进程）。
3. **支持多 URL 批量**：核心能力从「单次运行」升级为「任务列表 + 批量顺序执行」，每个任务 = 目标 URL + 按钮 + 输出目录 + 可选登录 + 可选入库。
4. **任务持久化**：任务存 `tasks.json`，重启不丢。
5. **安全**：去硬编码凭据、`.env` 管理、仅本机监听、路径校验、`.gitignore`、git 版本控制。

## 2. 现状与问题

| 问题 | 说明 |
| --- | --- |
| 双语言 | `server.mjs`/`auto_export.mjs`（Node）+ `import_generic.py`（Python）拼凑，跨语言靠子进程 + 字符串解析 |
| 遗留死代码 | 4 个多肽专用脚本 + 2 份 HTML 文档 |
| 硬编码凭据 | 真实姓名/密码、`root123456` 明文在代码里 |
| 真实数据未保护 | `downloads/`、`orders_extracted/` 含真实患者数据，无 `.gitignore` |
| 无版本控制 | 项目不是 git 仓库 |
| 单次运行 | 一次只能跑一个 URL，无任务列表、无持久化 |
| 肽类残留 | `DB_NAME` 默认 `peptide_orders`、前端页脚、端口探测写死 |

## 3. 目标架构

```
┌──────────────┐   HTTP(NDJSON 流)   ┌──────────────────────────────┐
│  React 前端   │ ◄──────────────────► │  FastAPI 后端（单进程）          │
│  Vite + TS   │   /api/*            │  ├─ main.py      路由 + 静态托管 │
└──────────────┘                     │  ├─ config.py    .env 加载      │
                                     │  ├─ tasks.py     任务 CRUD      │
                                     │  ├─ browser.py   Playwright 引擎│
                                     │  └─ import_data.py MySQL 入库   │
                                     └───────────┬───────────────────┘
                                                 │ 同进程 import
                                   ┌─────────────▼─────────────┐
                                   │  Playwright(Chrome)        │
                                   │  mysql.connector → MySQL   │
                                   └───────────────────────────┘
```

- 后端单进程、单语言（Python 3.11+）。
- 浏览器引擎与入库均为**同进程模块调用**，不再 spawn 子进程。
- 前端开发期独立 Vite 服务，构建后由 FastAPI 托管静态产物。

## 4. 目录结构

```
export-automation/
├── README.md
├── .gitignore
├── .env.example                # 提交（占位符）；真实 .env 不提交
├── tasks.example.json          # 提交（示例）；真实 tasks.json 不提交
├── requirements.txt            # 运行依赖
├── requirements-dev.txt        # 测试依赖（pytest）
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口：路由 + 静态托管 + 启动
│   ├── config.py               # .env 加载、默认值、类型化配置对象
│   ├── tasks.py                # Task(pydantic) + tasks.json 读写/校验/CRUD
│   ├── browser.py              # Playwright 引擎 run_task()
│   └── import_data.py          # MySQL 入库 import_files()（移植自 import_generic.py）
├── tests/
│   ├── test_config.py
│   ├── test_tasks.py
│   ├── test_browser_utils.py
│   └── test_import_types.py
├── frontend/                   # React + Vite + TS
│   ├── package.json
│   ├── vite.config.ts          # /api 代理到后端
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api.ts              # fetch 封装 + NDJSON 流解析
│       ├── types.ts            # Task、日志事件等 TS 类型
│       ├── styles.css
│       └── components/
│           ├── TaskList.tsx
│           ├── TaskForm.tsx
│           ├── Console.tsx
│           └── StatusPills.tsx
└── downloads/                  # 默认输出根（gitignored）
```

## 5. 配置（.env）

`.env.example`（提交），真实 `.env`（不提交）：

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

- `config.py` 用 `pydantic-settings` 加载，缺省给上述默认值。
- `DB_PASS` 默认空；入库前若未配置则报错（不再有 `root123456` 之类的硬编码）。

## 6. 数据模型

`Task`（pydantic，`tasks.json` 为数组）：

```python
class Task(BaseModel):
    id: str
    name: str                                  # 展示名；也作默认输出目录名
    url: str                                   # 目标页面（必填，http/https）
    button_text: str = ""                      # 按钮文字（与 button_selector 至少一个）
    button_selector: str = ""                  # CSS 选择器（优先级最高）
    username: str = ""
    password: str = ""
    login_url: str = ""                        # 留空 = 目标页同源 /login
    captcha_mode: Literal["auto","none","manual"] = "auto"
    output_dir: str = ""                       # 留空 = downloads/<name>
    import_after: bool = False                 # 下载后是否入库
    enabled: bool = True                       # 是否纳入「运行全部」
    headless: bool = False
```

校验规则：
- `id` 由后端生成（格式 `t_<13位毫秒时间戳>`），创建时忽略客户端传入。
- `url` 必填且为 http/https。
- `button_text` 与 `button_selector` 至少填一个。
- `name` 必填；`output_dir` 留空时由后端推导为 `downloads/<name>`。
- 密码明文存于 `tasks.json`（不提交，等价本地密码管理器，见 §15 取舍）。

## 7. API 接口

| 方法 | 路径 | 请求 | 响应 |
| --- | --- | --- | --- |
| GET | `/api/status?url=…` | — | `{db: bool, site: bool}` |
| GET | `/api/tasks` | — | `{tasks: Task[]}` |
| POST | `/api/tasks` | Task（不含 id） | `{task}`（后端生成 id） |
| PUT | `/api/tasks/{id}` | Task 部分字段（合并更新，id 不可改） | `{task}` |
| DELETE | `/api/tasks/{id}` | — | `{ok: true}` |
| POST | `/api/run` | `{ids?: string[]}` | NDJSON 流（见下） |

`/api/run`：`ids` 缺省 = 全部 `enabled` 任务，按创建顺序**顺序执行**。若已有一次运行在进行中，返回 `409`（不并发，避免浏览器/资源冲突）。返回 NDJSON 流（`application/x-ndjson`），每行一个事件：

```json
{"type":"task_start","task_id":"…","name":"…","index":1,"total":3}
{"type":"log","task_id":"…","line":"…","level":"info|ok|err|warn|net|captcha|dim"}
{"type":"task_end","task_id":"…","ok":true,"files":["…"],"imported":{…},"error":"…"}
{"type":"done","summary":{"total":3,"ok":2,"failed":1}}
```

单任务执行流程：
1. 发射 `task_start`。
2. `run_task(task, on_log)`：登录(可选) → 进目标页 → 点按钮 → 抓下载到 `output_dir`；每条日志发射 `log`。
3. 若 `task.import_after` 且有文件：调用 `import_files(files)`，结果并入 `task_end.imported`。
4. 发射 `task_end`。
5. 全部结束后发射 `done`。

> 不再保留独立的 `/api/import` 端点——入库是任务属性，由后端在同进程内触发，无需客户端传任意路径（也消除了路径注入面）。未来若要手动重导，再加一个受限端点即可。

## 8. 核心模块

### 8.1 config.py
- 用 `pydantic-settings` 读 `.env`，产出类型化 `Settings` 单例（host/port/db…）。
- 提供 `DOWNLOADS_ROOT`（默认 `downloads/`）与 `resolve_output_dir(task)` 工具。

### 8.2 tasks.py
- `load_tasks() / save_tasks(list)` 读写 `tasks.json`（数组）。
- CRUD：`list_tasks() / create_task() / update_task(id) / delete_task(id)`。
- 校验（§6），非法输入抛 `ValueError`（由 FastAPI 转 422/400）。
- 写入用原子写（先写临时文件再 rename），避免并发/崩溃写坏。

### 8.3 browser.py（移植自 auto_export.mjs）
- `async def run_task(task, on_log) -> RunResult`，`RunResult = {ok, files, error}`，绝不 `sys.exit`。
- 保留现有已验证逻辑（逐行移植到 Playwright-Python **async API**）：
  - 输入框候选识别：`find_username / find_password / find_captcha_input`
  - 验证码：`find_captcha_image` + `solve_captcha_svg`（SVG `<text>/<tspan>` 按 x 坐标排序还原）
  - 按钮：`find_login_button / find_export_button`
  - 登录：`do_login`（识别失败回退、登录成功判定）
  - 下载捕获：`page.on("download")` + `page.on("response")` 拦截文件型响应兜底
  - `guess_ext`、时间戳文件命名
- 浏览器启动：`channel="chrome"`（复用本机 Chrome），`headless` 由任务控制。
- 输出目录：`task.output_dir` 或 `downloads/<name>`，逐任务 `mkdir -p`。
- 纯函数（`solve_captcha_svg`、`guess_ext`）独立导出，便于单测。

### 8.4 import_data.py（移植自 import_generic.py）
- `def import_files(paths: list[str]) -> dict`（汇总 `{tables, total_rows}`）。
- 保留：表头识别、类型推断（BIGINT/DOUBLE/DATE/DATETIME/VARCHAR/TEXT）、每 sheet 建表、zip 解包。
- 改动：DB 配置从 `config.py` 读、`DB_NAME` 默认 `export_data`、无硬编码密码。

## 9. 前端（React + Vite + TS）

- **App.tsx**：布局 = 顶栏（状态探测）+ 任务列表 + 运行控制台。
- **StatusPills**：数据库 / 站点在线状态，轮询 `/api/status`。
- **TaskList**：表格列出任务（启用开关 / 名称 / URL / 按钮文字 / 输出目录 / 入库开关 / 操作），支持新增、编辑、删除、单条运行。
- **TaskForm**：新增/编辑表单，字段对应 §6 模型（高级选项折叠：选择器 / 登录页 / 验证码模式 / headless）。
- **Console**：`POST /api/run` 的 NDJSON 流解析，按任务分段渲染彩色日志与进度。
- **api.ts**：`fetch` 封装 + `ReadableStream` 逐行解析 NDJSON。
- **types.ts**：`Task`、日志事件、`RunSummary` 等 TS 类型，与后端 pydantic 对齐。
- 风格：延续现有深色主题（青绿强调色），作为独立 `styles.css`。

## 10. 安全

- 服务默认只监听 `127.0.0.1`（`HOST` 可改）。
- 无硬编码凭据；DB 密码走 `.env`；任务密码存 `tasks.json`（不提交）。
- `/api/status`：校验 URL 为 http/https，限制超时与响应体大小，防止被用作探测/SSRF 跳板。
- 入库文件路径仅来自引擎写入的 `downloads/` 内产物，不接收客户端任意路径。
- `.gitignore`：`node_modules/`、`.env`、`tasks.json`、`downloads/`、`__pycache__/`、`.DS_Store`、`*.log`、`frontend/dist/`。

## 11. 清理与迁移

**删除（彻底清空）**：
- 脚本：`auto_export.mjs`、`browser_click_generate.mjs`、`click_export.mjs`、`generate_order.mjs`、`import_orders.py`、`import_generic.py`（逻辑已迁至 `app/`）
- 文档：`方案.html`、`订单自动化逆向结果.html`
- 数据：`downloads/*`、`orders_extracted/*`
- 杂物：`__pycache__/`、`.DS_Store`、`server.log`、`web/`（旧前端）、根 `package.json`/`package-lock.json`/`node_modules/`

**逻辑迁移映射**：

| 源 | 目标 |
| --- | --- |
| `server.mjs` 路由/静态托管 | `app/main.py` |
| `auto_export.mjs` 引擎 | `app/browser.py` |
| `import_generic.py` 入库 | `app/import_data.py` |
| `web/index.html` 界面 | `frontend/src/*` |

## 12. 测试

- 后端 `pytest`（`requirements-dev.txt`）：
  - `test_config.py`：env 解析、默认值、`resolve_output_dir`
  - `test_tasks.py`：校验（非法 url / 缺按钮）、CRUD、JSON 往返、原子写
  - `test_browser_utils.py`：`solve_captcha_svg`、`guess_ext` 纯函数
  - `test_import_types.py`：类型推断（`infer_type`）、表头识别（`detect_header`）
- 前端：本次不写单测，靠类型检查（`tsc`）+ 手动冒烟。
- 端到端（真实 Chrome 点击 + 真实 MySQL 入库）：README 手动冒烟步骤，不进 CI。

## 13. 开发 / 生产流程

- **开发**：
  - 后端：`uvicorn app.main:app --reload`（:8787）
  - 前端：`cd frontend && npm run dev`（Vite :5173，`/api` 代理到 8787）
- **生产**：
  - `cd frontend && npm run build` → FastAPI 托管 `frontend/dist`，单进程对外。

## 14. 非目标（本次不做）

- 操作台自身的登录/鉴权（本机工具）。
- 定时/周期执行（未来可加，不在本次范围）。
- 任务并行执行（本次严格顺序，串行避免浏览器/资源冲突）。
- 多用户 / 跨设备同步。

## 15. 风险与取舍

| 风险/取舍 | 说明与对策 |
| --- | --- |
| 自动化逻辑移植 | ~300 行 JS → Python，机械但量大；用真实站点手动冒烟验证，且保留纯函数单测 |
| 密码明文存 tasks.json | 不提交、仅本机；README 注明；等价本地密码管理器 |
| 依赖本机 Chrome | `channel="chrome"`；README 注明需安装 Chrome |
| 验证码 SVG 解析脆弱 | 沿用现有正则方案，仅在纯文字型验证码可用；`captcha_mode` 支持 manual 截图 |
| Playwright 首次需装浏览器 | Python 版 `channel="chrome"` 可避免下载 chromium；如需内置 chromium 再 `playwright install` |
