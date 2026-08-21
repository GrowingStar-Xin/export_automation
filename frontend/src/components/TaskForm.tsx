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
    <div className="task-form-overlay" onClick={onCancel}>
      <div className="task-form" onClick={e => e.stopPropagation()}>
        <div className="tf-head">
          <h3>{initial ? '编辑任务' : '新增任务'}</h3>
          <button className="tf-close" onClick={onCancel} aria-label="关闭">✕</button>
        </div>

        <div className="tf-body">
          <div className="field">
            <label>任务名称 <span className="req">*</span></label>
            <input value={form.name} onChange={e => set('name', e.target.value)} placeholder="例如：客户A日报" />
          </div>
          <div className="field">
            <label>目标页面 URL <span className="req">*</span></label>
            <input value={form.url} onChange={e => set('url', e.target.value)} placeholder="https://…/含导出按钮的页面" />
          </div>
          <div className="field">
            <label>导出按钮文字 <span className="req">*</span></label>
            <input value={form.button_text} onChange={e => set('button_text', e.target.value)} placeholder="按钮上显示的字，如「导出」「下载」" />
          </div>
          <div className="field">
            <label>输出目录 <span className="hint">留空 = downloads/名称</span></label>
            <input value={form.output_dir} onChange={e => set('output_dir', e.target.value)} placeholder="downloads/客户A" />
          </div>

          <details className="tf-advanced">
            <summary>登录与高级选项</summary>
            <div className="adv-body">
              <div className="field-row">
                <div className="field">
                  <label>用户名</label>
                  <input value={form.username} onChange={e => set('username', e.target.value)} placeholder="可选" />
                </div>
                <div className="field">
                  <label>密码</label>
                  <input type="password" value={form.password} onChange={e => set('password', e.target.value)} placeholder="可选" />
                </div>
              </div>
              <div className="field">
                <label>导出按钮 CSS 选择器 <span className="hint">优先级最高，留空用按钮文字</span></label>
                <input value={form.button_selector} onChange={e => set('button_selector', e.target.value)} placeholder=".export-btn 或 #download" />
              </div>
              <div className="field">
                <label>登录页 URL <span className="hint">留空 = 目标页同源 /login</span></label>
                <input value={form.login_url} onChange={e => set('login_url', e.target.value)} placeholder="http://…/login" />
              </div>
              <div className="field">
                <label>验证码处理</label>
                <select value={form.captcha_mode} onChange={e => set('captcha_mode', e.target.value as TaskInput['captcha_mode'])}>
                  <option value="auto">自动识别（SVG 文字型）</option>
                  <option value="none">无验证码</option>
                  <option value="manual">人工（截图保存）</option>
                </select>
              </div>
              <div className="checks">
                <label className="check"><input type="checkbox" checked={form.import_after} onChange={e => set('import_after', e.target.checked)} /> 下载后入库</label>
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
