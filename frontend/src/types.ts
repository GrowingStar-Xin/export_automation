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
  system: string
  enabled: boolean
  headless: boolean
}

export type TaskInput = Omit<Task, 'id'>

export interface RunSummary {
  total: number
  ok: number
  failed: number
}

export type RunEvent =
  | { type: 'task_start'; task_id: string; name: string; index: number; total: number }
  | { type: 'log'; task_id: string; line: string; level: string }
  | { type: 'task_end'; task_id: string; ok: boolean; files: string[]; system: string; error: string }
  | { type: 'done'; summary: RunSummary }
