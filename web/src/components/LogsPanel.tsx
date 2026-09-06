import { useEffect, useState } from 'react'
import { api, AuditEvent } from '../api'

function sevColor(s: number) {
  if (s >= 5) return '#ff4d4d'
  if (s >= 4) return '#ff8c42'
  if (s >= 3) return '#ffb86b'
  if (s >= 2) return '#ffd166'
  return '#7af0a0'
}

export function LogsPanel() {
  const [rows, setRows] = useState<AuditEvent[]>([])
  const [filter, setFilter] = useState<string>('all')
  const [minSev, setMinSev] = useState<number>(0)

  const load = () => api.audit(100, minSev).then(setRows).catch(() => {})

  useEffect(() => {
    load()
    const id = setInterval(load, 3000)
    return () => clearInterval(id)
  }, [minSev])

  const filtered = rows.filter(r => (filter === 'all' ? true : r.tool === filter))

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={filter} onChange={e => setFilter(e.target.value)} style={{ background: '#0f1320', color: '#e6e8ec', border: '1px solid #2a3347', borderRadius: 6, padding: '6px 8px' }}>
          <option value="all">All tools</option>
          <option value="web_fetch">web_fetch</option>
          <option value="web_search">web_search</option>
          <option value="run_bash">run_bash</option>
          <option value="run_python">run_python</option>
          <option value="write_file">write_file</option>
          <option value="read_file">read_file</option>
          <option value="list_files">list_files</option>
          <option value="llm_chat">llm_chat</option>
        </select>
        <select value={String(minSev)} onChange={e => setMinSev(Number(e.target.value))} style={{ background: '#0f1320', color: '#e6e8ec', border: '1px solid #2a3347', borderRadius: 6, padding: '6px 8px' }}>
          <option value="0">Severity ≥0</option>
          <option value="2">≥2 medium</option>
          <option value="3">≥3 high</option>
          <option value="4">≥4 critical</option>
        </select>
        <span style={{ fontSize: 11, opacity: 0.6 }}>{filtered.length} events • hash chain audited • local-first</span>
        <button onClick={load} style={{ marginLeft: 'auto', background: '#1a2333', border: '1px solid #2a3347', color: '#e6e8ec', borderRadius: 6, padding: '6px 10px', cursor: 'pointer' }}>Refresh</button>
      </div>

      <div style={{ overflowX: 'auto', border: '1px solid #1f2533', borderRadius: 8 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ background: '#11151d', textAlign: 'left' }}>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid #1f2533' }}>Time</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid #1f2533' }}>Tool</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid #1f2533' }}>Target</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid #1f2533' }}>Bytes</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid #1f2533' }}>Sev</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid #1f2533' }}>Impact</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid #1f2533' }}>Hash</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid #1f2533' }}>Sensitivity</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => (
              <tr key={r.id} style={{ borderBottom: '1px solid #151a24' }}>
                <td style={{ padding: '7px 10px', opacity: 0.7, whiteSpace: 'nowrap' }}>{new Date(r.ts * 1000).toLocaleTimeString()}</td>
                <td style={{ padding: '7px 10px' }}>
                  <span style={{ background: '#0f1320', border: '1px solid #2a3347', borderRadius: 4, padding: '2px 6px', fontSize: 11 }}>{r.tool}</span>
                </td>
                <td style={{ padding: '7px 10px', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.file_path || r.network_url || r.command || ''}>
                  {r.file_path || r.network_url || (r.command ? r.command.slice(0, 50) : '') || r.tool}
                </td>
                <td style={{ padding: '7px 10px', opacity: 0.8 }}>{r.bytes_out}→{r.bytes_in}</td>
                <td style={{ padding: '7px 10px', color: sevColor(r.severity), fontWeight: 600 }}>{r.severity}</td>
                <td style={{ padding: '7px 10px' }}>
                  <span style={{ background: r.impact > 70 ? '#3a1f1f' : r.impact > 40 ? '#332a1a' : '#1a2a22', borderRadius: 4, padding: '2px 6px' }}>{r.impact}</span>
                </td>
                <td style={{ padding: '7px 10px', fontFamily: 'monospace', fontSize: 11, opacity: 0.7 }}>{r.hash.slice(0, 8)}</td>
                <td style={{ padding: '7px 10px', fontSize: 11, opacity: 0.7 }}>{r.sensitivity}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length === 0 && <div style={{ padding: 12, opacity: 0.5, fontSize: 12 }}>No events for filter — try severity 0 and All tools.</div>}
    </div>
  )
}
