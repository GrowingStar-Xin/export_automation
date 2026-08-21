#!/usr/bin/env node
/**
 * 通用导出自动化：模拟真实手动操作
 *   打开目标页 →（可选）自动识别并登录 → 点击用户指定的「导出按钮」→ 抓取下载的文件
 *
 * 环境变量（由 server.mjs 或命令行传入）：
 *   TARGET_URL            目标页面 URL（必填）
 *   BUTTON_TEXT           导出按钮文字（模糊匹配，与 BUTTON_SELECTOR 二选一）
 *   BUTTON_SELECTOR       导出按钮 CSS 选择器（高级，优先级最高）
 *   USERNAME / PASSWORD   登录账号（可选，缺省则跳过登录，直接进入目标页）
 *     —— 内部使用 LOGIN_USER / LOGIN_PASS 环境变量（避免 zsh 的 USERNAME 只读冲突）
 *   LOGIN_URL             登录页 URL（可选，缺省自动从 TARGET_URL 推导 /login）
 *   USERNAME_SELECTOR / PASSWORD_SELECTOR / LOGIN_BUTTON_SELECTOR   高级字段选择器
 *   CAPTCHA_MODE          auto(自动识别 SVG 验证码, 默认) | none(无验证码) | manual(截图人工)
 *   HEADLESS              1 = 无头运行（不弹窗口）
 *
 * 输出约定：
 *   普通日志一行一条；结尾打印一行  __FILES__ ["/abs/path1", ...]  表示抓到的文件列表
 *   退出码：0=成功(≥1个文件) 2=缺目标页 3=未找到按钮 4=未捕获到文件 1=其他错误
 */
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const cfg = {
  targetUrl: (process.env.TARGET_URL || '').trim(),
  loginUrl: (process.env.LOGIN_URL || '').trim(),
  username: process.env.LOGIN_USER || '',
  password: process.env.LOGIN_PASS || '',
  buttonText: (process.env.BUTTON_TEXT || '').trim(),
  buttonSelector: (process.env.BUTTON_SELECTOR || '').trim(),
  usernameSelector: (process.env.USERNAME_SELECTOR || '').trim(),
  passwordSelector: (process.env.PASSWORD_SELECTOR || '').trim(),
  loginButtonSelector: (process.env.LOGIN_BUTTON_SELECTOR || '').trim(),
  captchaMode: (process.env.CAPTCHA_MODE || 'auto').trim(),
  headless: process.env.HEADLESS === '1',
};
const OUT_DIR = path.resolve(process.cwd(), 'downloads');

const log = (m) => console.log(m);

/** 验证码 SVG：提取 <text>/<tspan> 明文，按 x 坐标排序还原阅读顺序 */
function solveCaptchaSvg(svg) {
  const items = [];
  const re = /<(?:text|tspan)\b[^>]*\bx="([\d.]+)"[^>]*>([^<]*)<\/(?:text|tspan)>/gi;
  let m;
  while ((m = re.exec(svg))) items.push({ x: parseFloat(m[1]) || 0, ch: m[2] });
  if (!items.length) {
    const re2 = /<(?:text|tspan)\b[^>]*>([^<]*)<\/(?:text|tspan)>/gi;
    while ((m = re2.exec(svg))) items.push({ x: items.length, ch: m[1] });
  }
  return items.sort((a, b) => a.x - b.x).map((i) => i.ch).join('').trim();
}

/** 通用：探测用户名输入框 */
async function findUsername(page) {
  if (cfg.usernameSelector) return page.locator(cfg.usernameSelector).first();
  const candidates = [
    'input[placeholder*="用户名"]', 'input[placeholder*="账号"]', 'input[placeholder*="手机"]',
    'input[placeholder*="邮箱"]', 'input[placeholder*="username"]', 'input[placeholder*="account"]',
    'input[placeholder*="user"]', 'input[name*="username"]', 'input[name*="account"]',
    'input[name*="phone"]', 'input[name*="loginName"]', 'input[type="email"]', 'input[type="text"]',
  ];
  for (const s of candidates) {
    const el = page.locator(s).first();
    if (await el.count()) return el;
  }
  return null;
}

/** 通用：探测密码输入框 */
async function findPassword(page) {
  if (cfg.passwordSelector) return page.locator(cfg.passwordSelector).first();
  return page.locator('input[type="password"]').first();
}

