import { useEffect, useState } from 'react'
import { StatusCards } from './components/StatusCards'
import { AuditCharts } from './components/AuditCharts'
import { LogsPanel } from './components/LogsPanel'
import { api } from './api'

export default function App() {
  const [tab, setTab] = useState<'research' | 'machine'>('research')
  const [verify, setVerify] = useState<{ ok: boolean; msg: string } | null>(null)
  const [sessions, setSessions] = useState<[string, string, number][]>([])
  const [workflows, setWorkflows] = useState<{ name: string; path: string }[]>([])

  useEffect(() => {
    api.verify().then(setVerify).catch(() => setVerify({ ok: false, msg: 'verify failed — DB not yet created (run hive machine ls)' }))
    api.sessions().then(setSessions).catch(() => {})
    api.workflows().then(setWorkflows).catch(() => {})
  }, [])

  const tabBtn = (id: 'research' | 'machine', label: string) => (
    <button
      onClick={() => setTab(id)}
      style={{
        background: tab === id ? '#1e2a44' : '#0f1320',
        border: `1px solid ${tab === id ? '#4f8cff' : '#1f2533'}`,
        color: tab === id ? '#e6e8ec' : '#889',
        padding: '8px 14px',
        borderRadius: 8,
        cursor: 'pointer',
        fontWeight: tab === id ? 600 : 400,
      }}
    >
      {label}
    </button>
  )

  return (
    <div style={{ minHeight: '100vh', background: '#0b0e14', color: '#e6e8ec' }}>
      <header style={{ padding: '18px 20px', borderBottom: '1px solid #1f2533', background: '#0f1320', position: 'sticky', top: 0, zIndex: 10 }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <div style={{ fontWeight: 800, fontSize: 18, letterSpacing: 0.3 }}>Hive Research — A Local research companion</div>
          <div style={{ opacity: 0.6, fontSize: 12, border: '1px solid #1f2533', borderRadius: 999, padding: '4px 10px' }}>local-first • Ollama / LM Studio / Nvidia NIM • audited proofs</div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>{tabBtn('research', 'Research Companion')} {tabBtn('machine', 'Hive-Machine')}</div>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: 20, display: 'grid', gap: 18 }}>
        {/* Statuses */}
        <section style={{ background: '#0f1320', border: '1px solid #1f2533', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            Local-first statuses
            <span style={{ fontSize: 11, opacity: 0.6, border: '1px solid #2a3347', borderRadius: 999, padding: '2px 8px' }}>{verify ? (verify.ok ? '✓ chain verified' : '✗ chain') : 'checking…' } {verify?.msg?.slice(0, 60)}</span>
            <span style={{ marginLeft: 'auto', fontSize: 11, opacity: 0.5 }}>DB: ~/.hive/machine/audit.db • hash chain • no egress</span>
          </div>
          <StatusCards />
        </section>

        {tab === 'research' ? (
          <>
            <section style={{ background: '#0f1320', border: '1px solid #1f2533', borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Research Companion — deep analysis</div>
              <div style={{ fontSize: 12, opacity: 0.6, marginBottom: 12 }}>Papers via OpenAlex/arXiv, rank + full-text (Europe PMC), 20-section Feynman report, sessions & artifacts. All via local LLM.</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 12 }}>
                <div style={{ background: '#11151d', borderRadius: 8, padding: 12, border: '1px solid #1f2533' }}>
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>Recent sessions (hive sessions)</div>
                  {sessions.length ? (
                    <div style={{ display: 'grid', gap: 6 }}>
                      {sessions.slice(0, 8).map(([id, topic, ts]) => (
                        <div key={id} style={{ display: 'flex', gap: 8, opacity: 0.9 }}>
                          <span style={{ fontFamily: 'monospace', background: '#0b0e14', borderRadius: 4, padding: '2px 6px' }}>{id}</span>
                          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{topic}</span>
                          <span style={{ opacity: 0.5 }}>{new Date(ts * 1000).toLocaleDateString()}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ opacity: 0.5 }}>No sessions yet — run <code>hive report "AI Agents"</code></div>
                  )}
                </div>
                <div style={{ background: '#11151d', borderRadius: 8, padding: 12, border: '1px solid #1f2533' }}>
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>Workflows (hive machine workflow)</div>
                  {workflows.length ? (
                    <div style={{ display: 'grid', gap: 6 }}>
                      {workflows.slice(0, 8).map(w => (
                        <div key={w.name} style={{ display: 'flex', gap: 8 }}>
                          <span style={{ background: '#0b0e14', borderRadius: 4, padding: '2px 6px', fontFamily: 'monospace' }}>{w.name}</span>
                          <span style={{ opacity: 0.6, fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis' }}>{w.path}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ opacity: 0.5 }}>No workflows — run <code>hive machine workflow example</code></div>
                  )}
                </div>
              </div>
            </section>

            <section style={{ background: '#0f1320', border: '1px solid #1f2533', borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Audit charts — Research + Machine (shared ledger)</div>
              <AuditCharts />
            </section>
          </>
        ) : (
          <>
            <section style={{ background: '#0f1320', border: '1px solid #1f2533', borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Hive-Machine — local Perplexity Computer</div>
              <div style={{ fontSize: 12, opacity: 0.6, marginBottom: 12 }}>Sandbox <code>~/.hive/machine/workspace</code> (jailed), tools: <code>list_files/read_file/write_file/run_bash/run_python/web_fetch/web_search</code>, Nvidia-PAIR routing, sensitive-data detection (severity), history DB.</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ background: '#11151d', border: '1px solid #1f2533', borderRadius: 999, padding: '6px 10px', fontSize: 12 }}>Workspace: ~/.hive/machine/workspace</span>
                <span style={{ background: '#11151d', border: '1px solid #1f2533', borderRadius: 999, padding: '6px 10px', fontSize: 12 }}>History: ~/.hive/machine/machine.db</span>
                <span style={{ background: '#11151d', border: '1px solid #1f2533', borderRadius: 999, padding: '6px 10px', fontSize: 12 }}>Audit: ~/.hive/machine/audit.db (hash chain)</span>
              </div>
            </section>

            <section style={{ background: '#0f1320', border: '1px solid #1f2533', borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Impact & severity — analysis dashboards</div>
              <AuditCharts />
            </section>
          </>
        )}

        <section style={{ background: '#0f1320', border: '1px solid #1f2533', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Logs — auditable proofs (network, data outflow, files, commands)</div>
          <div style={{ fontSize: 11, opacity: 0.6, marginBottom: 10 }}>Every tool: <code>bytes_out/in</code> • file_path • network_url • command • <code>severity 1-5</code> (low→critical) • <code>impact 0-100</code> • sensitivity • <code>hash/prev_hash</code> chain. Local-first, no egress.</div>
          <LogsPanel />
        </section>

        <section style={{ background: '#0f1320', border: '1px solid #1f2533', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 12, opacity: 0.7 }}>
            CLI: <code>hive machine ls/read/write/exec/fetch/search</code> • <code>hive machine workflow run &lt;name&gt;</code> • <code>hive dashboard</code> • <code>hive machine audit --verify</code> • <code>hive machine nvidia</code> • Web: <code>hive serve --web</code> (this dashboard on <code>http://localhost:8000</code>)
          </div>
        </section>
      </main>

      <footer style={{ padding: '14px 20px', textAlign: 'center', opacity: 0.5, fontSize: 11, borderTop: '1px solid #1f2533', marginTop: 20 }}>
        Hive Research - A Local research companion • Hive-Machine • local-first • Ollama / LM Studio / Nvidia NIM • audit hash chain • <code>~/.hive</code>
      </footer>
    </div>
  )
}
