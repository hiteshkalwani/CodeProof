import type { Revision } from './api'

export type Cell = 'pass' | 'fail' | 'missing'

export interface MatrixRow {
  revision: Revision
  cells: Cell[]
  error?: string // the run produced no per-test results (syntax error, timeout, ...)
}

/** Rows: every revision that has been run (its latest run). Columns: every test name seen, in first-seen order. */
export function buildMatrix(revisions: Revision[]): { tests: string[]; rows: MatrixRow[] } {
  const tests: string[] = []
  const ran = revisions.filter((r) => r.runs.length > 0)
  for (const revision of ran) {
    for (const result of revision.runs[revision.runs.length - 1].results) {
      if (!tests.includes(result.name)) tests.push(result.name)
    }
  }
  const rows = ran.map((revision) => {
    const run = revision.runs[revision.runs.length - 1]
    const byName = new Map(run.results.map((r) => [r.name, r.passed]))
    const cells = tests.map<Cell>((name) => (byName.has(name) ? (byName.get(name) ? 'pass' : 'fail') : 'missing'))
    return run.results.length ? { revision, cells } : { revision, cells, error: run.output.split('\n')[0] }
  })
  return { tests, rows }
}

/** "test_ignores_case" -> "ignores case" */
export function humanize(testName: string): string {
  return testName.replace(/^test_/, '').replace(/_/g, ' ')
}