/** 通用：探测验证码输入框 */
async function findCaptchaInput(page) {
  const candidates = [
    'input[placeholder*="验证码"]', 'input[placeholder*="验证"]',
    'input[placeholder*="captcha"]', 'input[name*="captcha"]', 'input[name*="code"]', 'input[name*="verify"]',
  ];
  for (const s of candidates) {
    const el = page.locator(s).first();
    if (await el.count()) return el;
  }
  return null;
}

/** 通用：探测验证码图片 */
async function findCaptchaImage(page) {
  const candidates = [
    '.captcha-image', 'img[src*="captcha"]', 'img[src*="verify"]', 'img[src*="code"]',
    '.captcha img', '.verify-code img', 'img.captcha', 'svg[class*="captcha"]', 'svg[class*="verify"]',
  ];
  for (const s of candidates) {
    const el = page.locator(s).first();
    if (await el.count() && await el.isVisible().catch(() => false)) return el;
  }
  return null;
}

/** 通用：探测登录按钮 */
async function findLoginButton(page) {
  if (cfg.loginButtonSelector) return page.locator(cfg.loginButtonSelector).first();
  const candidates = [
    'button[type="submit"]', 'input[type="submit"]',
    'button:has-text("登录")', 'button:has-text("登 录")', 'button:has-text("登入")',
    'button:has-text("Login")', 'button:has-text("Sign in")', '[role="button"]:has-text("登录")',
  ];
  for (const s of candidates) {
    const el = page.locator(s).first();
    if (await el.count() && await el.isVisible().catch(() => false)) return el;
  }
  return null;
}

/** 核心：定位用户指定的导出按钮 */
async function findExportButton(page) {
  if (cfg.buttonSelector) return page.locator(cfg.buttonSelector).first();
  const text = cfg.buttonText;
  if (!text) return null;
  let el = page.getByRole('button', { name: text }).first();
  if (await el.count()) return el;
  el = page.locator('button, a, [role="button"], .el-button, [class*="btn"]', { hasText: text }).first();
  if (await el.count()) return el;
  el = page.getByText(text, { exact: false }).first();
  if (await el.count()) return el;
  return null;
}

async function trySolveCaptcha(page, capInput) {
  if (!capInput) return;
  const img = await findCaptchaImage(page);
  if (!img) { log('[验证码] 检测到验证码输入框，但未找到验证码图片'); return; }
  const tag = await img.evaluate((e) => e.tagName.toLowerCase()).catch(() => '');
  // 非 <img>（div/svg 等）：尝试解析 innerHTML 里的 <text>/<tspan> 明文
  if (tag !== 'img') {
    const html = await img.evaluate((e) => e.outerHTML || e.innerHTML).catch(() => '');
    const code = solveCaptchaSvg(html);
    if (code) {
      log(`[验证码] 识别 = ${JSON.stringify(code)}`);
      await capInput.fill(code).catch(() => {});
      return;
    }
  }
  // 图片型验证码
  if (cfg.captchaMode === 'manual') {
    const p = path.join(OUT_DIR, `captcha_${Date.now()}.png`);
    await img.screenshot({ path: p }).catch(() => {});
    log(`[验证码] 无法自动识别（图片型），已截图保存: ${p}`);
  } else {
    log('[验证码] 无法自动识别（图片型），尝试直接提交');
  }
}

async function doLogin(page, loginUrl) {
  log(`[i] 打开登录页: ${loginUrl}`);
  await page.goto(loginUrl, { waitUntil: 'domcontentloaded' }).catch(() => {});
  await page.waitForTimeout(1200);

  const pwd = await findPassword(page);
  if (!(await pwd.count())) {
    log('[i] 未发现密码框，判定无需登录，直接进入目标页');
    return;
  }
  const usr = await findUsername(page);
  if (cfg.username) { if (await usr.count()) await usr.fill(cfg.username).catch(() => {}); }
  if (cfg.password) { await pwd.fill(cfg.password).catch(() => {}); }

  if (cfg.captchaMode !== 'none') {
    const capInput = await findCaptchaInput(page);
    await trySolveCaptcha(page, capInput);
  }

  const btn = await findLoginButton(page);
  if (!(await btn.count())) { log('[!] 未找到登录按钮，尝试直接进入目标页'); return; }
  await btn.click().catch(() => {});
  await page.waitForTimeout(2500);

  // 判断是否仍停留在登录页
  let stillLogin = /login|signin|sign-in|auth/i.test(page.url());
  if (!stillLogin) {
    const pw = page.locator('input[type="password"]').first();
    stillLogin = (await pw.count()) && (await pw.isVisible().catch(() => false));
  }
  if (stillLogin) {
    const err = await page.$eval('.el-message, .login-message, [class*="error"], [class*="alert"]', (e) => e.innerText).catch(() => null);
    log(`[!] 登录可能失败：${err || '未跳转（请检查账号/密码/验证码）'}`);
  } else {
    log('[✓] 登录成功');
  }
}

