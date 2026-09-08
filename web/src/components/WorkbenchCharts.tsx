import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, CartesianGrid, Legend } from 'recharts'
import { api } from '../api'

const COLORS = ['#4f8cff', '#7af0a0', '#ffb86b', '#ff6b6b', '#a78bfa', '#f472b6', '#34d399', '#facc15', '#a78bfa', '#60a5fa']

export function WorkbenchCharts() {
  const [learnSt, setLearnSt] = useState<any>(null)
  const [ledger, setLedger] = useState<any[]>([])
  const [workbenches, setWorkbenches] = useState<any[]>([])
  const [derived, setDerived] = useState<any[]>([])

  const load = () => {
    api.learnStatus().then(setLearnSt).catch(()=>{})
    api.ledger(100).then(setLedger).catch(()=>{})
    api.workbenches().then(setWorkbenches).catch(()=>{})
    api.derived().then(setDerived).catch(()=>{})
  }
  useEffect(() => { load(); const id=setInterval(load, 5000); return ()=>clearInterval(id) }, [])

  if (!learnSt) return <div style={{ opacity: 0.5, fontSize: 12 }}>Loading workbench charts…</div>

  const byWb = (learnSt.ledger?.by_workbench || []).map((x:any)=> ({ name: x.workbench.slice(0,12), count: x.count, reward: x.avg_reward || 0 }))
  const byCmd = (learnSt.ledger?.by_command || []).slice(0,6).map((x:any)=> ({ name: x.command.slice(0,18), count: x.count }))
  const memByWb = (learnSt.memory?.by_workbench || []).map((x:any)=> ({ name: x.workbench.slice(0,12), count: x.count, score: x.avg_score || 0 }))

  // Reward histogram from ledger
  const rewards = [1,2,3,4,5].map(r => ({ reward: String(r), count: ledger.filter((x:any)=> Math.round(x.reward || 0)===r).length }))
  const hasRewards = rewards.some(x=>x.count>0)

  // Scheme data: narrow AGI loop
  const schemeSteps = [
    { step: "Workbench", desc: "fox-fraud, EDA, UPI… (narrow domain)" },
    { step: "Experiment", desc: "hive experiment run --task" },
    { step: "Ledger", desc: "hash-chained executions" },
    { step: "Feedback", desc: "reward 1-5" },
    { step: "Learn loop", desc: "score → promote ≥4 → memory" },
    { step: "Next", desc: "memory biases next run" },
  ]

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      {/* Scheme */}
      <div style={{ background: '#0b0e14', border: '1px solid #1f2533', borderRadius: 8, padding: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 12 }}>Scheme — Narrow Spaced Ideal AGI Loop</div>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap', fontSize: 11 }}>
          {schemeSteps.map((s,i)=> (
            <div key={s.step} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div style={{ background: i===0 ? '#1e2a44' : i===3 ? '#1a2a22' : i===4 ? '#2a1e3a' : '#11151d', border: '1px solid #2a3347', borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
                <div style={{ fontWeight: 700 }}>{s.step}</div>
                <div style={{ opacity: 0.6, fontSize: 10 }}>{s.desc}</div>
              </div>
              {i < schemeSteps.length-1 && <span style={{ opacity: 0.5 }}>→</span>}
            </div>
          ))}
        </div>
        <div style={{ marginTop: 6, fontSize: 10, opacity: 0.5 }}>Auto logs every CLI via <code>main_callback</code> → workbench-scoped → ledger → feedback → learn → memory. Personal-experiments reused as legacy continual data.</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {/* By workbench */}
        <div style={{ background: '#0b0e14', border: '1px solid #1f2533', borderRadius: 8, padding: 12 }}>
          <div style={{ fontWeight: 600, fontSize: 11, marginBottom: 4 }}>Results — Ledger by Workbench (count) — {learnSt.ledger?.total || 0} total</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={byWb.length?byWb:[{name:'empty',count:0}]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2533" />
              <XAxis dataKey="name" tick={{ fill: '#889', fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={40} />
              <YAxis tick={{ fill: '#889', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#0f1320', border: '1px solid #2a3347', fontSize: 11 }} />
              <Bar dataKey="count" fill={COLORS[0]} radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
          <div style={{ fontSize: 10, opacity: 0.5, marginTop: 4 }}>Narrow spaced: each bar = one workbench (fox-fraud, EDA, UPI… 21). Click workbench left to filter ledger.</div>
        </div>

        {/* Avg reward */}
        <div style={{ background: '#0b0e14', border: '1px solid #1f2533', borderRadius: 8, padding: 12 }}>
          <div style={{ fontWeight: 600, fontSize: 11, marginBottom: 4 }}>Results — Avg Reward by Workbench (0-5)</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={byWb}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2533" />
              <XAxis dataKey="name" tick={{ fill: '#889', fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={40} />
              <YAxis domain={[0,5]} tick={{ fill: '#889', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#0f1320', border: '1px solid #2a3347', fontSize: 11 }} />
              <Bar dataKey="reward" fill={COLORS[1]} radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
          <div style={{ fontSize: 10, opacity: 0.5 }}>Reinforcement signal — high ≥4 promotes to memory. Avg {learnSt.ledger?.avg_reward?.toFixed?.(2) || '-'}</div>
        </div>

        {/* Memory */}
        <div style={{ background: '#0b0e14', border: '1px solid #1f2533', borderRadius: 8, padding: 12 }}>
          <div style={{ fontWeight: 600, fontSize: 11, marginBottom: 4 }}>Results — Memory by Workbench (continual learning)</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={memByWb.length?memByWb:[{name:'none',count:0}]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2533" />
              <XAxis dataKey="name" tick={{ fill: '#889', fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={40} />
              <YAxis tick={{ fill: '#889', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#0f1320', border: '1px solid #2a3347', fontSize: 11 }} />
              <Bar dataKey="count" fill={COLORS[2]} radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
          <div style={{ fontSize: 10, opacity: 0.5 }}>{learnSt.memory?.total || 0} reinforced entries (reward≥4) — <code>hive learn run</code> promotes.</div>
        </div>

        {/* Derived per workbench */}
        <div style={{ background: '#0b0e14', border: '1px solid #1f2533', borderRadius: 8, padding: 12 }}>
          <div style={{ fontWeight: 600, fontSize: 11, marginBottom: 4 }}>Derived — Scenarios per Workbench ({derived.length} total)</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={(() => {
              const counts: Record<string, number> = {}
              derived.forEach((d:any)=> counts[d.workbench]=(counts[d.workbench]||0)+1)
              return Object.entries(counts).map(([name,count])=> ({ name: name.slice(0,12), count }))
            })()}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2533" />
              <XAxis dataKey="name" tick={{ fill: '#889', fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={40} />
              <YAxis tick={{ fill: '#889', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#0f1320', border: '1px solid #2a3347', fontSize: 11 }} />
              <Bar dataKey="count" fill={COLORS[3]} radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
          <div style={{ fontSize: 10, opacity: 0.5 }}>Scenarios: robustness, shift, imbalance, privacy, efficiency — help narrow AGI</div>
        </div>

        {/* Command pie */}
        <div style={{ background: '#0b0e14', border: '1px solid #1f2533', borderRadius: 8, padding: 12 }}>
          <div style={{ fontWeight: 600, fontSize: 11, marginBottom: 4 }}>Results — Top Commands (gathered)</div>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie data={byCmd} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={60} label={({name, percent})=> `${name} ${(percent*100).toFixed(0)}%`} fontSize={10}>
                {byCmd.map((_:any,i:number)=><Cell key={i} fill={COLORS[i%COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#0f1320', border: '1px solid #2a3347', fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ fontSize: 10, opacity: 0.5 }}>All CLI + tools: <code>experiment:run, cli:workbench, ledger, learn</code>… auto-logged.</div>
        </div>

        {/* Reward histogram */}
        {hasRewards && (
          <div style={{ background: '#0b0e14', border: '1px solid #1f2533', borderRadius: 8, padding: 12, gridColumn: '1 / -1' }}>
            <div style={{ fontWeight: 600, fontSize: 11, marginBottom: 4 }}>Results — Reward Distribution (1-5, reinforcement)</div>
            <ResponsiveContainer width="100%" height={140}>
              <BarChart data={rewards}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2533" />
                <XAxis dataKey="reward" tick={{ fill: '#889', fontSize: 10 }} />
                <YAxis tick={{ fill: '#889', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#0f1320', border: '1px solid #2a3347', fontSize: 11 }} />
                <Bar dataKey="count" fill={COLORS[4]} radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
            <div style={{ fontSize: 10, opacity: 0.5 }}>Feedback `hive feedback &lt;id&gt; --reward 5` → learn loop. High (4-5) skewed = idealizing.</div>
          </div>
        )}

        {/* Workbench discovery */}
        <div style={{ background: '#0b0e14', border: '1px solid #1f2533', borderRadius: 8, padding: 12, gridColumn: '1 / -1' }}>
          <div style={{ fontWeight: 600, fontSize: 11, marginBottom: 4 }}>Schemes — Workbench Discovery (narrow spaced)</div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', fontSize: 10 }}>
            {workbenches.slice(0,14).map((wb:any)=> (
              <span key={wb.name} style={{ background: '#11151d', border: '1px solid #2a3347', borderRadius: 999, padding: '4px 8px' }}>{wb.name} <span style={{ opacity: 0.5 }}>{wb.source}</span></span>
            ))}
            {workbenches.length>14 && <span style={{ opacity: 0.5 }}>+{workbenches.length-14} more</span>}
          </div>
          <div style={{ fontSize: 10, opacity: 0.5, marginTop: 6 }}>21 narrow profiles: `~/.hive/workbench/*.yaml` (fox-fraud, eda-credit, privacy, quai-lora, diabetes) + auto `personal-experiments/*` (EDA-creditcard-demo, UPI-Peer-identification…). Each scopes datasets/tools/model/evaluation.</div>
        </div>
      </div>
    </div>
  )
}
