# Architecture

## The loop

```
          description
               │
               ▼
   ┌──── generate code (LLM_CODE_MODEL) ─────────────── r1  generated
   │           │
   │           ▼
   │     write tests (LLM_TEST_MODEL) ──── human can revise or edit ── r2  tests_generated
   │           │
   │           ▼
   │      run in sandbox ──► pass ──► done
   │           │
   │          fail: per-test errors
   │           ▼
   └─ repair code (tests are frozen) ─────────────────── r3  repaired   (repeat, up to N attempts)
```

Every arrow that changes code or tests writes a new **Revision**. Revisions are never edited, so the history answers "what did the model change, why, and did it help?" Each revision records the model and the tokens it used.

## Components

| Path | Responsibility |
|---|---|
| `backend/snippets/models.py` | `Snippet` → `Revision` (immutable code + tests) → `TestRun` (per-test results) |
| `backend/snippets/services/workflow.py` | The use cases: create, write tests, improve, edit, run, repair. Views call these and nothing else. |
| `backend/snippets/services/prompts.py` | One function per task. Picks the model per task. |
| `backend/snippets/services/llm.py` | The only module that talks to a provider. Strips code fences and records usage. |
| `backend/snippets/sandbox/` | `executor.py` starts one container per run. `runner.py` / `runner.js` run inside it and report JSON. |
| `backend/snippets/views.py` | DRF viewset: validation, throttling, and mapping domain errors to HTTP in one place. |
| `frontend/src/` | React UI. `matrix.ts` turns revisions into the pass/fail grid. |

## Decisions

**1. The model may change the code, never the tests, during repair.**
This is the main quality rule. If the model could edit tests while fixing failures, it could "pass" by weakening them. Tests change only through an explicit step that a human starts (write tests, revise tests with feedback, or a hand edit), and each of those is its own revision. A person reviews the *specification* (the tests), and the machine iterates on the implementation.

**2. Humans review intent. The loop checks behaviour.**
With most code LLM-generated, reviewers can't read every line with the same care. The UI puts the reviewer's attention where it matters most: whether the tests capture the requirement (feedback goes to *Revise tests*) and whether the result is acceptable (*Revise code*, *Edit*). Mechanical "does it work" checking is automated and recorded.

**3. A bounded repair budget.**
`repair` stops at the first green run or after `max_attempts` (default 3, capped by `MAX_REPAIR_ATTEMPTS`). An unbounded loop would turn a hard problem into a large bill. When the budget runs out, the snippet stays red and a person takes over.

**4. Model per task.**
Writing and repairing code uses `LLM_CODE_MODEL`, and writing tests uses the cheaper `LLM_TEST_MODEL`. Both are chosen in `prompts.py`, so swapping models is a config change, and the token columns show what each choice costs.

**5. Sandbox: one disposable container per run.**
Each run gets a fresh `python:3.12-alpine` or `node:22-alpine` container with no network, a read-only filesystem, the `nobody` user, all capabilities dropped, `no-new-privileges`, 128 MB memory, half a CPU, 64 PIDs and a 10s wall-clock timeout. The container is removed afterwards. Code and tests go in through an environment variable, which is why input is capped at 20,000 characters each. `test_sandbox_docker.py` checks network, filesystem and timeout isolation against real Docker in CI.

*Trade-off:* the API container reaches Docker through `/var/run/docker.sock`, which is root-equivalent on the host. That's acceptable for a single-tenant tool. For multi-tenant production, run sandboxes on a separate host or use gVisor / Firecracker / a hosted sandbox, behind the same `run_tests()` interface.

**6. PostgreSQL first.**
Revisions and runs are relational and append-only. A unique `(snippet, number)` constraint plus a row lock on the snippet keeps revision numbers sequential under concurrent requests. `TestRun.results` is JSON because its shape belongs to the runner, not the schema. SQLite exists only so `make dev-api` works without a database server.

**7. A scripted model (`LLM_PROVIDER=fake`).**
Tests, CI and the demo use a fake provider that answers every prompt with a palindrome checker whose first draft is wrong. The repair loop can then be demonstrated and tested end to end, deterministically, with no key and no cost. The sandbox is real in both cases.

## Known limitations / next steps

- `repair` runs inside the HTTP request (worst case: attempts × (model call + sandbox run)). It's marked `shortcut:` in `views.py`. Next step: a task queue (Celery or RQ, backed by Postgres or Redis) with the UI polling the run.
- No authentication: a single-user tool. Writes are throttled per IP because each one can cost money. The throttle counter is per-process memory, so use a shared cache before scaling out.
- Each run pulls nothing and starts a cold container (~200–300 ms). A warm pool would cut that if runs become frequent.
- Only Python and JavaScript. Another language needs one runner script and one image.
- The scripted model ignores the description. It exists to show and test the loop, not to generate code.
