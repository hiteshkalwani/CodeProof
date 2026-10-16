"""Execute untrusted, LLM-written code and its tests in a throwaway Docker container."""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import docker
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

MARKER = "__SANDBOX_RESULT__"
MAX_OUTPUT_CHARS = 10_000
_HERE = Path(__file__).parent
COMMANDS = {
    "python": ["python", "-I", "-c", (_HERE / "runner.py").read_text()],
    "javascript": ["node", "-e", (_HERE / "runner.js").read_text()],
}


class SandboxUnavailable(Exception):
    """Docker could not be reached or the container could not start."""


@dataclass
class RunResult:
    passed: bool
    results: list = field(default_factory=list)
    output: str = ""
    timed_out: bool = False
    duration_ms: int = 0


def parse_output(raw: str, *, timed_out: bool, duration_ms: int) -> RunResult:
    """Turn container logs into a result. Anything the code printed is kept as `output`."""
    payload, other_lines = None, []
    for line in raw.splitlines():
        if line.startswith(MARKER):
            payload = json.loads(line[len(MARKER):])
        else:
            other_lines.append(line)
    output = "\n".join(other_lines)[-MAX_OUTPUT_CHARS:]

    if timed_out:
        return RunResult(False, [], f"Timed out after {settings.SANDBOX_TIMEOUT_SECONDS}s.\n{output}".strip(), True, duration_ms)
    if payload is None:
        return RunResult(False, [], output or "The sandbox exited without reporting results.", False, duration_ms)
    if payload.get("load_error"):
        return RunResult(False, [], f"{payload['load_error']}\n{output}".strip(), False, duration_ms)

    results = payload["results"]
    if not results:
        output = (output + "\nNo tests were found.").strip()
    return RunResult(bool(results) and all(r["passed"] for r in results), results, output, False, duration_ms)


def run_tests(language: str, code: str, tests: str) -> RunResult:
    try:
        client = docker.from_env()
        container = client.containers.run(
            settings.SANDBOX_IMAGES[language],
            command=COMMANDS[language],
            environment={"SANDBOX_PAYLOAD": json.dumps({"code": code, "tests": tests})},
            detach=True,
            # Untrusted code: no network, no privileges, read-only FS, nobody user, bounded resources.
            network_disabled=True,
            read_only=True,
            user="65534:65534",
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            mem_limit=settings.SANDBOX_MEMORY,
            memswap_limit=settings.SANDBOX_MEMORY,
            nano_cpus=500_000_000,
            pids_limit=64,
        )
    except docker.errors.DockerException as exc:
        logger.exception("Sandbox container failed to start")
        raise SandboxUnavailable("The test sandbox is unavailable.") from exc

    started = time.monotonic()
    timed_out = False
    try:
        try:
            container.wait(timeout=settings.SANDBOX_TIMEOUT_SECONDS)
        except requests.exceptions.RequestException:
            timed_out = True
            container.kill()
        raw = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
    finally:
        container.remove(force=True)

    return parse_output(raw, timed_out=timed_out, duration_ms=int((time.monotonic() - started) * 1000))
