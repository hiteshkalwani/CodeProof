"""Runs inside the sandbox container as `python -I -c <this file>`.

Reads {"code", "tests"} from $SANDBOX_PAYLOAD, executes every `test_*` function and prints one
result line prefixed with __SANDBOX_RESULT__. Isolation comes from the container, not from here.
"""
import json
import linecache
import os
import traceback

MARKER = "__SANDBOX_RESULT__"


def emit(**result):
    print(MARKER + json.dumps(result), flush=True)


def load(source, filename, namespace):
    # Register the source so tracebacks can show the failing line.
    linecache.cache[filename] = (len(source), None, source.splitlines(True), filename)
    exec(compile(source, filename, "exec"), namespace)


def describe(exc):
    message = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "tests.py"]
    if frames and frames[-1].line:
        message += f" (line {frames[-1].lineno}: {frames[-1].line.strip()})"
    return message


payload = json.loads(os.environ["SANDBOX_PAYLOAD"])
namespace = {"__name__": "__sandbox__"}
try:
    load(payload["code"], "solution.py", namespace)
    load(payload["tests"], "tests.py", namespace)
except BaseException as exc:  # noqa: BLE001 - any load failure is a result, not a crash
    emit(load_error=describe(exc), results=[])
    raise SystemExit(0) from None

results = []
for name, value in list(namespace.items()):
    if name.startswith("test_") and callable(value):
        try:
            value()
            results.append({"name": name, "passed": True, "error": ""})
        except BaseException as exc:  # noqa: BLE001
            results.append({"name": name, "passed": False, "error": describe(exc)[:500]})
emit(results=results)
