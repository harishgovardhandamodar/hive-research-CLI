import { useEffect, useState } from 'react'
import { StatusCards } from './components/StatusCards'
import { AuditCharts } from './components/AuditCharts'
import { LogsPanel } from './components/LogsPanel'
import { WorkbenchCharts } from './components/WorkbenchCharts'
import { api } from './api'

export default function App() {
  const [tab, setTab] = useState<'research' | 'machine' | 'workbench'>('research')
  const [verify, setVerify] = useState<{ ok: boolean; msg: string } | null>(null)
  const [sessions, setSessions] = useState<[string, string, number][]>([])
  const [workflows, setWorkflows] = useState<{ name: string; path: string }[]>([])
  const [selectedWf, setSelectedWf] = useState<{ name: string; type: string } | null>(null)
  const [wfDetail, setWfDetail] = useState<any>(null)
  const [reports, setReports] = useState<any[]>([])
  const [selectedReport, setSelectedReport] = useState<string | null>(null)
  const [reportContent, setReportContent] = useState<string>('')
  const [researchWfs] = useState<string[]>(['deepresearch','lit','review','audit','replicate','recipe','compare','draft','autoresearch','watch'])
  const [workbenches, setWorkbenches] = useState<any[]>([])
  const [ledger, setLedger] = useState<any[]>([])
  const [learnSt, setLearnSt] = useState<any>(null)
  const [memory, setMemory] = useState<any[]>([])
  const [wbFilter, setWbFilter] = useState<string>('')
  const [unit, setUnit] = useState<'mgdl'|'mmol'>('mgdl')

  useEffect(() => {
    api.verify().then(setVerify).catch(() => setVerify({ ok: false, msg: 'verify failed — DB not yet created (run hive machine ls)' }))
    api.sessions().then(setSessions).catch(() => {})
    api.workflows().then(setWorkflows).catch(() => {})
    api.reports().then(setReports).catch(()=>{})
    api.workbenches().then(setWorkbenches).catch(()=>{})
    api.ledger().then(setLedger).catch(()=>{})
    api.learnStatus().then(setLearnSt).catch(()=>{})
    api.memory().then(setMemory).catch(()=>{})
  }, [])

  useEffect(() => {
    if (!selectedWf) { setWfDetail(null); return }
    api.workflowDetail(selectedWf.name, selectedWf.type).then(setWfDetail).catch(e=> setWfDetail({error: String(e)}))
  }, [selectedWf])

  useEffect(() => {
    if (!selectedReport) { setReportContent(''); return }
    api.report(selectedReport).then(setReportContent).catch(e=> setReportContent('Error: '+String(e)))
  }, [selectedReport])

  const tabBtn = (id: 'research' | 'machine' | 'workbench', label: string) => (
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
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>{tabBtn('research', 'Research Companion')} {tabBtn('machine', 'Hive-Machine')} {tabBtn('workbench', 'AGI Workbench')}</div>
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
                  <div style={{ fontWeight: 600, marginBottom: 6, display: 'flex', gap: 8, alignItems: 'center' }}>Recent sessions (hive sessions) <span style={{ fontSize: 10, opacity: 0.5 }}>{sessions.filter((s:any)=> String(s[1]).startsWith('[legacy]')).length} legacy</span> <button onClick={()=> { api.sessions().then(setSessions).catch(()=>{}); api.reports().then(setReports).catch(()=>{}) }} style={{ marginLeft: 'auto', background: '#0f1320', border: '1px solid #2a3347', color: '#889', borderRadius: 6, padding: '2px 6px', cursor: 'pointer', fontSize: 10 }}>Refresh</button></div>
                  {sessions.length ? (
                    <div style={{ display: 'grid', gap: 6 }}>
                      {sessions.slice(0, 8).map(([id, topic, ts]) => (
                        <div key={id} style={{ display: 'flex', gap: 8, opacity: 0.9, alignItems: 'center' }}>
                          <span style={{ fontFamily: 'monospace', background: String(topic).startsWith('[legacy]') ? '#1a2333' : '#0b0e14', border: `1px solid ${String(topic).startsWith('[legacy]') ? '#2a3347' : '#1f2533'}`, borderRadius: 4, padding: '2px 6px' }}>{id}</span>
                          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{String(topic).replace('[legacy] ', '')}</span>
                          {String(topic).startsWith('[legacy]') ? <span style={{ fontSize: 10, borderRadius: 999, padding: '2px 6px', background: '#1a2333', border: '1px solid #2a3347', opacity: 0.7 }}>legacy</span> : null}
                          <span style={{ opacity: 0.5 }}>{new Date(ts * 1000).toLocaleDateString()}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ opacity: 0.5, lineHeight: 1.5 }}>No sessions yet — run <code>hive report "AI Agents"</code> or <code>hive deepresearch "topic"</code><br/><span style={{ fontSize: 11 }}>Legacy: <code>~/codebase/personal-experiments</code> auto-indexed via <code>HIVE_EXPERIMENTS_DIR</code> • check <code>hive doctor</code> / <code>hive sessions --legacy</code></span></div>
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
        ) : tab === 'machine' ? (
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
        ) : (
          <>
            <section style={{ background: '#0f1320', border: '1px solid #1f2533', borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>AGI Workbench — narrow spaced ideal experimentation</div>
              <div style={{ fontSize: 12, opacity: 0.6, marginBottom: 12 }}>Profiles scope datasets, tools, model, evaluation. Ledger gathers all commands (hash-chained). Learn loop scores & promotes to memory (continual reinforcement). <code>hive workbench | hive ledger | hive learn</code> • auto logs every CLI via <code>main_callback</code>.</div>
              <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 12, fontSize: 12 }}>
                <div style={{ background: '#11151d', borderRadius: 8, padding: 10, border: '1px solid #1f2533', maxHeight: 420, overflowY: 'auto' }}>
                  <div style={{ fontWeight: 600, marginBottom: 8, display: 'flex', gap: 6 }}>Workbenches <span style={{ opacity: 0.5 }}>{workbenches.length}</span> <button onClick={() => { api.workbenches().then(setWorkbenches); api.ledger().then(setLedger); api.learnStatus().then(setLearnSt); api.memory().then(setMemory); }} style={{ marginLeft: 'auto', background: '#0f1320', border: '1px solid #2a3347', color: '#889', borderRadius: 6, padding: '2px 6px', fontSize: 10, cursor: 'pointer' }}>Refresh</button></div>
                  {workbenches.length ? workbenches.map((wb:any) => (
                    <div key={wb.name} onClick={() => { setWbFilter(wb.name); api.ledger(30, wb.name).then(setLedger); api.memory(wb.name).then(setMemory); }} style={{ padding: '6px 8px', borderRadius: 6, cursor: 'pointer', background: wbFilter===wb.name ? '#1e2a44' : 'transparent', border: '1px solid ' + (wbFilter===wb.name ? '#4f8cff' : 'transparent'), marginBottom: 4 }}>
                      <div style={{ fontFamily: 'monospace', fontWeight: 600 }}>{wb.name}</div>
                      <div style={{ opacity: 0.7, fontSize: 11 }}>{wb.description?.slice(0,60)}</div>
                      <div style={{ opacity: 0.5, fontSize: 10 }}>{wb.domain} • {wb.source} • {wb.datasets?.length || 0} datasets</div>
                    </div>
                  )) : <div style={{ opacity: 0.5 }}>No workbenches — builtins auto-seed (fox-fraud, eda-credit, privacy, quai-lora, diabetes)</div>}
                  <div style={{ marginTop: 8, fontSize: 10, opacity: 0.4 }}>CLI: <code>hive workbench list|show|create</code> • <code>HIVE_EXPERIMENTS_DIR</code></div>
                </div>
                <div style={{ display: 'grid', gap: 10 }}>
                  <div style={{ background: '#11151d', borderRadius: 8, padding: 10, border: '1px solid #1f2533' }}>
                    <div style={{ fontWeight: 600, marginBottom: 6, display: 'flex', gap: 6 }}>Ledger — all executions <span style={{ opacity: 0.5 }}>{ledger.length}</span> {wbFilter ? <span style={{ fontSize: 10, opacity: 0.6 }}>filter: {wbFilter} <button onClick={() => { setWbFilter(''); api.ledger().then(setLedger); }} style={{ background: '#0f1320', border: '1px solid #2a3347', borderRadius: 4, padding: '1px 4px', fontSize: 10, cursor: 'pointer' }}>clear</button></span> : null}</div>
                    <div style={{ maxHeight: 180, overflowY: 'auto', display: 'grid', gap: 4 }}>
                      {ledger.length ? ledger.slice(0,12).map((r:any) => (
                        <div key={r.id} style={{ display: 'flex', gap: 6, fontSize: 11, background: '#0b0e14', borderRadius: 6, padding: '6px 8px', border: '1px solid #1f2533' }}>
                          <span style={{ fontFamily: 'monospace', opacity: 0.7 }}>{r.id}</span>
                          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.command}</span>
                          <span style={{ opacity: 0.6 }}>{r.workbench}</span>
                          <span style={{ background: r.reward >=4 ? '#1a2a22' : r.reward ? '#1e2a44' : '#11151d', borderRadius: 4, padding: '1px 6px' }}>{r.reward ?? '-'}</span>
                        </div>
                      )) : <div style={{ opacity: 0.5 }}>No ledger yet — run <code>hive experiment run --workbench fox-fraud --task "test"</code></div>}
                    </div>
                    <div style={{ marginTop: 6, fontSize: 10, opacity: 0.5 }}>Hash-chained • <code>hive ledger --verify</code> • <code>hive feedback &lt;id&gt; --reward 5</code></div>
                  </div>
                  <div style={{ background: '#11151d', borderRadius: 8, padding: 10, border: '1px solid #1f2533' }}>
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>Learn — continual reinforcement loop</div>
                    {learnSt ? (
                      <div style={{ fontSize: 11 }}>
                        <div>Ledger total {learnSt.ledger?.total || 0} • avg reward {learnSt.ledger?.avg_reward?.toFixed?.(2) || '-'} • memory {learnSt.memory?.total || 0}</div>
                        <div style={{ opacity: 0.7, marginTop: 4 }}>By workbench: {(learnSt.ledger?.by_workbench || []).slice(0,3).map((x:any)=> `${x.workbench}:${x.count}(${x.avg_reward?.toFixed(1) || '-'})`).join(' • ') || '-'}</div>
                        <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                          <button onClick={async () => { const r=await fetch('/api/learn/run', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({workbench: wbFilter || 'default', iterations: 10})}); alert(await r.text()); api.learnStatus().then(setLearnSt); api.memory(wbFilter || undefined).then(setMemory); api.ledger(30, wbFilter || undefined).then(setLedger); }} style={{ background: '#1e2a44', border: '1px solid #4f8cff', color: '#e6e8ec', borderRadius: 6, padding: '4px 8px', cursor: 'pointer', fontSize: 11 }}>Run loop (10)</button>
                          <button onClick={async () => { const r=await fetch('/api/learn/run', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({workbench: wbFilter || 'default', iterations: 20, dry: true})}); alert(await r.text()); }} style={{ background: '#0f1320', border: '1px solid #2a3347', color: '#889', borderRadius: 6, padding: '4px 8px', cursor: 'pointer', fontSize: 11 }}>Dry</button>
                        </div>
                        <div style={{ marginTop: 8, maxHeight: 100, overflowY: 'auto' }}>
                          {memory.length ? memory.slice(0,6).map((m:any) => (
                            <div key={m.id} style={{ background: '#0b0e14', borderRadius: 4, padding: '4px 6px', marginBottom: 4, border: '1px solid #1f2533' }}>
                              <span style={{ opacity: 0.6 }}>{m.kind}</span> <span style={{ background: '#1a2a22', borderRadius: 4, padding: '1px 4px', fontSize: 10 }}>{m.score}</span> <span style={{ opacity: 0.8 }}>{m.content?.slice(0,80)}</span>
                            </div>
                          )) : <div style={{ opacity: 0.5 }}>No memory yet — high-reward (≥4) ledger entries promote here</div>}
                        </div>
                      </div>
                    ) : <div style={{ opacity: 0.5 }}>Loading learn status...</div>}
                    <div style={{ marginTop: 6, fontSize: 10, opacity: 0.4 }}>CLI: <code>hive learn status|run|memory --workbench &lt;name&gt;</code> • <code>hive learn rollback</code></div>
                  </div>
                </div>
              </div>
            </section>
            <section style={{ background: '#0f1320', border: '1px solid #1f2533', borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Experiment — narrow AGI run (gathers all)</div>
              <div style={{ fontSize: 11, opacity: 0.6, marginBottom: 8 }}>Quick run in workbench: <code>hive experiment run --workbench {wbFilter || 'fox-fraud'} --task "describe fraud pattern" [--dry]</code>. Every run logs to ledger, can be rated via <code>hive feedback &lt;id&gt; --reward 5</code>, then <code>hive learn run</code> reinforces.</div>
              <div style={{ background: '#11151d', borderRadius: 8, padding: 10, border: '1px solid #1f2533', fontSize: 11 }}>
                <div style={{ background: '#0b0e14', border: '1px solid #4f8cff', borderRadius: 6, padding: '6px 8px', marginBottom: 6 }}>📄 <b>Collected Reports:</b> <a href="/api/report?path=default/reports/narrow_agi_report.md" target="_blank" style={{ color: '#4f8cff' }}>narrow_agi_report.md</a> (2 exp) • <a href="/api/report?path=default/reports/all_experiments_report.md" target="_blank" style={{ color: '#4f8cff' }}>all_experiments_report.md</a> (ALL 50 exp, 14 workbenches, samples) • in Reports → click</div>
                <div>Sources: <code>~/.hive/ledger.db</code> (hash chain) + <code>~/.hive/hive.db</code> (sessions) + <code>~/.hive/machine/audit.db</code> (tools) • Personal-experiments auto-indexed</div>
                <div style={{ marginTop: 8 }}><WorkbenchCharts /></div>
                <div style={{ opacity: 0.6 }}>AGI workbench value: narrow domain + continual data + reinforcement = ideal small AGI (specialized, not general).</div>
              </div>
            </section>
          </>
        )}

        <section style={{ background: '#0f1320', border: '1px solid #1f2533', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Workflows — steps inspector (research + Hive-Machine)</div>
          <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 12, fontSize: 12 }}>
            <div style={{ background: '#11151d', borderRadius: 8, padding: 10, border: '1px solid #1f2533', maxHeight: 380, overflowY: 'auto' }}>
              <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 11, opacity: 0.7 }}>Research Companion (hive report / lit / deepResearch)</div>
              {researchWfs.map(k => (
                <div key={k} onClick={()=> setSelectedWf({name:k, type:'research'})} style={{ padding: '6px 8px', borderRadius: 6, cursor: 'pointer', background: selectedWf?.name===k && selectedWf?.type==='research' ? '#1e2a44' : 'transparent', border: '1px solid ' + (selectedWf?.name===k && selectedWf?.type==='research' ? '#4f8cff' : 'transparent'), marginBottom: 4 }}>
                  <span style={{ fontFamily: 'monospace' }}>{k}</span> <span style={{ opacity: 0.5 }}>research</span>
                </div>
              ))}
              <div style={{ height: 1, background: '#1f2533', margin: '10px 0' }} />
              <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 11, opacity: 0.7 }}>Hive-Machine (local-only • core-workflow)</div>
              {workflows.length ? workflows.map(w => (
                <div key={w.name} onClick={()=> setSelectedWf({name:w.name, type:'machine'})} style={{ padding: '6px 8px', borderRadius: 6, cursor: 'pointer', background: selectedWf?.name===w.name && selectedWf?.type==='machine' ? '#1e2a44' : 'transparent', border: '1px solid ' + (selectedWf?.name===w.name && selectedWf?.type==='machine' ? '#4f8cff' : 'transparent'), marginBottom: 4, display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span style={{ fontFamily: 'monospace', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{w.name}</span>
                  <span style={{ opacity: 0.4, fontSize: 10 }}>{w.path.split('/').pop()}</span>
                </div>
              )) : <div style={{ opacity: 0.5 }}>No machine workflows — run hive machine workflow example</div>}
              <div style={{ marginTop: 10, fontSize: 10, opacity: 0.5 }}>Diabetes: <code>diabetes_management</code> • click to view steps</div>
            </div>
            <div style={{ background: '#11151d', borderRadius: 8, padding: 12, border: '1px solid #1f2533', maxHeight: 380, overflowY: 'auto' }}>
              {!selectedWf ? <div style={{ opacity: 0.5 }}>Select a workflow to view steps</div> : !wfDetail ? <div style={{ opacity: 0.5 }}>Loading {selectedWf.name}…</div> : wfDetail.error ? <div style={{ color: '#ff6b6b' }}>{wfDetail.error}</div> : (
                <div>
                  <div style={{ fontWeight: 700 }}>{wfDetail.name} <span style={{ opacity: 0.5, fontSize: 11 }}>({wfDetail.type})</span> <span style={{ marginLeft: 8, fontSize: 10, border: '1px solid #2a3347', borderRadius: 999, padding: '2px 6px', opacity: 0.7 }}>{wfDetail.access}</span></div>
                  <div style={{ opacity: 0.7, marginBottom: 10 }}>{wfDetail.description}</div>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {wfDetail.steps?.length ? wfDetail.steps.map((s:any, i:number) => (
                      <div key={i} style={{ background: '#0b0e14', borderRadius: 8, padding: 10, border: '1px solid #1f2533' }}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          <span style={{ background: '#1e2a44', borderRadius: 4, padding: '2px 6px', fontFamily: 'monospace', fontSize: 11 }}>{s.id || 'step'+(i+1)}</span>
                          {s.tool ? <span style={{ background: '#132a1e', borderRadius: 4, padding: '2px 6px', fontSize: 11 }}>{s.tool}</span> : null}
                          {s.llm ? <span style={{ background: '#2a1e3a', borderRadius: 4, padding: '2px 6px', fontSize: 11 }}>llm: {s.llm.provider || 'auto'} {s.llm.model || ''}</span> : null}
                          {s.access ? <span style={{ marginLeft: 'auto', fontSize: 10, opacity: 0.6, border: '1px solid #2a3347', borderRadius: 999, padding: '2px 6px' }}>{s.access}</span> : null}
                        </div>
                        {s.args ? <pre style={{ margin: '6px 0 0', fontSize: 11, opacity: 0.8, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{JSON.stringify(s.args, null, 2).slice(0, 800)}</pre> : null}
                        {s.prompt ? <pre style={{ margin: '6px 0 0', fontSize: 11, opacity: 0.8, whiteSpace: 'pre-wrap' }}>{String(s.prompt).slice(0, 1200)}</pre> : null}
                        {s.desc ? <div style={{ marginTop: 6, opacity: 0.7 }}>{s.desc}</div> : null}
                        {s.llm?.prompt ? <pre style={{ marginTop: 6, fontSize: 11, opacity: 0.7, whiteSpace: 'pre-wrap', borderTop: '1px solid #1f2533', paddingTop: 6 }}>{String(s.llm.prompt).slice(0, 1500)}</pre> : null}
                      </div>
                    )) : <div style={{ opacity: 0.5 }}>No steps defined</div>}
                  </div>
                  {wfDetail.prompt_preview ? <div style={{ marginTop: 10 }}><div style={{ fontWeight: 600, fontSize: 11, opacity: 0.7 }}>Prompt preview (research)</div><pre style={{ fontSize: 11, whiteSpace: 'pre-wrap', opacity: 0.7 }}>{wfDetail.prompt_preview.slice(0,3000)}</pre></div> : null}
                  <div style={{ marginTop: 10, fontSize: 10, opacity: 0.5 }}>Tip: trigger via CLI — <code>hive machine workflow run {wfDetail.name}</code> or <code>hive report "{wfDetail.name}"</code> for research</div>
                </div>
              )}
            </div>
          </div>
        </section>

        <section style={{ background: '#0f1320', border: '1px solid #1f2533', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>Generated Reports — timeseries & research (local)
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 4, border: '1px solid #1f2533', borderRadius: 999, padding: 2, background: '#11151d' }}>
              <button onClick={()=> setUnit('mgdl')} style={{ background: unit==='mgdl' ? '#4f8cff' : 'transparent', color: unit==='mgdl' ? '#fff' : '#889', border: 'none', borderRadius: 999, padding: '4px 10px', cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>mg/dL</button>
              <button onClick={()=> setUnit('mmol')} style={{ background: unit==='mmol' ? '#4f8cff' : 'transparent', color: unit==='mmol' ? '#fff' : '#889', border: 'none', borderRadius: 999, padding: '4px 10px', cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>mmol/L</button>
            </span>
            <span style={{ fontSize: 10, opacity: 0.5 }}>÷18.01559</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 12, fontSize: 12 }}>
            <div style={{ background: '#11151d', borderRadius: 8, padding: 10, border: '1px solid #1f2533', maxHeight: 420, overflowY: 'auto' }}>
              <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                <button onClick={()=> api.reports().then(setReports)} style={{ background: '#1e2a44', border: '1px solid #4f8cff', color: '#e6e8ec', borderRadius: 6, padding: '4px 8px', cursor: 'pointer', fontSize: 11 }}>Refresh</button>
                <span style={{ opacity: 0.5, fontSize: 11, alignSelf: 'center' }}>{reports.length} reports</span>
              </div>
              {reports.length ? reports.map((r:any) => (
                <div key={r.full_path} onClick={()=> setSelectedReport(r.path)} style={{ padding: '6px 8px', borderRadius: 6, cursor: 'pointer', background: selectedReport===r.path ? '#1e2a44' : 'transparent', border: '1px solid ' + (selectedReport===r.path ? '#4f8cff' : 'transparent'), marginBottom: 4 }}>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span style={{ fontFamily: 'monospace', fontSize: 11, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.name}</span>
                    <span style={{ fontSize: 10, borderRadius: 999, padding: '2px 6px', background: r.type==='machine' ? '#132a1e' : '#1e2a44', opacity: 0.8 }}>{r.type}</span>
                  </div>
                  <div style={{ opacity: 0.6, fontSize: 10, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.path} • {r.workflow || ''} {r.tier ? '• '+r.tier : ''} • {(r.size/1024).toFixed(1)}KB</div>
                </div>
              )) : <div style={{ opacity: 0.5 }}>No reports yet — run <code>python scripts/diabetes_carelink_report.py --no-llm</code> or <code>hive machine workflow run diabetes_management</code></div>}
              <div style={{ marginTop: 8, fontSize: 10, opacity: 0.4 }}>WS: ~/.hive/machine/workspace/*/reports + output/*.md + ~/.hive/sessions</div>
            </div>
            <div style={{ background: '#11151d', borderRadius: 8, padding: 12, border: '1px solid #1f2533', maxHeight: 420, overflowY: 'auto' }}>
              {!selectedReport ? <div style={{ opacity: 0.5 }}>Select a report to view (MD/JSON/CSV/PNG path). Diabetes Timeseries: click <code>carelink_report.md</code> — use mg/dL ↔ mmol/L toggle above</div> : selectedReport.endsWith('.png') ? (
                <div>
                  <div style={{ fontWeight: 600, marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center' }}>{selectedReport}
                    {selectedReport.includes('carelink') ? <span style={{ fontSize: 10, opacity: 0.6 }}>({unit === 'mmol' ? 'mmol/L' : 'mg/dL'} view — toggle above)</span> : null}
                  </div>
                  {(() => {
                    let imgPath = selectedReport
                    if (unit === 'mmol' && selectedReport.includes('carelink_timeseries.png')) imgPath = selectedReport.replace('carelink_timeseries.png', 'carelink_timeseries_mmol.png')
                    else if (unit === 'mgdl' && selectedReport.includes('carelink_timeseries_mmol.png')) imgPath = selectedReport.replace('carelink_timeseries_mmol.png', 'carelink_timeseries.png')
                    else if (unit === 'mmol' && selectedReport.includes('carelink_daily.png') && !selectedReport.includes('mmol')) imgPath = selectedReport.replace('carelink_daily.png', 'carelink_daily_mmol.png')
                    else if (unit === 'mgdl' && selectedReport.includes('carelink_daily_mmol.png')) imgPath = selectedReport.replace('carelink_daily_mmol.png', 'carelink_daily.png')
                    return <img src={'/api/report?path=' + encodeURIComponent(imgPath)} style={{ maxWidth: '100%', borderRadius: 8, border: '1px solid #1f2533' }} alt={imgPath} onError={(e:any)=>{ if(imgPath!==selectedReport) e.currentTarget.src='/api/report?path='+encodeURIComponent(selectedReport) }} />
                  })()}
                  <div style={{ marginTop: 8, fontSize: 10, opacity: 0.5 }}>Served via /api/report — {unit === 'mmol' ? '1 mmol/L = 18.01559 mg/dL' : '1 mg/dL = 0.0555 mmol/L'} • jailed</div>
                </div>
              ) : (
                <div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ fontWeight: 600, fontFamily: 'monospace' }}>{selectedReport}</span>
                    <button onClick={()=> navigator.clipboard?.writeText(reportContent)} style={{ marginLeft: 'auto', background: '#0b0e14', border: '1px solid #1f2533', color: '#889', borderRadius: 6, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}>Copy</button>
                  </div>
                  <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 11, lineHeight: 1.5, background: '#0b0e14', padding: 10, borderRadius: 8, border: '1px solid #1f2533', maxHeight: 340, overflowY: 'auto' }}>{(() => {
                    if (!reportContent) return 'Loading…'
                    if (unit === 'mgdl' || !selectedReport.includes('carelink')) return reportContent.slice(0,20000)
                    // mmol view: convert mg/dL numbers where mmol not already present
                    // New reports already have both units, so just annotate
                    if (reportContent.includes('mmol/L') && reportContent.includes('mg/dL')) return reportContent.slice(0,20000) + '\n\n[mmol/L view: 1 mmol/L = 18.01559 mg/dL — values above show both units]'
                    // Legacy mg/dL-only: convert on fly
                    return reportContent.slice(0,20000).replace(/(\d+\.?\d*)\s*mg\/dL/g, (_:string, n:string) => {
                      const mmol = (parseFloat(n)/18.01559).toFixed(1)
                      return `${n} mg/dL (${mmol} mmol/L)`
                    })
                  })()}</pre>
                </div>
              )}
            </div>
          </div>
        </section>

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
