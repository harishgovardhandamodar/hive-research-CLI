export type AuditEvent = {
  id: number
  ts: number
  tool: string
  args: string
  result_preview: string
  bytes_out: number
  bytes_in: number
  file_path: string | null
  network_url: string | null
  command: string | null
  severity: number
  impact: number
  sensitivity: string
  tags: string
  prev_hash: string
  hash: string
  workflow_id: string | null
  model: string | null
}

export type Stats = {
  total: [number, number, number]
  by_tool: [string, number, number, number, number, number][]
}

export type ModelInfo = {
  provider: string
  model: string
  url: string
  healthy: boolean
  extra: string
}

export type SessionRow = [string, string, number]

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path)
  if (!r.ok) throw new Error(`${r.status} ${path}`)
  return r.json()
}

export const api = {
  health: () => get<{ ollama: string; lmstudio: string; nvidia: string; openalex: string; arxiv: string }>('/api/health'),
  models: () => get<ModelInfo[]>('/api/models'),
  audit: (limit = 50, minSeverity = 0) => get<AuditEvent[]>(`/api/audit?limit=${limit}&min_severity=${minSeverity}`),
  stats: () => get<Stats>('/api/stats'),
  verify: () => get<{ ok: boolean; msg: string }>('/api/verify'),
  sessions: () => get<SessionRow[]>('/api/sessions'),
  workflows: () => get<{ name: string; path: string }[]>('/api/workflows'),
  files: () => get<{ path: string; type: string; size: number }[]>('/api/files'),
  nvidia: () => get<{ gpu: string; models: ModelInfo[] }>('/api/nvidia'),
}
