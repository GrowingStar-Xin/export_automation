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

export interface ImportItem {
  system: string
  files: string[]
}

export async function importFiles(items: ImportItem[]): Promise<{ ok: boolean; error?: string; results?: unknown[] }> {
  const r = await fetch('/api/import', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ items }) })
  return r.json()
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
