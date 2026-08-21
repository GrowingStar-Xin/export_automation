import { useEffect, useState } from 'react'
import { fetchStatus } from '../api'

export default function StatusPills({ url }: { url: string }) {
  const [s, setS] = useState({ db: false, site: false })
  useEffect(() => {
    let alive = true
    const tick = () => fetchStatus(url).then(x => { if (alive) setS(x) }).catch(() => {})
    tick()
    const h = setInterval(tick, 15000)
    return () => { alive = false; clearInterval(h) }
  }, [url])
  return (
    <div className="status-group">
      <span className={`status-pill ${s.site ? 'ok' : 'off'}`}><span className="dot" />站点</span>
      <span className={`status-pill ${s.db ? 'ok' : 'off'}`}><span className="dot" />数据库</span>
    </div>
  )
}
