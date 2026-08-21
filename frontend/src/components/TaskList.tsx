import type { Task } from '../types'

export default function TaskList({ tasks, onEdit, onDelete, onRunOne, onToggle }: {
  tasks: Task[]
  onEdit: (t: Task) => void
  onDelete: (id: string) => void
  onRunOne: (id: string) => void
  onToggle: (id: string, enabled: boolean) => void
}) {
  if (!tasks.length) {
    return <div className="empty">暂无任务，点击「新增任务」开始</div>
  }
  return (
    <table className="task-table">
      <thead>
        <tr>
          <th>启用</th><th>名称</th><th>系统</th><th>URL</th><th>按钮</th><th>输出目录</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        {tasks.map(t => (
          <tr key={t.id}>
            <td><input type="checkbox" checked={t.enabled} onChange={e => onToggle(t.id, e.target.checked)} /></td>
            <td>{t.name}</td>
            <td>{t.system || '—'}</td>
            <td className="mono">{t.url}</td>
            <td>{t.button_text || t.button_selector}</td>
            <td className="mono">{t.output_dir || 'downloads/' + t.name}</td>
            <td className="ops">
              <button onClick={() => onRunOne(t.id)}>运行</button>
              <button onClick={() => onEdit(t)}>编辑</button>
              <button onClick={() => onDelete(t.id)}>删除</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
