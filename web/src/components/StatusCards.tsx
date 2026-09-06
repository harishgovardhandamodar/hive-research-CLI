import { useEffect, useState } from 'react'

type Health = { ollama: string; lmstudio: string; nvidia: string; openalex: string; arxiv: string }

export function StatusCards() {
  const [h, setH] = useState<Health | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health').then(r => r.json()).then(setH).catch(e => setErr(String(e)))
    const id = setInterval(() => fetch('/api/health').then(r => r.json()).then(setH).catch(() => {}), 8000)
    return () => clearInterval(id)
  }, [])

  if (err) return <div style={{ color: '#ff6b6b', padding: 12 }}>Health error: {err}</div>
  if (!h) return <div style={{ padding: 12, opacity: 0.6 }}>Checking local providers…</div>

  const card = (label: string, value: string) => {
    const isOptional = value.toLowerCase().includes('optional')
    const ok = value.toLowerCase().includes('ok') || value === '200'
    const border = ok ? '#1f6b3a' : isOptional ? '#3a2f1a' : '#6b1f1f'
    const color = ok ? '#7af0a0' : isOptional ? '#ffb86b' : '#ff8e8e'
    const status = ok ? '✓ local-first' : isOptional ? '○ optional (no GPU)' : '✗ unreachable'
    return (
      <div style={{ background: '#151a24', border: `1px solid ${border}`, borderRadius: 10, padding: '12px 14px', minWidth: 160 }}>
        <div style={{ fontSize: 11, opacity: 0.6, letterSpacing: 0.5 }}>{label}</div>
        <div style={{ fontSize: 13, marginTop: 4, color, wordBreak: 'break-all' }}>{value.slice(0, 80)}</div>
        <div style={{ fontSize: 10, marginTop: 6, opacity: 0.5 }}>{status}</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      {card('Ollama', h.ollama)}
      {card('LM Studio', h.lmstudio)}
      {card('Nvidia NIM', h.nvidia)}
      {card('OpenAlex', h.openalex)}
      {card('arXiv', h.arxiv)}
    </div>
  )
}
