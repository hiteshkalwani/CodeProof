import { describe, expect, it } from 'vitest'
import type { Revision, TestRun } from './api'
import { buildMatrix, humanize } from './matrix'

const run = (results: [string, boolean][], output = ''): TestRun => ({
  id: 1,
  passed: results.every(([, p]) => p) && results.length > 0,
  results: results.map(([name, passed]) => ({ name, passed, error: '' })),
  output,
  timed_out: false,
  duration_ms: 1,
  created_at: '',
})

const revision = (number: number, runs: TestRun[]): Revision => ({
  id: number, number, source: 'generated', code: '', tests: '', feedback: '', model: '',
  prompt_tokens: 0, completion_tokens: 0, created_at: '', runs,
})

describe('buildMatrix', () => {
  it('skips revisions that were never run and uses each revision’s latest run', () => {
    const { tests, rows } = buildMatrix([
      revision(1, []),
      revision(2, [run([['test_a', false]]), run([['test_a', true], ['test_b', false]])]),
      revision(3, [run([['test_a', true], ['test_b', true]])]),
    ])
    expect(tests).toEqual(['test_a', 'test_b'])
    expect(rows.map((r) => r.revision.number)).toEqual([2, 3])
    expect(rows.map((r) => r.cells)).toEqual([['pass', 'fail'], ['pass', 'pass']])
  })

  it('marks tests a revision did not have as missing', () => {
    const { rows } = buildMatrix([revision(1, [run([['test_a', true]])]), revision(2, [run([['test_a', true], ['test_new', true]])])])
    expect(rows[0].cells).toEqual(['pass', 'missing'])
  })

  it('surfaces a run that produced no results', () => {
    const { rows } = buildMatrix([revision(1, [run([], 'SyntaxError: invalid syntax\nmore')])])
    expect(rows[0].error).toBe('SyntaxError: invalid syntax')
  })
})

it('humanizes test names', () => {
  expect(humanize('test_ignores_case')).toBe('ignores case')
  expect(humanize('ignores case')).toBe('ignores case')
})
