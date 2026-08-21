import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

from playwright.async_api import Page, async_playwright

from .config import resolve_output_dir, settings
from .tasks import Task

# ---------- 纯函数（Task 4） ----------


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


# ---------- 候选定位器 ----------

USERNAME_CANDIDATES = [
    'input[placeholder*="用户名"]', 'input[placeholder*="账号"]', 'input[placeholder*="手机"]',
    'input[placeholder*="邮箱"]', 'input[placeholder*="username"]', 'input[placeholder*="account"]',
    'input[placeholder*="user"]', 'input[name*="username"]', 'input[name*="account"]',
    'input[name*="phone"]', 'input[name*="loginName"]', 'input[type="email"]', 'input[type="text"]',
]
CAPTCHA_INPUT_CANDIDATES = [
    'input[placeholder*="验证码"]', 'input[placeholder*="验证"]',
    'input[placeholder*="captcha"]', 'input[name*="captcha"]', 'input[name*="code"]', 'input[name*="verify"]',
]
CAPTCHA_IMAGE_CANDIDATES = [
    '.captcha-image', 'img[src*="captcha"]', 'img[src*="verify"]', 'img[src*="code"]',
    '.captcha img', '.verify-code img', 'img.captcha', 'svg[class*="captcha"]', 'svg[class*="verify"]',
]
LOGIN_BUTTON_CANDIDATES = [
    'button[type="submit"]', 'input[type="submit"]',
    'button:has-text("登录")', 'button:has-text("登 录")', 'button:has-text("登入")',
    'button:has-text("Login")', 'button:has-text("Sign in")', '[role="button"]:has-text("登录")',
]


async def _first(page: Page, selectors: list[str]):
    for s in selectors:
        el = page.locator(s).first
        if await el.count():
            return el
    return None


async def _find_username(page: Page):
    return await _first(page, USERNAME_CANDIDATES)


async def _find_password(page: Page):
    return page.locator('input[type="password"]').first


async def _find_captcha_input(page: Page):
    return await _first(page, CAPTCHA_INPUT_CANDIDATES)


async def _find_captcha_image(page: Page):
    for s in CAPTCHA_IMAGE_CANDIDATES:
        el = page.locator(s).first
        if await el.count() and await el.is_visible():
            return el
    return None


async def _find_login_button(page: Page):
    for s in LOGIN_BUTTON_CANDIDATES:
        el = page.locator(s).first
        if await el.count() and await el.is_visible():
            return el
    return None


async def _find_export_button(page: Page, task: Task):
    if task.button_selector:
        return page.locator(task.button_selector).first
    text = task.button_text
    if not text:
        return None
    el = page.get_by_role("button", name=text).first
    if await el.count():
        return el
    el = page.locator('button, a, [role="button"], .el-button, [class*="btn"]', has_text=text).first
    if await el.count():
        return el
    el = page.get_by_text(text, exact=False).first
    if await el.count():
        return el
    return None


# ---------- 登录 / 验证码 ----------


async def _solve_captcha(page: Page, cap_input, task: Task, log):
    if cap_input is None:
        return
    img = await _find_captcha_image(page)
    if img is None:
        log("[验证码] 检测到验证码输入框，但未找到验证码图片")
        return
    tag = ""
    try:
        tag = (await img.evaluate("e => e.tagName.toLowerCase()")) or ""
    except Exception:
        pass
    if tag != "img":
        html = ""
        try:
            html = (await img.evaluate("e => e.outerHTML || e.innerHTML")) or ""
        except Exception:
            pass
        code = solve_captcha_svg(html)
        if code:
            log(f"[验证码] 识别 = {code}")
            await cap_input.fill(code)
            return
    if task.captcha_mode == "manual":
        os.makedirs(settings.downloads_root, exist_ok=True)
        p = os.path.join(settings.downloads_root, f"captcha_{int(time.time() * 1000)}.png")
        await img.screenshot(path=p)
        log(f"[验证码] 无法自动识别（图片型），已截图保存: {p}")
    else:
        log("[验证码] 无法自动识别（图片型），尝试直接提交")


async def _do_login(page: Page, task: Task, login_url: str, log):
    log(f"[i] 打开登录页: {login_url}")
    try:
        await page.goto(login_url, wait_until="domcontentloaded")
    except Exception:
        pass
    await page.wait_for_timeout(1200)

    pwd = await _find_password(page)
    if not await pwd.count():
        log("[i] 未发现密码框，判定无需登录，直接进入目标页")
        return
    usr = await _find_username(page)
    if task.username and usr is not None and await usr.count():
        await usr.fill(task.username)
    if task.password:
        await pwd.fill(task.password)

    if task.captcha_mode != "none":
        cap_input = await _find_captcha_input(page)
        await _solve_captcha(page, cap_input, task, log)

    btn = await _find_login_button(page)
    if btn is None:
        log("[!] 未找到登录按钮，尝试直接进入目标页")
        return
    await btn.click()
    await page.wait_for_timeout(2500)

    still_login = bool(re.search(r"login|signin|sign-in|auth", page.url, re.I))
    if not still_login:
        pw = page.locator('input[type="password"]').first
        still_login = bool(await pw.count()) and bool(await pw.is_visible())
    if still_login:
        err = None
        try:
            err = await page.eval_on_selector('.el-message, .login-message, [class*="error"], [class*="alert"]', "e => e.innerText")
        except Exception:
            pass
        log(f"[!] 登录可能失败：{err or '未跳转（请检查账号/密码/验证码）'}")
    else:
        log("[✓] 登录成功")


# ---------- 引擎 ----------


@dataclass
class RunResult:
    ok: bool
    files: list[str] = field(default_factory=list)
    error: str = ""


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
            is_file = ("attachment" in cd.lower()) or any(
                k in ct for k in ("zip", "spreadsheetml", "excel", "csv", "octet-stream", "pdf")
            )
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
            login_url = task.login_url or urljoin(task.url, "/login")
            await _do_login(page, task, login_url, log)

        # 2) 进入目标页
        if page.url != task.url:
            try:
                await page.goto(task.url, wait_until="domcontentloaded")
            except Exception:
                pass
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

        # 4) 等待下载；若有确认弹窗则点击
        await page.wait_for_timeout(1500)
        if not downloaded:
            for s in ['button:has-text("确定")', 'button:has-text("确认")', '.el-message-box button:has-text("确定")']:
                el = page.locator(s).first
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
