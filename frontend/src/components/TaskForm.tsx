import { useState, type ReactNode } from 'react'
import type { Task, TaskInput } from '../types'

const EMPTY: TaskInput = {
  name: '', url: '', button_text: '', button_selector: '', username: '', password: '',
  login_url: '', captcha_mode: 'auto', output_dir: '', system: '', enabled: true, headless: false,
}

function toInput(t: Task): TaskInput {
  return {
    name: t.name, url: t.url, button_text: t.button_text, button_selector: t.button_selector,
    username: t.username, password: t.password, login_url: t.login_url,
    captcha_mode: t.captcha_mode, output_dir: t.output_dir,
    system: t.system, enabled: t.enabled, headless: t.headless,
  }
}

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  )
}

const ic = {
  edit: <Icon><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" /></Icon>,
  tag: <Icon><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" /><line x1="7" y1="7" x2="7.01" y2="7" /></Icon>,
  link: <Icon><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></Icon>,
  check: <Icon><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></Icon>,
  folder: <Icon><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></Icon>,
  user: <Icon><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></Icon>,
  lock: <Icon><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></Icon>,
  code: <Icon><polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" /></Icon>,
  login: <Icon><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /><polyline points="10 17 15 12 10 7" /><line x1="15" y1="12" x2="3" y2="12" /></Icon>,
  captcha: <Icon><circle cx="12" cy="12" r="3" /><path d="M12 1l9 4-9 4-9-4 9-4z" /></Icon>,
  db: <Icon><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" /></Icon>,
}

function Field({ label, required, hint, icon, children }: {
  label: string
  required?: boolean
  hint?: string
  icon?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="field">
      <label>
        {label}
        {required && <span className="req">*</span>}
        {hint && <span className="hint">{hint}</span>}
      </label>
      <div className="input-wrap">
        {icon && <span className="lead">{icon}</span>}
        {children}
      </div>
    </div>
  )
}

export default function TaskForm({ initial, onSave, onCancel }: {
  initial: Task | null
  onSave: (t: TaskInput) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState<TaskInput>(() => (initial ? toInput(initial) : EMPTY))
  const set = <K extends keyof TaskInput>(k: K, v: TaskInput[K]) => setForm(f => ({ ...f, [k]: v }))

  return (
    <div className="task-form-overlay" onClick={onCancel}>
      <div className="task-form" onClick={e => e.stopPropagation()}>
        <div className="tf-head">
          <div className="tf-title">
            <span className="tf-mark">{ic.edit}</span>
            <h3>{initial ? '编辑任务' : '新增任务'}</h3>
          </div>
          <button className="tf-close" onClick={onCancel} aria-label="关闭">✕</button>
        </div>

        <div className="tf-body">
          <Field label="任务名称" required icon={ic.tag}>
            <input type="text" value={form.name} onChange={e => set('name', e.target.value)} placeholder="例如：客户A日报" />
          </Field>
          <Field label="系统标识" hint="用于数据库表名，留空用任务名" icon={ic.db}>
            <input type="text" value={form.system} onChange={e => set('system', e.target.value)} placeholder="如 customer_a" />
          </Field>
          <Field label="目标页面 URL" required icon={ic.link}>
            <input type="text" value={form.url} onChange={e => set('url', e.target.value)} placeholder="https://…/含导出按钮的页面" />
          </Field>
          <Field label="导出按钮文字" required icon={ic.check}>
            <input type="text" value={form.button_text} onChange={e => set('button_text', e.target.value)} placeholder="按钮上显示的字，如「导出」「下载」" />
          </Field>
          <Field label="输出目录" hint="留空 = downloads/名称" icon={ic.folder}>
            <input type="text" value={form.output_dir} onChange={e => set('output_dir', e.target.value)} placeholder="downloads/客户A" />
          </Field>

          <details className="tf-advanced">
            <summary>登录与高级选项</summary>
            <div className="adv-body">
              <div className="field-row">
                <Field label="用户名" icon={ic.user}>
                  <input type="text" value={form.username} onChange={e => set('username', e.target.value)} placeholder="可选" />
                </Field>
                <Field label="密码" icon={ic.lock}>
                  <input type="password" value={form.password} onChange={e => set('password', e.target.value)} placeholder="可选" />
                </Field>
              </div>
              <Field label="导出按钮 CSS 选择器" hint="优先级最高，留空用按钮文字" icon={ic.code}>
                <input type="text" value={form.button_selector} onChange={e => set('button_selector', e.target.value)} placeholder=".export-btn 或 #download" />
              </Field>
              <Field label="登录页 URL" hint="留空 = 目标页同源 /login" icon={ic.login}>
                <input type="text" value={form.login_url} onChange={e => set('login_url', e.target.value)} placeholder="http://…/login" />
              </Field>
              <Field label="验证码处理" icon={ic.captcha}>
                <select value={form.captcha_mode} onChange={e => set('captcha_mode', e.target.value as TaskInput['captcha_mode'])}>
                  <option value="auto">自动识别（SVG 文字型）</option>
                  <option value="none">无验证码</option>
                  <option value="manual">人工（截图保存）</option>
                </select>
              </Field>
              <div className="checks">
                <label className="check"><input type="checkbox" checked={form.enabled} onChange={e => set('enabled', e.target.checked)} /> 启用（纳入「运行全部」）</label>
              </div>
            </div>
          </details>
        </div>

        <div className="tf-foot">
          <button className="btn-no" onClick={onCancel}>取消</button>
          <button className="btn-ok" onClick={() => onSave(form)}>保存任务</button>
        </div>
      </div>
    </div>
  )
}
