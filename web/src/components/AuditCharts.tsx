import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, CartesianGrid, Legend } from 'recharts'
import { api, AuditEvent } from '../api'

const COLORS = ['#4f8cff', '#7af0a0', '#ffb86b', '#ff6b6b', '#a78bfa']

export function AuditCharts() {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [stats, setStats] = useState<any>(null)

  useEffect(() => {
    api.audit(200).then(setEvents).catch(() => {})
    api.stats().then(setStats).catch(() => {})
    const id = setInterval(() => {
      api.audit(200).then(setEvents).catch(() => {})
      api.stats().then(setStats).catch(() => {})
    }, 5000)
    return () => clearInterval(id)
  }, [])

  if (!events.length) return <div style={{ padding: 16, opacity: 0.6 }}>No audit events yet — run <code>hive machine ls</code> or <code>hive rank</code> to generate proofs.</div>

  // severity distribution
  const sevCount = [1, 2, 3, 4, 5].map(s => ({ name: `sev ${s}`, value: events.filter(e => e.severity === s).length }))
  // tool counts
  const toolMap: Record<string, number> = {}
  events.forEach(e => (toolMap[e.tool] = (toolMap[e.tool] || 0) + 1))
  const toolData = Object.entries(toolMap).map(([name, value]) => ({ name, value }))
  // impact over time (last 30)
  const timeline = events.slice(0, 30).reverse().map((e, i) => ({
    t: new Date(e.ts * 1000).toLocaleTimeString(),
    impact: e.impact,
    severity: e.severity,
    bytes: e.bytes_out + e.bytes_in,
  }))
  // network vs file vs command
  const net = events.filter(e => e.tool === 'web_fetch' || e.tool === 'web_search').length
  const files = events.filter(e => ['list_files', 'read_file', 'write_file', 'delete_path'].includes(e.tool)).length
  const cmds = events.filter(e => ['run_bash', 'run_python'].includes(e.tool)).length
  const catData = [
    { name: 'Network', value: net },
    { name: 'Files', value: files },
    { name: 'Commands', value: cmds },
    { name: 'LLM', value: events.filter(e => e.tool === 'llm_chat').length },
  ].filter(d => d.value > 0)

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div style={{ background: '#11151d', borderRadius: 10, padding: 12, border: '1px solid #1f2533' }}>
        <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>Severity distribution (audited, 1=low →5=critical)</div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={sevCount}>
            <XAxis dataKey="name" tick={{ fill: '#889', fontSize: 11 }} />
            <YAxis tick={{ fill: '#889', fontSize: 11 }} />
            <Tooltip contentStyle={{ background: '#0f1320', border: '1px solid #2a3347' }} />
            <Bar dataKey="value" fill="#4f8cff" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div style={{ background: '#11151d', borderRadius: 10, padding: 12, border: '1px solid #1f2533' }}>
        <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>Tool usage (proofs)</div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={toolData}>
            <XAxis dataKey="name" tick={{ fill: '#889', fontSize: 10 }} interval={0} angle={-15} dy={10} height={40} />
            <YAxis tick={{ fill: '#889', fontSize: 11 }} />
            <Tooltip contentStyle={{ background: '#0f1320', border: '1px solid #2a3347' }} />
            <Bar dataKey="value" fill="#7af0a0" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div style={{ background: '#11151d', borderRadius: 10, padding: 12, border: '1px solid #1f2533' }}>
        <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>Impact over time (0-100, last 30 events)</div>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={timeline}>
            <CartesianGrid stroke="#1f2533" strokeDasharray="3 3" />
            <XAxis dataKey="t" tick={{ fill: '#667', fontSize: 9 }} interval={4} />
            <YAxis tick={{ fill: '#889', fontSize: 11 }} domain={[0, 100]} />
            <Tooltip contentStyle={{ background: '#0f1320', border: '1px solid #2a3347' }} />
            <Legend />
            <Line type="monotone" dataKey="impact" stroke="#ffb86b" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="severity" stroke="#4f8cff" strokeWidth={1} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div style={{ background: '#11151d', borderRadius: 10, padding: 12, border: '1px solid #1f2533' }}>
        <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>Category breakdown (network / files / commands / LLM)</div>
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie data={catData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, value }) => `${name}:${value}`}>
              {catData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={{ background: '#0f1320', border: '1px solid #2a3347' }} />
          </PieChart>
        </ResponsiveContainer>
        {stats && (
          <div style={{ fontSize: 11, opacity: 0.6, marginTop: 6 }}>
            Total events: {stats.total[0]} • Bytes out: {stats.total[1] ?? 0} • In: {stats.total[2] ?? 0}
          </div>
        )}
      </div>
    </div>
  )
}
