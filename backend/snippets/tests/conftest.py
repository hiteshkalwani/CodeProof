import json
import os
import shutil
import subprocess
import time

import pytest
from rest_framework.test import APIClient

from snippets.sandbox import executor


def run_locally(language: str, code: str, tests: str) -> executor.RunResult:
    """Run the real sandbox runner script in a subprocess. Test-only: no isolation at all."""
    started = time.monotonic()
    env = {**os.environ, "SANDBOX_PAYLOAD": json.dumps({"code": code, "tests": tests})}
    try:
        proc = subprocess.run(executor.COMMANDS[language], env=env, capture_output=True, text=True, timeout=10)
        raw, timed_out = proc.stdout + proc.stderr, False
    except subprocess.TimeoutExpired:
        raw, timed_out = "", True
    return executor.parse_output(raw, timed_out=timed_out, duration_ms=int((time.monotonic() - started) * 1000))


@pytest.fixture
def local_sandbox(monkeypatch):
    monkeypatch.setattr(executor, "run_tests", run_locally)


@pytest.fixture
def api():
    return APIClient()


requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
