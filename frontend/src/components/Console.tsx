import type { RunEvent } from '../types'

interface TaskLog {
  id: string
  name: string
  ok?: boolean
  logs: { line: string; level: string }[]
}

export default function Console({ events }: { events: RunEvent[] }) {
  if (!events.length) {
    return <div className="log-empty">等待启动…</div>
  }
  const tasks: TaskLog[] = []
  const index = new Map<string, number>()
  let summary: { total: number; ok: number; failed: number } | null = null

  for (const e of events) {
    if (e.type === 'task_start') {
      index.set(e.task_id, tasks.length)
      tasks.push({ id: e.task_id, name: e.name, logs: [] })
    } else if (e.type === 'log') {
      const i = index.get(e.task_id)
      if (i !== undefined) tasks[i].logs.push({ line: e.line, level: e.level })
    } else if (e.type === 'task_end') {
      const i = index.get(e.task_id)
      if (i !== undefined) tasks[i].ok = e.ok
    } else if (e.type === 'done') {
      summary = e.summary
    }
  }

  return (
    <div className="console">
      {tasks.map(t => (
        <div key={t.id} className="task-log">
          <div className={`task-log-head ${t.ok === true ? 'ok' : t.ok === false ? 'err' : ''}`}>
            <span>{t.name}</span>
            {t.ok === true && <span>✓</span>}
            {t.ok === false && <span>✕</span>}
          </div>
          {t.logs.map((l, i) => (
            <div key={i} className={`log-line ${l.level}`}>{l.line}</div>
          ))}
        </div>
      ))}
      {summary && (
        <div className="summary">完成：{summary.ok} 成功 / {summary.failed} 失败 / 共 {summary.total}</div>
      )}
    </div>
  )
}