function guessExt(ct, cd) {
  const m = /filename\*?=(?:UTF-8''|"?)([^";]+)/i.exec(cd) || /filename="?([^";]+)"?/i.exec(cd);
  if (m) { const e = path.extname(m[1]); if (e) return e.slice(1); }
  if (/zip/.test(ct)) return 'zip';
  if (/spreadsheetml|xlsx/.test(ct) || /excel/.test(ct)) return 'xlsx';
  if (/csv/.test(ct)) return 'csv';
  if (/pdf/.test(ct)) return 'pdf';
  return 'bin';
}

function ts() {
  const d = new Date(), p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

async function main() {
  if (!cfg.targetUrl) { log('[!] 未指定目标页面 URL'); process.exit(2); }
  if (!cfg.buttonText && !cfg.buttonSelector) { log('[!] 请指定导出按钮文字或 CSS 选择器'); process.exit(3); }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: cfg.headless });
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();

  // 抓下载（主）
  const downloaded = [];
  page.on('download', async (d) => {
    const p = path.join(OUT_DIR, d.suggestedFilename());
    await d.saveAs(p).catch(() => {});
    if (!downloaded.includes(p)) { downloaded.push(p); log(`[✓] 下载完成: ${p}`); }
  });
  // 兜底：拦截文件型接口响应（content-disposition: attachment 或 文件型 content-type）
  page.on('response', async (res) => {
    const ct = (res.headers()['content-type'] || '').toLowerCase();
    const cd = res.headers()['content-disposition'] || '';
    const isFile = /attachment/i.test(cd) || /(zip|spreadsheetml|excel|csv|octet-stream|pdf|text\/csv)/.test(ct);
    if (res.status() === 200 && isFile) {
      try {
        const buf = await res.body();
        if (buf && buf.length > 0) {
          const p = path.join(OUT_DIR, `download_${ts()}.${guessExt(ct, cd)}`);
          fs.writeFileSync(p, buf);
          if (!downloaded.includes(p)) { downloaded.push(p); log(`[net] 捕获接口文件: ${p}`); }
        }
      } catch {}
    }
  });

  // 1) 登录（可选）
  if (cfg.username || cfg.password) {
    const loginUrl = cfg.loginUrl || (() => { try { return new URL('/login', cfg.targetUrl).href; } catch { return cfg.targetUrl; } })();
    await doLogin(page, loginUrl);
  }

  // 2) 进入目标页
  if (page.url() !== cfg.targetUrl) {
    await page.goto(cfg.targetUrl, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(1500);
  }

  // 3) 定位并点击导出按钮
  const btn = await findExportButton(page);
  if (!btn || !(await btn.count())) {
    log(`[!] 未找到导出按钮（按钮文字="${cfg.buttonText}" 选择器="${cfg.buttonSelector}"），请检查配置`);
    await browser.close(); process.exit(3);
  }
  await btn.scrollIntoViewIfNeeded().catch(() => {});
  await btn.waitFor({ state: 'visible', timeout: 15000 }).catch(() => {});
  log('[i] 已找到导出按钮，点击中…');
  await btn.click().catch(async () => { await btn.click({ force: true }).catch(() => {}); });

  // 4) 等待下载；若弹确认框则尝试点「确定/确认」
  await page.waitForTimeout(1500);
  if (!downloaded.length) {
    for (const s of ['button:has-text("确定")', 'button:has-text("确认")', '.el-message-box button:has-text("确定")']) {
      const el = page.locator(s).first();
      if (await el.count() && await el.isVisible().catch(() => false)) {
        await el.click().catch(() => {});
        log('[i] 已点击确认弹窗');
        break;
      }
    }
  }
  await page.waitForTimeout(4500);

  // 5) 汇总
  if (downloaded.length) {
    downloaded.forEach((f) => log(`[完成] 已产出文件: ${f}`));
  } else {
    log('[!] 未捕获到下载文件，请检查页面是否有报错/弹窗');
  }
  const tip = await page.$eval('.el-message, .el-notification, .ant-message', (e) => e.innerText).catch(() => null);
  if (tip) log(`[提示] ${tip}`);

  console.log('__FILES__ ' + JSON.stringify(downloaded));
  await browser.close();
  process.exit(downloaded.length ? 0 : 4);
}

main().catch((e) => { console.error('失败:', e.message || e); process.exit(1); });
