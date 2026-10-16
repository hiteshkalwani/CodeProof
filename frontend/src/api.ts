export type Language = 'python' | 'javascript'
export type Status = 'passing' | 'failing' | 'untested'

export interface TestResult {
  name: string
  passed: boolean
  error: string
}

export interface TestRun {
  id: number
  passed: boolean
  results: TestResult[]
  output: string
  timed_out: boolean
  duration_ms: number
  created_at: string
}

export interface Revision {
  id: number
  number: number
  source: 'generated' | 'tests_generated' | 'tests_improved' | 'improved' | 'repaired' | 'edited'
  code: string
  tests: string
  feedback: string
  model: string
  prompt_tokens: number
  completion_tokens: number
  created_at: string
  runs: TestRun[]
}

export interface SnippetSummary {
  id: number
  description: string
  language: Language
  status: Status
  updated_at: string
}

export interface Snippet extends SnippetSummary {
  revisions: Revision[]
}

async function request<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json' },
    body: init?.json === undefined ? undefined : JSON.stringify(init.json),
  })
  if (response.status === 204) return undefined as T
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(errorMessage(response.status, data))
  return data as T
}

function errorMessage(status: number, data: Record<string, unknown>): string {
  if (typeof data.detail === 'string') return data.detail
  if (status === 400) return Object.values(data).flat().join(' ') || 'Check the form and try again.'
  return `Request failed (${status}).`
}

export const api = {
  list: () => request<SnippetSummary[]>('/snippets/'),
  get: (id: number) => request<Snippet>(`/snippets/${id}/`),
  create: (description: string, language: Language) =>
    request<Snippet>('/snippets/', { method: 'POST', json: { description, language } }),
  remove: (id: number) => request<void>(`/snippets/${id}/`, { method: 'DELETE' }),
  writeTests: (id: number, feedback = '') => request<Snippet>(`/snippets/${id}/tests/`, { method: 'POST', json: { feedback } }),
  improve: (id: number, feedback: string) => request<Snippet>(`/snippets/${id}/improve/`, { method: 'POST', json: { feedback } }),
  edit: (id: number, code: string, tests: string) =>
    request<Snippet>(`/snippets/${id}/edit/`, { method: 'POST', json: { code, tests } }),
  run: (id: number) => request<Snippet>(`/snippets/${id}/run/`, { method: 'POST' }),
  repair: (id: number, maxAttempts: number) =>
    request<Snippet>(`/snippets/${id}/repair/`, { method: 'POST', json: { max_attempts: maxAttempts } }),
}
