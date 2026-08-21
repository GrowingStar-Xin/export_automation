# 通用导出自动化 · 操作台

给任意网站配一个「导出按钮」，一键完成：**浏览器自动登录（可选）→ 点击指定按钮 → 抓取下载文件到指定目录 →（可选）通用表格入库 MySQL**。支持**多 URL 任务列表**，一键顺序批量执行。

## 架构

- 后端：**Python + FastAPI**（单进程；Playwright async + mysql.connector 均为同进程调用，不再跨语言 spawn）
- 前端：**React + Vite + TypeScript**（开发期独立运行，构建后由 FastAPI 托管静态产物）

```
export-automation/
├── app/
│   ├── main.py         # FastAPI 入口 + 路由 + 静态托管
│   ├── config.py       # .env 加载
│   ├── tasks.py        # 任务模型 + tasks.json 持久化
│   ├── browser.py      # Playwright 引擎 run_task()
│   └── import_data.py  # MySQL 入库 import_files()
├── tests/              # pytest（纯逻辑 + API）
├── frontend/           # React + Vite + TS
└── downloads/          # 默认输出根（gitignored）
```

## 环境准备

- Python 3.11+
- 本机 Chrome（浏览器自动化走 `channel="chrome"`，不下载 chromium）
- （可选）MySQL，勾选「入库」的任务需要

## 安装

```bash
pip install -r requirements.txt          # 运行依赖
pip install -r requirements-dev.txt      # 测试依赖（pytest/httpx/openpyxl）
cd frontend && npm install
```

> 国内网络：pip 可加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`；npm 已配置 npmmirror 镜像。

## 配置

```bash
cp .env.example .env              # 编辑 DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME
cp tasks.example.json tasks.json  # 任务列表（含站点密码，不提交）
```

## 启动

开发（两个进程）：

```bash
python3 -m app.main               # 后端 http://localhost:8788（自动 reload）
cd frontend && npm run dev        # 前端 http://localhost:5174（/api 代理到 8788）
```

生产（单进程）：

```bash
cd frontend && npm run build     # 生成 frontend/dist
RELOAD=0 python3 -m app.main      # FastAPI 托管 dist + API（不 reload）
```

浏览器打开 <http://localhost:8788>。

## 使用流程

1. 点「新增任务」：填任务名称、系统标识（数据库表名，留空用任务名）、目标页面 URL、导出按钮文字、输出目录（留空 = `downloads/名称`）；高级选项里可填登录账号/密码、CSS 选择器、验证码模式。
2. 点「运行全部」（或单条「运行」）→ 后端拉起 Chrome 逐任务执行，控制台实时显示每任务日志。
3. 跑完后弹窗询问是否入库；确认后按「系统标识」动态建表入库——同一系统追加到同一张表（不重复建表），结构相同的 sheet 合并、结构不同的分表。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/status?url=…` | 探测数据库 / 站点在线 |
| GET | `/api/tasks` | 任务列表 |
| POST | `/api/tasks` | 新增任务 |
| PUT | `/api/tasks/{id}` | 更新任务 |
| DELETE | `/api/tasks/{id}` | 删除任务 |
| POST | `/api/run` | 批量执行（NDJSON 流式返回逐任务日志） |
| POST | `/api/import` | 入库（body `{items:[{system,files}]}`） |

## 环境变量（.env）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `HOST` / `PORT` | `127.0.0.1` / `8788` | 后端监听 |
| `DB_HOST` / `DB_PORT` | `127.0.0.1` / `3307` | MySQL 连接 |
| `DB_USER` / `DB_PASS` | `root` / 空 | 入库账号（`DB_PASS` 为空则入库报错） |
| `DB_NAME` | `export_data` | 入库数据库 |
| `TABLE_PREFIX` | 空 | 表名前缀 |

## 测试

```bash
pytest          # 23 个用例：config/tasks/browser 纯函数/import 类型推断/API/流式端点
```

## 手动冒烟

- **浏览器点击**：建一个指向真实导出页的任务，运行后检查 `downloads/` 下是否产出文件（验证登录/验证码/找按钮/抓下载整条链）。
- **入库**：`docker start peptide-mysql-test`（或自备 MySQL）→ 建一个勾选「入库」的任务或直接 `python3 -c "from app.import_data import import_files; print(import_files(['下载文件路径']))"`，验证建表与行数。
