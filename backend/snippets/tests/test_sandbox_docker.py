"""The real Docker sandbox. Skipped when Docker is not reachable; CI runs it."""

import docker
import pytest

from snippets.sandbox.executor import run_tests


def docker_available() -> bool:
    try:
        return docker.from_env().ping()
    except docker.errors.DockerException:
        return False


pytestmark = pytest.mark.skipif(not docker_available(), reason="Docker is not reachable")


def test_python_runs_in_container():
    result = run_tests("python", "def add(a, b):\n    return a + b\n", "def test_add():\n    assert add(2, 3) == 5\n")
    assert result.passed, result.output


def test_javascript_runs_in_container():
    result = run_tests("javascript", "const add = (a, b) => a + b", 'test("add", () => assert.strictEqual(add(2, 3), 5))')
    assert result.passed, result.output


def test_no_network():
    code = (
        "import socket\n"
        "def reach():\n"
        "    socket.create_connection(('1.1.1.1', 53), timeout=2)\n"
        "    return True\n"
    )
    result = run_tests("python", code, "def test_network():\n    assert reach()\n")
    assert not result.passed
    assert "OSError" in result.results[0]["error"] or "Network is unreachable" in result.results[0]["error"]


def test_read_only_filesystem():
    code = "def write():\n    open('/tmp/x', 'w').write('x')\n"
    result = run_tests("python", code, "def test_write():\n    write()\n")
    assert not result.passed and "Read-only file system" in result.results[0]["error"]


def test_infinite_loop_is_killed(settings):
    settings.SANDBOX_TIMEOUT_SECONDS = 2
    result = run_tests("python", "def spin():\n    while True:\n        pass\n", "def test_spin():\n    spin()\n")
    assert result.timed_out and not result.passed
