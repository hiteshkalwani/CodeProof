"""The scripts that run inside the sandbox, exercised directly (no Docker)."""

from snippets.tests.conftest import requires_node, run_locally

PY_CODE = "def add(a, b):\n    return a + b\n"


def test_python_reports_each_test():
    result = run_locally("python", PY_CODE, "def test_ok():\n    assert add(1, 2) == 3\n\ndef test_bad():\n    assert add(1, 2) == 4\n")

    assert not result.passed
    assert [r["name"] for r in result.results] == ["test_ok", "test_bad"]
    assert result.results[0]["passed"] and not result.results[1]["passed"]
    assert "line 5: assert add(1, 2) == 4" in result.results[1]["error"]


def test_python_all_green():
    result = run_locally("python", PY_CODE, "def test_ok():\n    assert add(2, 2) == 4\n")
    assert result.passed and result.output == ""


def test_python_syntax_error_is_a_failed_run_not_a_crash():
    result = run_locally("python", "def add(a, b) return a + b", "def test_ok():\n    assert True\n")
    assert not result.passed and result.results == []
    assert "SyntaxError" in result.output


def test_python_no_tests_is_not_a_pass():
    result = run_locally("python", PY_CODE, "x = 1\n")
    assert not result.passed and "No tests were found" in result.output


def test_python_prints_are_kept_as_output():
    result = run_locally("python", PY_CODE, "def test_ok():\n    print('debug!')\n    assert True\n")
    assert result.passed and result.output == "debug!"


@requires_node
def test_javascript_reports_each_test():
    code = "function add(a, b) { return a + b }"
    tests = 'test("ok", () => assert.strictEqual(add(1, 2), 3))\ntest("bad", () => assert.strictEqual(add(1, 2), 4))'
    result = run_locally("javascript", code, tests)

    assert not result.passed
    assert [(r["name"], r["passed"]) for r in result.results] == [("ok", True), ("bad", False)]
    assert "AssertionError" in result.results[1]["error"]


@requires_node
def test_javascript_async_tests_are_awaited():
    code = "async function later(v) { return v }"
    result = run_locally("javascript", code, 'test("async", async () => assert.strictEqual(await later(2), 2))')
    assert result.passed
