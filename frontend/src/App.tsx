import { FormEvent, useCallback, useEffect, useState } from 'react'
import { api, Language, Revision, Snippet, SnippetSummary, Status } from './api'
import { buildMatrix, humanize } from './matrix'

const SOURCE_LABEL: Record<Revision['source'], string> = {
  generated: 'Code generated',
  tests_generated: 'Tests written',
  tests_improved: 'Tests revised from feedback',
  improved: 'Code revised from feedback',
  repaired: 'Code repaired from failing tests',
  edited: 'Edited by hand',
}

const STATUS_LABEL: Record<Status, string> = { passing: 'Tests pass', failing: 'Tests fail', untested: 'Not tested' }

export default function App() {
  const [snippets, setSnippets] = useState<SnippetSummary[]>([])
  const [snippet, setSnippet] = useState<Snippet | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshList = useCallback(() => api.list().then(setSnippets).catch((e: Error) => setError(e.message)), [])
  useEffect(() => {
    void refreshList()
  }, [refreshList])

  // Every action returns the whole snippet, so one helper handles busy state, errors and the list refresh.
  async function act(label: string, call: () => Promise<Snippet | void>) {
    setBusy(label)
    setError(null)
    try {
      const result = await call()
      if (result) setSnippet(result)
      await refreshList()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          CodeProof
        </div>
        <button type="button" className="new-button" onClick={() => setSnippet(null)} aria-pressed={snippet === null}>
          New snippet
        </button>
        <nav aria-label="Snippets">
          <ul className="snippet-list">
            {snippets.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className="snippet-link"
                  aria-current={snippet?.id === s.id ? 'page' : undefined}
                  onClick={() => act('Loading', () => api.get(s.id))}
                >
                  <span className={`dot dot-${s.status}`} title={STATUS_LABEL[s.status]} />
                  <span className="snippet-link-text">{s.description}</span>
                  <span className="lang">{s.language === 'python' ? 'py' : 'js'}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <main className="main">
        {error && (
          <p className="banner" role="alert">
            {error}
          </p>
        )}
        {snippet ? (
          <SnippetView
            key={snippet.id}
            snippet={snippet}
            busy={busy}
            act={act}
            onDelete={() =>
              act('Deleting', async () => {
                await api.remove(snippet.id)
                setSnippet(null)
              })
            }
          />
        ) : (
          <NewSnippet busy={busy} onCreate={(d, l) => act('Generating code', () => api.create(d, l))} />
        )}
      </main>
    </div>
  )
}

function NewSnippet({ busy, onCreate }: { busy: string | null; onCreate: (d: string, l: Language) => void }) {
  const [description, setDescription] = useState('')
  const [language, setLanguage] = useState<Language>('python')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (description.trim()) onCreate(description.trim(), language)
  }

  return (
    <form className="new-form" onSubmit={submit}>
      <h1>Describe a function</h1>
      <p className="lede">
        A model writes the code and its tests. The tests run in an isolated sandbox, and failures go back to the model
        until they pass. Every revision is kept.
      </p>
      <label htmlFor="description">What should it do?</label>
      <textarea
        id="description"
        rows={4}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Check whether a string is a palindrome, ignoring case, spaces and punctuation"
      />
      <div className="form-row">
        <label htmlFor="language">Language</label>
        <select id="language" value={language} onChange={(e) => setLanguage(e.target.value as Language)}>
          <option value="python">Python</option>
          <option value="javascript">JavaScript</option>
        </select>
        <button type="submit" className="primary" disabled={!!busy || !description.trim()}>
          {busy ?? 'Generate code'}
        </button>
      </div>
    </form>
  )
}

interface ViewProps {
  snippet: Snippet
  busy: string | null
  act: (label: string, call: () => Promise<Snippet | void>) => Promise<void>
  onDelete: () => void
}

function SnippetView({ snippet, busy, act, onDelete }: ViewProps) {
  const latest = snippet.revisions[snippet.revisions.length - 1]
  const [selected, setSelected] = useState(latest.number)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({ code: latest.code, tests: latest.tests })
  const [feedback, setFeedback] = useState('')
  const [attempts, setAttempts] = useState(3)

  // A new revision arrived: follow it.
  useEffect(() => {
    setSelected(latest.number)
    setDraft({ code: latest.code, tests: latest.tests })
    setEditing(false)
  }, [latest.number, latest.code, latest.tests])

  const shown = snippet.revisions.find((r) => r.number === selected) ?? latest
  const isLatest = shown.number === latest.number
  const hasTests = latest.tests.trim() !== ''
  const disabled = !!busy
  const run = shown.runs[shown.runs.length - 1]

  return (
    <article className="snippet">
      <header className="snippet-head">
        <div>
          <h1>{snippet.description}</h1>
          <p className="meta">
            <span className={`status status-${snippet.status}`}>{STATUS_LABEL[snippet.status]}</span>
            <span>{snippet.language === 'python' ? 'Python' : 'JavaScript'}</span>
            <span>{snippet.revisions.length} revisions</span>
          </p>
        </div>
        <button type="button" className="quiet" onClick={onDelete} disabled={disabled}>
          Delete
        </button>
      </header>

      <Matrix snippet={snippet} selected={shown.number} onSelect={setSelected} />

      <section className="actions" aria-label="Actions">
        {busy && (
          <p className="working" role="status">
            {busy}…
          </p>
        )}
        <div className="action-row">
          <button type="button" className="primary" disabled={disabled || !hasTests} onClick={() => act('Running tests', () => api.run(snippet.id))}>
            Run tests
          </button>
          <span className="repair">
            <button
              type="button"
              className="primary"
              disabled={disabled || !hasTests || snippet.status === 'passing'}
              onClick={() => act('Repairing until tests pass', () => api.repair(snippet.id, attempts))}
            >
              Repair until tests pass
            </button>
            <label>
              up to
              <select value={attempts} onChange={(e) => setAttempts(Number(e.target.value))} aria-label="Maximum repair attempts">
                {[1, 2, 3].map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
              attempts
            </label>
          </span>
          {!hasTests && (
            <button type="button" className="primary" disabled={disabled} onClick={() => act('Writing tests', () => api.writeTests(snippet.id))}>
              Write tests
            </button>
          )}
        </div>
        <form
          className="feedback-row"
          onSubmit={(e) => {
            e.preventDefault()
            if (feedback.trim()) void act('Revising code', () => api.improve(snippet.id, feedback)).then(() => setFeedback(''))
          }}
        >
          <label htmlFor="feedback" className="visually-hidden">
            Review feedback
          </label>
          <input
            id="feedback"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Review feedback, e.g. “also handle None”"
            autoComplete="off"
          />
          <button type="submit" disabled={disabled || !feedback.trim()}>
            Revise code
          </button>
          <button
            type="button"
            disabled={disabled || !feedback.trim() || !hasTests}
            onClick={() => void act('Revising tests', () => api.writeTests(snippet.id, feedback)).then(() => setFeedback(''))}
          >
            Revise tests
          </button>
        </form>
      </section>

      <section className="panes" aria-label={`Revision ${shown.number}`}>
        <div className="pane-head">
          <h2>
            Revision {shown.number}
            <span className="pane-sub">{SOURCE_LABEL[shown.source]}</span>
          </h2>
          {isLatest &&
            (editing ? (
              <span className="pane-tools">
                <button type="button" className="quiet" onClick={() => setEditing(false)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="primary"
                  disabled={disabled}
                  onClick={() => act('Saving edit', () => api.edit(snippet.id, draft.code, draft.tests))}
                >
                  Save as new revision
                </button>
              </span>
            ) : (
              <button type="button" className="quiet" onClick={() => setEditing(true)} disabled={disabled}>
                Edit
              </button>
            ))}
        </div>
        <div className="pane-grid">
          <CodePane title="Code" value={editing ? draft.code : shown.code} editing={editing} onChange={(code) => setDraft({ ...draft, code })} />
          <CodePane
            title="Tests"
            value={editing ? draft.tests : shown.tests}
            editing={editing}
            onChange={(tests) => setDraft({ ...draft, tests })}
            empty="No tests yet. Write them before running anything."
          />
        </div>
        {run && !run.passed && (
          <div className="failures">
            <h3>{run.timed_out ? 'Timed out' : 'Failures'}</h3>
            <ul>
              {run.results
                .filter((r) => !r.passed)
                .map((r) => (
                  <li key={r.name}>
                    <strong>{humanize(r.name)}</strong> <code>{r.error}</code>
                  </li>
                ))}
            </ul>
            {run.output && <pre>{run.output}</pre>}
          </div>
        )}
      </section>

      <History revisions={snippet.revisions} selected={shown.number} onSelect={setSelected} />
    </article>
  )
}

function Matrix({ snippet, selected, onSelect }: { snippet: Snippet; selected: number; onSelect: (n: number) => void }) {
  const { tests, rows } = buildMatrix(snippet.revisions)
  if (!rows.length) {
    return (
      <p className="matrix-empty">
        {snippet.revisions.some((r) => r.tests) ? 'Run the tests to see results here.' : 'Write tests, then run them to see results here.'}
      </p>
    )
  }
  return (
    <section className="matrix-wrap" aria-label="Test results by revision">
      <table className="matrix">
        <thead>
          <tr>
            <th scope="col">Revision</th>
            {tests.map((t) => (
              <th key={t} scope="col" className="test-col" title={humanize(t)}>
                <span>{humanize(t)}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ revision, cells, error }) => (
            <tr key={revision.number} aria-selected={revision.number === selected} onClick={() => onSelect(revision.number)}>
              <th scope="row">
                <button type="button" className="row-button" onClick={() => onSelect(revision.number)}>
                  r{revision.number}
                  <span>{SOURCE_LABEL[revision.source]}</span>
                </button>
              </th>
              {error ? (
                <td colSpan={Math.max(tests.length, 1)} className="cell-error">
                  {error}
                </td>
              ) : (
                cells.map((cell, i) => (
                  <td key={tests[i]} className={`cell cell-${cell}`}>
                    <span className="visually-hidden">{cell === 'pass' ? 'passed' : cell === 'fail' ? 'failed' : 'not present'}</span>
                  </td>
                ))
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function CodePane(props: { title: string; value: string; editing: boolean; onChange: (v: string) => void; empty?: string }) {
  return (
    <div className="pane">
      <h3>{props.title}</h3>
      {props.editing ? (
        <textarea className="code" value={props.value} onChange={(e) => props.onChange(e.target.value)} spellCheck={false} aria-label={props.title} />
      ) : props.value ? (
        <pre className="code">{props.value}</pre>
      ) : (
        <p className="pane-empty">{props.empty}</p>
      )}
    </div>
  )
}

function History({ revisions, selected, onSelect }: { revisions: Revision[]; selected: number; onSelect: (n: number) => void }) {
  const tokens = revisions.reduce((sum, r) => sum + r.prompt_tokens + r.completion_tokens, 0)
  return (
    <section className="history" aria-label="Revision history">
      <h2>
        History <span className="pane-sub">{tokens.toLocaleString()} tokens across {revisions.filter((r) => r.model).length} model calls</span>
      </h2>
      <ol>
        {[...revisions].reverse().map((r) => {
          const run = r.runs[r.runs.length - 1]
          return (
            <li key={r.number} aria-current={r.number === selected ? 'true' : undefined}>
              <button type="button" className="history-item" onClick={() => onSelect(r.number)}>
                <span className="history-num">r{r.number}</span>
                <span className="history-main">
                  {SOURCE_LABEL[r.source]}
                  {r.feedback && <span className="history-feedback">{r.feedback}</span>}
                </span>
                <span className="history-meta">
                  {r.model ? `${r.model}, ${(r.prompt_tokens + r.completion_tokens).toLocaleString()} tokens` : 'by hand'}
                </span>
                {run && <span className={`status status-${run.passed ? 'passing' : 'failing'}`}>{run.passed ? 'pass' : 'fail'}</span>}
              </button>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
