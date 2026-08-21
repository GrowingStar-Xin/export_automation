import { useState } from 'react'
import type { Task, TaskInput } from '../types'

const EMPTY: TaskInput = {
  name: '', url: '', button_text: '', button_selector: '', username: '', password: '',
  login_url: '', captcha_mode: 'auto', output_dir: '', import_after: false, enabled: true, headless: false,
}

function toInput(t: Task): TaskInput {
  return {
    name: t.name, url: t.url, button_text: t.button_text, button_selector: t.button_selector,
    username: t.username, password: t.password, login_url: t.login_url,
    captcha_mode: t.captcha_mode, output_dir: t.output_dir,
    import_after: t.import_after, enabled: t.enabled, headless: t.headless,
  }
}

export default function TaskForm({ initial, onSave, onCancel }: {
  initial: Task | null
  onSave: (t: TaskInput) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState<TaskInput>(() => (initial ? toInput(initial) : EMPTY))
  const set = <K extends keyof TaskInput>(k: K, v: TaskInput[K]) => setForm(f => ({ ...f, [k]: v }))

  return (
    <div className="task-form-overlay">
      <div className="task-form">
        <h3>{initial ? '编辑任务' : '新增任务'}</h3>
        <label>任务名称 *<input value={form.name} onChange={e => set('name', e.target.value)} placeholder="客户A日报" /></label>
        <label>目标页面 URL *<input value={form.url} onChange={e => set('url', e.target.value)} placeholder="https://…/report" /></label>
        <label>导出按钮文字 *<input value={form.button_text} onChange={e => set('button_text', e.target.value)} placeholder="导出 / 下载 / 生成订单" /></label>
        <label>输出目录（留空 = downloads/名称）<input value={form.output_dir} onChange={e => set('output_dir', e.target.value)} placeholder="downloads/客户A" /></label>
        <details>
          <summary>登录与高级选项</summary>
          <label>用户名<input value={form.username} onChange={e => set('username', e.target.value)} /></label>
          <label>密码<input type="password" value={form.password} onChange={e => set('password', e.target.value)} /></label>
          <label>CSS 选择器（优先级最高）<input value={form.button_selector} onChange={e => set('button_selector', e.target.value)} placeholder=".export-btn" /></label>
          <label>登录页 URL<input value={form.login_url} onChange={e => set('login_url', e.target.value)} /></label>
          <label>验证码处理
            <select value={form.captcha_mode} onChange={e => set('captcha_mode', e.target.value as TaskInput['captcha_mode'])}>
              <option value="auto">自动识别（SVG 文字型）</option>
              <option value="none">无验证码</option>
              <option value="manual">人工（截图保存）</option>
            </select>
          </label>
          <label className="check"><input type="checkbox" checked={form.import_after} onChange={e => set('import_after', e.target.checked)} /> 下载后入库</label>
          <label className="check"><input type="checkbox" checked={form.enabled} onChange={e => set('enabled', e.target.checked)} /> 启用（纳入「运行全部」）</label>
        </details>
        <div className="form-actions">
          <button className="btn-ok" onClick={() => onSave(form)}>保存</button>
          <button className="btn-no" onClick={onCancel}>取消</button>
        </div>
      </div>
    </div>
  )
}
