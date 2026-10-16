// Runs inside the sandbox container as `node -e <this file>`.
// Reads {code, tests} from $SANDBOX_PAYLOAD, runs every test("name", fn) and prints one result
// line prefixed with __SANDBOX_RESULT__. `vm` is not a security boundary; the container is.
const assert = require('node:assert')
const vm = require('node:vm')

const MARKER = '__SANDBOX_RESULT__'
const emit = (result) => console.log(MARKER + JSON.stringify(result))
const describe = (e) => `${e && e.name ? e.name : 'Error'}: ${e && e.message ? e.message : e}`.slice(0, 500)

const payload = JSON.parse(process.env.SANDBOX_PAYLOAD)
const tests = []
const context = vm.createContext({ test: (name, fn) => tests.push({ name, fn }), assert, console })

;(async () => {
  try {
    vm.runInContext(`${payload.code}\n${payload.tests}`, context, { filename: 'solution.js' })
  } catch (e) {
    emit({ load_error: describe(e), results: [] })
    return
  }
  const results = []
  for (const t of tests) {
    try {
      await t.fn()
      results.push({ name: t.name, passed: true, error: '' })
    } catch (e) {
      results.push({ name: t.name, passed: false, error: describe(e) })
    }
  }
  emit({ results })
})()
