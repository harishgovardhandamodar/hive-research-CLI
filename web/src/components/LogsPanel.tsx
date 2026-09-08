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
  const [selected, setSelected] = useState<AuditEvent | null>(null)

  const load = () => api.audit(500, minSev).then(setRows).catch(() => {})

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

      <div style={{ overflowX: 'auto', overflowY: 'auto', border: '1px solid #1f2533', borderRadius: 8, maxHeight: 420, scrollbarWidth: 'thin' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
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
              <tr key={r.id} onClick={() => setSelected(r)} style={{ borderBottom: '1px solid #151a24', cursor: 'pointer', background: selected?.id === r.id ? '#1a2333' : 'transparent' }} onMouseEnter={e => (e.currentTarget.style.background = '#1a2333')} onMouseLeave={e => (e.currentTarget.style.background = selected?.id === r.id ? '#1a2333' : 'transparent')}>
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
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8, fontSize: 11, opacity: 0.6 }}>
        <span>{filtered.length} / {rows.length} shown • scroll to view all • click row for overlay</span>
        <span style={{ marginLeft: 'auto' }}>maxHeight 420px • sticky header</span>
      </div>
      {filtered.length === 0 && <div style={{ padding: 12, opacity: 0.5, fontSize: 12 }}>No events for filter — try severity 0 and All tools.</div>}

      {selected && (
        <div onClick={() => setSelected(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, padding: 16 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: '#0f1320', border: '1px solid #2a3347', borderRadius: 12, maxWidth: 720, width: '100%', maxHeight: '85vh', overflowY: 'auto', padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <span style={{ background: '#11151d', border: '1px solid #2a3347', borderRadius: 999, padding: '4px 10px', fontSize: 11 }}>{selected.tool}</span>
              <span style={{ color: sevColor(selected.severity), fontWeight: 700, fontSize: 12 }}>Sev {selected.severity}</span>
              <span style={{ background: selected.impact > 70 ? '#3a1f1f' : selected.impact > 40 ? '#332a1a' : '#1a2a22', borderRadius: 999, padding: '4px 10px', fontSize: 11 }}>Impact {selected.impact}</span>
              <span style={{ fontSize: 11, opacity: 0.6 }}>{new Date(selected.ts * 1000).toLocaleString()}</span>
              <button onClick={() => setSelected(null)} style={{ marginLeft: 'auto', background: '#1a2333', border: '1px solid #2a3347', color: '#e6e8ec', borderRadius: 6, padding: '4px 10px', cursor: 'pointer' }}>✕ Close</button>
            </div>

            <div style={{ display: 'grid', gap: 10, fontSize: 12 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8 }}>
                <span style={{ opacity: 0.6 }}>Target</span><span style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{selected.file_path || selected.network_url || selected.command || selected.tool}</span>
                <span style={{ opacity: 0.6 }}>Bytes</span><span>{selected.bytes_out} → {selected.bytes_in} (out → in)</span>
                <span style={{ opacity: 0.6 }}>Sensitivity</span><span>{selected.sensitivity} • {selected.tags}</span>
                <span style={{ opacity: 0.6 }}>Workflow / Model</span><span>{selected.workflow_id || '—'} {selected.model ? '• ' + selected.model : ''}</span>
                <span style={{ opacity: 0.6 }}>Hash</span><span style={{ fontFamily: 'monospace', fontSize: 11, wordBreak: 'break-all' }}>{selected.hash}<br/><span style={{ opacity: 0.5 }}>prev: {selected.prev_hash}</span></span>
              </div>

              <div>
                <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 11, opacity: 0.7 }}>Args (full)</div>
                <pre style={{ background: '#0b0e14', border: '1px solid #1f2533', borderRadius: 8, padding: 10, whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 180, overflowY: 'auto', fontSize: 11 }}>{(() => { try { return JSON.stringify(JSON.parse(selected.args), null, 2) } catch { return selected.args } })()}</pre>
              </div>

              <div>
                <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 11, opacity: 0.7 }}>Result preview</div>
                <pre style={{ background: '#0b0e14', border: '1px solid #1f2533', borderRadius: 8, padding: 10, whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 240, overflowY: 'auto', fontSize: 11 }}>{selected.result_preview || '(empty)'}</pre>
              </div>

              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button onClick={() => { navigator.clipboard?.writeText(JSON.stringify(selected, null, 2)); }} style={{ background: '#11151d', border: '1px solid #2a3347', color: '#e6e8ec', borderRadius: 6, padding: '6px 10px', cursor: 'pointer', fontSize: 11 }}>Copy JSON</button>
                <button onClick={() => { navigator.clipboard?.writeText(selected.result_preview); }} style={{ background: '#11151d', border: '1px solid #2a3347', color: '#e6e8ec', borderRadius: 6, padding: '6px 10px', cursor: 'pointer', fontSize: 11 }}>Copy result</button>
              </div>

              <div style={{ fontSize: 10, opacity: 0.4 }}>Auditable proofs — network, data outflow, files, commands • severity/impact • hash chain • local-first. Click outside to close.</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
