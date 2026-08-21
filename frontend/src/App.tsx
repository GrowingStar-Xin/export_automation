import { useCallback, useEffect, useState } from 'react'
import { createTask, deleteTask, listTasks, streamRun, updateTask } from './api'
import type { RunEvent, Task, TaskInput } from './types'
import StatusPills from './components/StatusPills'
import TaskList from './components/TaskList'
import TaskForm from './components/TaskForm'
import Console from './components/Console'

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [events, setEvents] = useState<RunEvent[]>([])
  const [editing, setEditing] = useState<Task | null | undefined>(undefined)
  const [running, setRunning] = useState(false)

  const reload = useCallback(() => { listTasks().then(setTasks).catch(() => {}) }, [])
  useEffect(() => { reload() }, [reload])

  const run = async (ids: string[]) => {
    setEvents([])
    setRunning(true)
    try {
      await streamRun(ids, e => setEvents(prev => [...prev, e]))
    } catch (err) {
      setEvents(prev => [...prev, { type: 'log', task_id: '', line: '请求失败：' + (err as Error).message, level: 'err' }])
    } finally {
      setRunning(false)
    }
  }

  const handleSave = async (input: TaskInput) => {
    try {
      if (editing) await updateTask(editing.id, input)
      else await createTask(input)
      setEditing(undefined)
      reload()
    } catch (err) {
      alert('保存失败：' + (err as Error).message)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除该任务？')) return
    await deleteTask(id)
    reload()
  }

  const handleToggle = async (id: string, enabled: boolean) => {
    await updateTask(id, { enabled })
    reload()
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="t1">通用导出自动化 · 操作台</div>
          <div className="t2">Universal Export Console</div>
        </div>
        <StatusPills url={tasks[0]?.url || ''} />
      </header>

      <main>
        <section className="panel">
          <div className="panel-head">
            <span className="panel-title">任务列表</span>
            <div className="panel-actions">
              <button className="ghost" onClick={() => setEditing(null)}>新增任务</button>
              <button className="run-btn" disabled={running || !tasks.length} onClick={() => run([])}>
                {running ? '运行中…' : '运行全部'}
              </button>
            </div>
          </div>
          <TaskList tasks={tasks} onEdit={t => setEditing(t)} onDelete={handleDelete} onRunOne={id => run([id])} onToggle={handleToggle} />
        </section>

        <section className="panel">
          <div className="panel-head"><span className="panel-title">运行日志</span></div>
          <Console events={events} />
        </section>
      </main>

      {editing !== undefined && (
        <TaskForm initial={editing} onSave={handleSave} onCancel={() => setEditing(undefined)} />
      )}
    </div>
  )
}
