# 通用导出自动化 · 操作台

给任意网站配一个「导出按钮」，一键完成：**浏览器自动登录（可选）→ 点击你指定的按钮 → 抓取下载的文件 →（可选）通用表格入库 MySQL**。不再绑死某个具体站点。

## 目录

- `web/index.html` —— 操作台前端页面（自包含，深色界面，无构建依赖）
- `server.mjs` —— 后端服务（Node 内置 http，托管页面 + 三个接口）
- `auto_export.mjs` —— **通用浏览器自动化**（登录/验证码/找按钮/抓下载，全部自动识别）
- `import_generic.py` —— **通用表格入库**（任意 xlsx/csv/zip，每个 sheet 自动建表 + 类型推断）
- `browser_click_generate.mjs` / `import_orders.py` —— 早期「多肽合成订单」专用版，保留作参考
- `downloads/` —— 抓取到的文件输出目录

## 启动

```bash
cd ~/.openclaw-autoclaw/workspace/peptide-export-automation

# 1) 确保测试 MySQL 已启动（入库时需要）
docker start peptide-mysql-test

# 2) 启动操作台
node server.mjs
```

浏览器打开 <http://localhost:8787>。

## 使用流程

1. 填「目标页面 URL」（含导出按钮的那个页面）。
2. 填「导出按钮文字」——按钮上显示的字，比如「导出」「下载」「生成订单」；或展开「高级选项」直接给 CSS 选择器（优先级最高）。
3. 用户名 / 密码可留空：留空 = 跳过登录，直接进目标页点按钮（适合公开页）。
4. 点「启动自动化」→ 本机弹出 Chrome，自动识别登录框/验证码、点击你指定的按钮、抓取下载。
5. 完成后询问「是否导入数据库」→ 点「是」自动把下载的 xlsx/csv 每个 sheet 建表入库。

## 通用化能力

| 环节 | 说明 |
| --- | --- |
| 登录 | 自动识别用户名框 / 密码框 / 登录按钮；账号密码留空则跳过 |
| 验证码 | 自动识别 SVG 文字型验证码；图片型可切换「人工（截图保存）」 |
| 找按钮 | 按「按钮文字」模糊匹配，或按「CSS 选择器」精确定位 |
| 抓文件 | 监听浏览器下载事件 + 兜底拦截文件型接口响应（zip/xlsx/csv/pdf 等） |
| 入库 | 任意 xlsx/csv/zip，自动识别表头、推断列类型、每个 sheet 建一张表 |

## 接口

- `GET /api/status?url=...` → `{mysql, site}` 探测数据库 / 站点是否在线
- `POST /api/automate` body `{url, username, password, buttonText, buttonSelector, loginUrl, captchaMode, headless}` → 流式日志 + `__RESULT__` 结尾的 `{ok, files[]}`
- `POST /api/import` body `{files: [path, ...]}` → `{ok, log, summary}`

## 环境变量

- 后端：`PORT`（默认 8787）
- 入库：`DB_HOST / DB_PORT / DB_USER / DB_PASS / DB_NAME`、`TABLE_PREFIX`（表名前缀）、`APPEND=1`（追加而非重建表）

## 修改指南

- 改自动化识别逻辑（登录框候选、按钮查找、下载捕获）：`auto_export.mjs`
- 改入库逻辑（表头识别、类型推断、表名规则）：`import_generic.py`
- 改页面文案 / 配色 / 字段：`web/index.html`（样式在 `<style>` 内）
- 改后端接口 / 端口：`server.mjs`

> 注意：通用入库默认「重建表」（同名表先 DROP 再 CREATE，保证干净重导）；设 `APPEND=1` 改为追加。
