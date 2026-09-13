# Bug-Fix Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the correctness and robustness bugs found in a full-repo audit of `faraday/`, `agents/`, and `evals/`, without changing any documented, intentional behavior.

**Architecture:** Eight small, independent bug fixes across the orchestrator (`runner.py`, `worker.py`), the grading layer (`deterministic.py`), the BYO-eval installer (`evals_io.py`), the queue client (`queue.py`), and one stale doc. Each fix follows red/green TDD: a failing test that reproduces the bug, then the minimal code change that makes it pass.

**Tech Stack:** Python 3.12, pytest, docker-py, SQLAlchemy (SQLite in tests via `tests/conftest.py`), Redis.

**Spec:** No separate spec document — the findings below come from a manual code audit plus an independent `code-review` agent pass over the repo on 2026-09-12 (session transcript). Every finding was verified by reading the actual source before being added here.

## Global Constraints

- Every task must leave `pytest -m "not docker" -q` fully green (129+ tests passing) before it is committed.
- Run `ruff check faraday/ tests/ agents/` clean before each commit (matches `.github/workflows/ci.yml`).
- No behavior change beyond the specific bug being fixed — do not refactor unrelated code.
- Follow existing test conventions: unit-test the smallest testable seam (a private method, a module-level helper), the same way `tests/test_runner_agent_env.py` tests `_start_agent`/`_start_task_env` directly via `object.__new__(LocalRunner)` instead of calling `LocalRunner.run()` (which needs a live Docker daemon and is only exercised by `tests/test_e2e_docker.py`).
- Commit once per task, in order, with the message given in that task's last step.

---

## File Structure

| File | Change |
|---|---|
| `faraday/orchestrator/runner.py` | Add `_grader_context` (method), `_grade_safely`, `_wait_for_agent` (module functions); rewire `LocalRunner.run()` to use them |
| `faraday/grading/deterministic.py` | `JsonFieldGrader_`: block bool/int cross-type equality |
| `faraday/orchestrator/worker.py` | `process_job` / `main`: never let one bad job kill the poll loop |
| `faraday/evals_io.py` | `_safe_extract`: cap total uncompressed size (zip-bomb guard) |
| `faraday/queue.py` | `connection()`: reuse one Redis client instead of one per call |
| `docs/DECISIONS.md` | Refresh the stale "What's next" section |
| `tests/test_runner_grading.py` | **New.** Tasks 1 and 3 |
| `tests/test_runner_wait.py` | **New.** Task 4 |
| `tests/test_graders.py` | **Append.** Task 2 |
| `tests/test_worker.py` | **New.** Task 5 |
| `tests/test_evals_io.py` | **Append.** Task 6 |
| `tests/test_queue.py` | **New.** Task 7 |

---

## Findings summary (severity-ordered)

1. **Grader timeout hardcoded at 60s, ignoring the task's declared `limits.timeout_s`** — a silent scoring bug: a correct agent answer can be marked `FAILED` if its `script-exit` grader script legitimately needs 61s+ of a task's declared 120s+ budget. 8 of 15 `shell-mini` tasks use `script-exit`.
2. **`JsonFieldGrader_` uses bare `==`, so `expect: 1` wrongly matches a JSON `true`** (Python: `bool` is a subclass of `int`) — a silent false-PASS on a type-mismatched answer.
3. **An unexpected exception during grading (e.g. a `docker.errors.APIError` when the task-env container dies mid-grade) escapes `LocalRunner.run()`'s `try/finally`** — `result.json` is never written, and the per-run temp staging directory (full workspace contents) leaks on disk forever.
4. **`except Exception` around `agent.wait()` mislabels every Docker/infra error as a timeout** — a real error (daemon hiccup, container removed) gets reported to the user as "agent exceeded Ns limit", hiding the actual cause.
5. **`worker.process_job()` has no exception guard around its first few lines, and `worker.main()` calls it with no guard either** — a malformed queue job (missing key) or a transient DB error crashes the entire worker process, silently stalling every other queued run until someone notices and restarts it.
6. **BYO-eval zip upload only caps compressed size (5 MB) and entry count (500), never total uncompressed size** — a small, highly-compressible archive (a "zip bomb") can expand to fill the host's disk.
7. **`faraday/queue.py` opens a brand-new Redis connection/pool on every `enqueue`/`dequeue`/`publish_event` call** — the worker's poll loop (every 5s, forever) churns a fresh TCP connection each tick instead of reusing one. Efficiency, not correctness.
8. **`docs/DECISIONS.md`'s "What's next" section is stale** — it lists the real LLM agent, sandbox hardening, and BYO-eval web upload as *not yet built*, but `README.md` confirms all three have shipped.

Not included as a task (investigated, not a bug): `faraday/cli.py`'s `eval add` defaults to allowing `script-exit` graders unless `--no-shell-graders` is passed, which looks inconsistent with the API upload path's opposite default — but this is intentional and already documented in `docs/byo-eval.md` ("`faraday eval add` trusts local zips; pass `--no-shell-graders` to opt out."). No code change needed.

---

## Task 1: Wire the task's configured grading timeout into `GraderContext`

**Root cause:** `faraday/grading/base.py:24` defaults `GraderContext.timeout_s` to `60`. `faraday/orchestrator/runner.py`'s `LocalRunner.run()` constructs `GraderContext(...)` (around line 198) without ever passing `timeout_s=spec.limits.timeout_s`, so every run silently uses the 60s default regardless of what the task's `task.yaml` declares (e.g. every `shell-mini` task declares `timeout_s: 120`). `faraday/grading/container_graders.py:43` then does `["timeout", str(ctx.timeout_s), "bash", container_path]` — so the grader script is killed at 60s even when the task says the run gets up to 120s (or more). Confirmed via `tests/test_container_graders.py`, which has no test covering this wiring at all.

**Files:**
- Modify: `faraday/orchestrator/runner.py`
- Test: `tests/test_runner_grading.py` (create)

**Interfaces:**
- Produces: `LocalRunner._grader_context(self, spec: TaskSpec, workspace: Path, task_dir: Path, task_container) -> GraderContext` — used by Task 3.

- [ ] **Step 1: Write the failing test**

Create `tests/test_runner_grading.py`:

```python
"""LocalRunner's grader-context wiring and crash-safety."""

from __future__ import annotations

from pathlib import Path

from faraday.orchestrator.runner import LocalRunner
from faraday.spec import TaskSpec


class _FakeClient:
    pass


def _runner() -> LocalRunner:
    r = object.__new__(LocalRunner)
    r.client = _FakeClient()
    return r


def _spec(timeout_s: int = 300) -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "id": "t001-hello",
            "name": "x",
            "instruction": "go",
            "grader": {"type": "file-match", "path": "output/r.txt", "expect": "1"},
            "limits": {"timeout_s": timeout_s},
        }
    )


def test_grader_context_uses_the_tasks_configured_timeout(tmp_path: Path) -> None:
    runner = _runner()
    ctx = runner._grader_context(_spec(timeout_s=175), tmp_path, tmp_path, task_container=None)
    assert ctx.timeout_s == 175
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runner_grading.py -v`
Expected: FAIL with `AttributeError: 'LocalRunner' object has no attribute '_grader_context'`

- [ ] **Step 3: Add the method**

In `faraday/orchestrator/runner.py`, find:

```python
    def _limits_kwargs(self, spec: TaskSpec) -> dict:
        return {
            "mem_limit": f"{spec.limits.memory_mb}m",
            "nano_cpus": int(spec.limits.cpus * 1e9),
        }
```

Replace with:

```python
    def _limits_kwargs(self, spec: TaskSpec) -> dict:
        return {
            "mem_limit": f"{spec.limits.memory_mb}m",
            "nano_cpus": int(spec.limits.cpus * 1e9),
        }

    def _grader_context(
        self, spec: TaskSpec, workspace: Path, task_dir: Path, task_container
    ) -> GraderContext:
        return GraderContext(
            workspace=workspace,
            task_dir=task_dir,
            docker_client=self.client,
            task_container=task_container,
            timeout_s=spec.limits.timeout_s,
        )
```

- [ ] **Step 4: Use it at the call site**

Find:

```python
            usage = _read_usage(workspace)
            outcome = run_grader(
                spec.grader,
                GraderContext(
                    workspace=workspace,
                    task_dir=tdir,
                    docker_client=self.client,
                    task_container=task_env,
                ),
            )
            _copy_tree(workspace / "output", layout.output_dir)
```

Replace with:

```python
            usage = _read_usage(workspace)
            outcome = run_grader(
                spec.grader, self._grader_context(spec, workspace, tdir, task_env)
            )
            _copy_tree(workspace / "output", layout.output_dir)
```

- [ ] **Step 5: Run test to verify it passes, then the full non-docker suite**

Run: `pytest tests/test_runner_grading.py -v`
Expected: PASS

Run: `pytest -m "not docker" -q`
Expected: all pass (this must not change any existing test's behavior)

- [ ] **Step 6: Commit**

```bash
git add faraday/orchestrator/runner.py tests/test_runner_grading.py
git commit -m "fix: honor the task's configured grading timeout instead of a hardcoded 60s"
```

---

## Task 2: `JsonFieldGrader_` must not let `bool` match `int`

**Root cause:** `faraday/grading/deterministic.py`'s `JsonFieldGrader_.grade()` falls through to plain `current == expected` for non-string values. Python's `bool` is a subclass of `int`, so `True == 1` and `False == 0` are both `True`. A task grader written as `expect: 1` will therefore incorrectly PASS an agent whose JSON output has `"field": true` — a type-mismatched, semantically wrong answer. The codebase already guards against exactly this elsewhere (`faraday/orchestrator/runner.py::_read_usage` explicitly checks `isinstance(count, bool)` before accepting a token count, and it's unit-tested in `tests/test_runner_usage.py::test_boolean_token_counts_rejected`) — this grader just missed the same guard.

**Files:**
- Modify: `faraday/grading/deterministic.py`
- Test: `tests/test_graders.py` (append)

- [ ] **Step 1: Write the failing test**

In `tests/test_graders.py`, after `test_json_field_string_compare_is_trimmed`, add:

```python
def test_json_field_bool_does_not_match_int(tmp_path: Path) -> None:
    # bool is a subclass of int in Python; `expect: 1` must not match a JSON `true`.
    ctx = _ctx(tmp_path, {"output/o.json": '{"ok": true}'})
    out = run_grader(
        JsonFieldGrader(type="json-field", path="output/o.json", field="ok", expect=1), ctx
    )
    assert not out.passed


def test_json_field_bool_matches_bool(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"output/o.json": '{"ok": true}'})
    out = run_grader(
        JsonFieldGrader(type="json-field", path="output/o.json", field="ok", expect=True), ctx
    )
    assert out.passed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_graders.py -k bool -v`
Expected: `test_json_field_bool_does_not_match_int` FAILS (`assert not True` — it currently passes because `True == 1`)

- [ ] **Step 3: Fix the comparison**

In `faraday/grading/deterministic.py`, find:

```python
        expected: object = self.spec.expect
        if isinstance(expected, str) and isinstance(current, str):
            ok = current.strip() == expected.strip()
        else:
            ok = current == expected
```

Replace with:

```python
        expected: object = self.spec.expect
        if isinstance(expected, str) and isinstance(current, str):
            ok = current.strip() == expected.strip()
        elif isinstance(expected, bool) or isinstance(current, bool):
            # bool is a subclass of int in Python; without this guard `expect: 1`
            # would wrongly match a JSON `true` (and `expect: 0` a `false`).
            ok = isinstance(current, bool) and current == expected
        else:
            ok = current == expected
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_graders.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add faraday/grading/deterministic.py tests/test_graders.py
git commit -m "fix: json-field grader must not let bool cross-match int"
```

---

## Task 3: Never let an unexpected grading exception skip `result.save()` / cleanup

**Root cause:** `faraday/grading/deterministic.py::run_grader` only catches `FaradayError`. `faraday/grading/container_graders.py::ScriptExitGrader_.grade()` calls `ctx.task_container.exec_run(...)`, which can raise `docker.errors.APIError` (e.g. the task-env container was OOM-killed or removed mid-grade) — not a `FaradayError`, so it isn't caught. That exception then escapes the `try/finally` in `LocalRunner.run()` (the `finally` block still removes containers/network, but execution never reaches the code after it), so `result.save()` and `shutil.rmtree(staging)` never run: no `result.json` is written for that run, and the per-run temp staging directory (containing the full workspace, potentially including task inputs) is orphaned on disk permanently.

**Files:**
- Modify: `faraday/orchestrator/runner.py`
- Test: `tests/test_runner_grading.py` (append)

**Interfaces:**
- Consumes: `LocalRunner._grader_context` from Task 1.
- Produces: `_grade_safely(grader_spec, ctx: GraderContext) -> GraderOutcome` — used at the call site in `LocalRunner.run()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_runner_grading.py`:

```python
def test_grade_safely_survives_an_unexpected_exception(monkeypatch, tmp_path: Path) -> None:
    from faraday.grading.base import GraderContext
    from faraday.orchestrator import runner as runner_mod

    def _boom(grader_spec, ctx):
        raise RuntimeError("container vanished mid-grade")

    monkeypatch.setattr(runner_mod, "run_grader", _boom)

    ctx = GraderContext(workspace=tmp_path, task_dir=tmp_path)
    outcome = runner_mod._grade_safely(object(), ctx)

    assert outcome.passed is False
    assert outcome.score == 0.0
    assert "RuntimeError" in outcome.detail


def test_grade_safely_passes_through_a_normal_outcome(tmp_path: Path) -> None:
    from faraday.grading.base import GraderContext
    from faraday.orchestrator.runner import _grade_safely
    from faraday.spec import FileMatchGrader

    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "r.txt").write_text("ok", encoding="utf-8")
    ctx = GraderContext(workspace=tmp_path, task_dir=tmp_path)
    grader_spec = FileMatchGrader(type="file-match", path="output/r.txt", expect="ok")

    outcome = _grade_safely(grader_spec, ctx)

    assert outcome.passed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runner_grading.py -k grade_safely -v`
Expected: FAIL with `AttributeError: module 'faraday.orchestrator.runner' has no attribute '_grade_safely'`

- [ ] **Step 3: Implement `_grade_safely` and use it**

In `faraday/orchestrator/runner.py`, find the import line:

```python
from faraday.grading import run_grader
from faraday.grading.base import GraderContext
```

Replace with:

```python
from faraday.grading import run_grader
from faraday.grading.base import GraderContext, GraderOutcome
```

Find:

```python
def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
```

Replace with:

```python
def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def _grade_safely(grader_spec, ctx: GraderContext) -> GraderOutcome:
    """Run the grader; never let a container/infra crash skip result.save()."""
    try:
        return run_grader(grader_spec, ctx)
    except Exception as e:
        return GraderOutcome(
            score=0.0, passed=False, detail=f"grader crashed: {type(e).__name__}: {e}"
        )
```

Now find the call site (as left by Task 1):

```python
            usage = _read_usage(workspace)
            outcome = run_grader(
                spec.grader, self._grader_context(spec, workspace, tdir, task_env)
            )
            _copy_tree(workspace / "output", layout.output_dir)
```

Replace with:

```python
            usage = _read_usage(workspace)
            outcome = _grade_safely(
                spec.grader, self._grader_context(spec, workspace, tdir, task_env)
            )
            _copy_tree(workspace / "output", layout.output_dir)
```

- [ ] **Step 4: Run tests to verify they pass, then the full non-docker suite**

Run: `pytest tests/test_runner_grading.py -v`
Expected: all PASS

Run: `pytest -m "not docker" -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add faraday/orchestrator/runner.py tests/test_runner_grading.py
git commit -m "fix: never let an unexpected grading exception skip result.save()/cleanup"
```

---

## Task 4: Don't mislabel a real Docker/infra error as a timeout

**Root cause:** In `faraday/orchestrator/runner.py::LocalRunner.run()`, the block around `agent.wait(timeout=spec.limits.timeout_s)` uses a bare `except Exception`, treating every failure — a genuine timeout, but also `docker.errors.APIError`, `DockerException`, a daemon disconnect, or the container having already been removed — as `timed_out = True`. The resulting `result.detail` says `"agent exceeded Ns limit"` even when the real cause was an infrastructure error, which is misleading to whoever is debugging the run.

**Files:**
- Modify: `faraday/orchestrator/runner.py`
- Test: `tests/test_runner_wait.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks (independent of Tasks 1-3, but this plan applies it after them since it touches an adjacent block in the same file).
- Produces: `_wait_for_agent(agent, timeout_s: int) -> tuple[bool, str | None, int]` — returns `(timed_out, wait_error, exit_code)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_runner_wait.py`:

```python
"""_wait_for_agent must tell a real timeout apart from a Docker/infra error."""

from __future__ import annotations

from docker.errors import APIError
from requests.exceptions import ReadTimeout

from faraday.orchestrator.runner import _wait_for_agent


class _FakeAgent:
    def __init__(self, wait_effect):
        self._wait_effect = wait_effect
        self.killed = False

    def wait(self, timeout):
        if isinstance(self._wait_effect, Exception):
            raise self._wait_effect
        return self._wait_effect

    def kill(self):
        self.killed = True


def test_normal_exit_reports_status_code() -> None:
    agent = _FakeAgent({"StatusCode": 0})
    timed_out, wait_error, rc = _wait_for_agent(agent, 30)
    assert (timed_out, wait_error, rc) == (False, None, 0)


def test_read_timeout_is_a_real_timeout_and_kills_the_container() -> None:
    agent = _FakeAgent(ReadTimeout("timed out"))
    timed_out, wait_error, rc = _wait_for_agent(agent, 30)
    assert timed_out is True
    assert wait_error is None
    assert agent.killed is True


def test_api_error_is_reported_as_an_error_not_a_timeout() -> None:
    agent = _FakeAgent(APIError("container removed"))
    timed_out, wait_error, rc = _wait_for_agent(agent, 30)
    assert timed_out is False
    assert wait_error is not None and "APIError" in wait_error
    assert agent.killed is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runner_wait.py -v`
Expected: FAIL with `ImportError: cannot import name '_wait_for_agent'`

- [ ] **Step 3: Add the `ReadTimeout` import**

Find:

```python
import docker
from docker.errors import APIError, DockerException, ImageNotFound
```

Replace with:

```python
import docker
from docker.errors import APIError, DockerException, ImageNotFound
from requests.exceptions import ReadTimeout
```

- [ ] **Step 4: Add `_wait_for_agent`**

Find (as left by Task 3):

```python
def _grade_safely(grader_spec, ctx: GraderContext) -> GraderOutcome:
    """Run the grader; never let a container/infra crash skip result.save()."""
    try:
        return run_grader(grader_spec, ctx)
    except Exception as e:
        return GraderOutcome(
            score=0.0, passed=False, detail=f"grader crashed: {type(e).__name__}: {e}"
        )
```

Replace with:

```python
def _grade_safely(grader_spec, ctx: GraderContext) -> GraderOutcome:
    """Run the grader; never let a container/infra crash skip result.save()."""
    try:
        return run_grader(grader_spec, ctx)
    except Exception as e:
        return GraderOutcome(
            score=0.0, passed=False, detail=f"grader crashed: {type(e).__name__}: {e}"
        )


def _wait_for_agent(agent, timeout_s: int) -> tuple[bool, str | None, int]:
    """Wait for the agent container; tell a real timeout apart from a Docker error.

    Returns ``(timed_out, wait_error, exit_code)``.
    """
    try:
        wait_status = agent.wait(timeout=timeout_s)
        return False, None, int(wait_status.get("StatusCode", -1))
    except ReadTimeout:
        try:
            agent.kill()
        except APIError:
            pass
        return True, None, -1
    except (APIError, DockerException) as e:
        return False, f"{type(e).__name__}: {e}", -1
```

- [ ] **Step 5: Use it in `run()` and thread `wait_error` into the status computation**

Find:

```python
        net = self.client.networks.create(f"faraday-net-{run_id}", driver="bridge")
        task_env = None
        agent = None
        timed_out = False
        rc = -1
        try:
            task_env = self._start_task_env(task_ref, workspace, run_id, spec)
            agent = self._start_agent(
                agent_ref, workspace, run_id, spec, manifest, net.id, env=env
            )
            try:
                wait_status = agent.wait(timeout=spec.limits.timeout_s)
                rc = int(wait_status.get("StatusCode", -1))
            except Exception:
                timed_out = True
                try:
                    agent.kill()
                except APIError:
                    pass
                rc = -1
            (layout.logs_dir / "agent.log").write_bytes(
                agent.logs(stdout=True, stderr=True, timestamps=True)
            )
```

Replace with:

```python
        net = self.client.networks.create(f"faraday-net-{run_id}", driver="bridge")
        task_env = None
        agent = None
        timed_out = False
        wait_error: str | None = None
        rc = -1
        try:
            task_env = self._start_task_env(task_ref, workspace, run_id, spec)
            agent = self._start_agent(
                agent_ref, workspace, run_id, spec, manifest, net.id, env=env
            )
            timed_out, wait_error, rc = _wait_for_agent(agent, spec.limits.timeout_s)
            (layout.logs_dir / "agent.log").write_bytes(
                agent.logs(stdout=True, stderr=True, timestamps=True)
            )
```

Find:

```python
        if timed_out:
            status = STATUS_TIMEOUT
            detail = f"agent exceeded {spec.limits.timeout_s}s limit; {outcome.detail}"
        elif rc != 0:
```

Replace with:

```python
        if wait_error:
            status = STATUS_AGENT_ERROR
            detail = f"agent container error: {wait_error}; {outcome.detail}"
        elif timed_out:
            status = STATUS_TIMEOUT
            detail = f"agent exceeded {spec.limits.timeout_s}s limit; {outcome.detail}"
        elif rc != 0:
```

- [ ] **Step 6: Run tests to verify they pass, then the full non-docker suite**

Run: `pytest tests/test_runner_wait.py -v`
Expected: all PASS

Run: `pytest -m "not docker" -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add faraday/orchestrator/runner.py tests/test_runner_wait.py
git commit -m "fix: distinguish a real agent timeout from a Docker/infra error"
```

---

## Task 5: One bad queue job must not crash the whole worker process

**Root cause:** `faraday/orchestrator/worker.py::process_job()` dereferences `job["run_id"]`, `job["task_dir"]`, `job["agent_dir"]` and runs the first DB `session.commit()` *before* its own `try/except` begins. `main()`'s loop then calls `process_job(job)` with no guard of its own. Any failure in that unguarded stretch — a malformed job dict (e.g. from a future API change or a corrupted queue entry) or a transient Postgres error on the very first commit — raises out of `process_job`, out of `main()`'s loop body, and kills the entire worker process. Every other job still sitting in the Redis queue is then stuck until a human notices and restarts `faraday worker`.

**Files:**
- Modify: `faraday/orchestrator/worker.py`
- Test: `tests/test_worker.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_worker.py`:

```python
"""process_job must never crash the worker loop on a bad job or a transient error."""

from __future__ import annotations

from faraday.orchestrator.worker import process_job
from faraday.store.db import Run


def test_process_job_ignores_a_job_with_no_run_id(fresh_db) -> None:
    process_job({})  # must not raise


def test_process_job_marks_the_run_errored_on_a_malformed_job(fresh_db) -> None:
    SessionLocal = fresh_db
    with SessionLocal() as session:
        session.add(Run(run_id="r1", task_slug="t", agent_slug="a"))
        session.commit()

    process_job({"run_id": "r1"})  # missing task_dir / agent_dir -- must not raise

    with SessionLocal() as session:
        row = session.query(Run).filter_by(run_id="r1").one()
        assert row.status == "error"
        assert "task_dir" in row.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_worker.py -v`
Expected: both FAIL — `test_process_job_ignores_a_job_with_no_run_id` with `KeyError: 'run_id'`; `test_process_job_marks_the_run_errored_on_a_malformed_job` with an uncaught `KeyError: 'task_dir'`

- [ ] **Step 3: Harden `process_job`**

In `faraday/orchestrator/worker.py`, find the whole function:

```python
def process_job(job: dict) -> None:
    run_id: str = job["run_id"]
    task_dir = Path(job["task_dir"])
    agent_dir = Path(job["agent_dir"])
    SessionLocal = get_sessionmaker()

    with SessionLocal() as session:
        row = session.query(Run).filter_by(run_id=run_id).one_or_none()
        if row is None:
            return
        row.status = "running"
        row.started_at = row.started_at or utcnow()
        session.commit()

    try:
        runner = LocalRunner(PROJECT_ROOT)
        result, run_dir = runner.run(
            task_dir, agent_dir, run_id=run_id, env=job.get("env")
        )
        trajectory = _read_trajectory(run_dir)
        usage = result.usage or {}
        cost = None
        if usage:
            from faraday.pricing import estimate_cost_usd

            cost = estimate_cost_usd(
                usage["model"], usage["input_tokens"], usage["output_tokens"]
            )
        with SessionLocal() as session:
            row = session.query(Run).filter_by(run_id=run_id).one()
            row.status = result.status
            row.score = result.score
            row.passed = result.passed
            row.duration_s = result.duration_s
            row.detail = result.detail
            row.trajectory = trajectory
            row.meta = result.meta
            row.model = usage.get("model")
            row.input_tokens = usage.get("input_tokens")
            row.output_tokens = usage.get("output_tokens")
            row.cost_usd = cost
            row.finished_at = utcnow()
            session.commit()
        publish_event(
            {"type": "run.finished", "run_id": run_id, "status": result.status}
        )
    except Exception as e:
        traceback.print_exc()
        with SessionLocal() as session:
            row = session.query(Run).filter_by(run_id=run_id).one_or_none()
            if row is not None:
                row.status = "error"
                row.error = f"{type(e).__name__}: {e}"
                row.finished_at = utcnow()
                session.commit()
        publish_event({"type": "run.error", "run_id": run_id})
```

Replace with:

```python
def process_job(job: dict) -> None:
    run_id = job.get("run_id")
    if not run_id:
        print(f"[worker] dropping malformed job (no run_id): {job!r}")
        return

    SessionLocal = get_sessionmaker()
    try:
        task_dir = Path(job["task_dir"])
        agent_dir = Path(job["agent_dir"])

        with SessionLocal() as session:
            row = session.query(Run).filter_by(run_id=run_id).one_or_none()
            if row is None:
                return
            row.status = "running"
            row.started_at = row.started_at or utcnow()
            session.commit()

        runner = LocalRunner(PROJECT_ROOT)
        result, run_dir = runner.run(
            task_dir, agent_dir, run_id=run_id, env=job.get("env")
        )
        trajectory = _read_trajectory(run_dir)
        usage = result.usage or {}
        cost = None
        if usage:
            from faraday.pricing import estimate_cost_usd

            cost = estimate_cost_usd(
                usage["model"], usage["input_tokens"], usage["output_tokens"]
            )
        with SessionLocal() as session:
            row = session.query(Run).filter_by(run_id=run_id).one()
            row.status = result.status
            row.score = result.score
            row.passed = result.passed
            row.duration_s = result.duration_s
            row.detail = result.detail
            row.trajectory = trajectory
            row.meta = result.meta
            row.model = usage.get("model")
            row.input_tokens = usage.get("input_tokens")
            row.output_tokens = usage.get("output_tokens")
            row.cost_usd = cost
            row.finished_at = utcnow()
            session.commit()
        publish_event(
            {"type": "run.finished", "run_id": run_id, "status": result.status}
        )
    except Exception as e:
        traceback.print_exc()
        try:
            with SessionLocal() as session:
                row = session.query(Run).filter_by(run_id=run_id).one_or_none()
                if row is not None:
                    row.status = "error"
                    row.error = f"{type(e).__name__}: {e}"
                    row.finished_at = utcnow()
                    session.commit()
        except Exception:
            traceback.print_exc()
        try:
            publish_event({"type": "run.error", "run_id": run_id})
        except Exception:
            pass
```

- [ ] **Step 4: Also guard the call site in `main()`**

Find:

```python
        run_id = job.get("run_id", "?")
        print(f"[worker] picked up run {run_id}")
        process_job(job)
        print(f"[worker] finished run {run_id}")
```

Replace with:

```python
        run_id = job.get("run_id", "?")
        print(f"[worker] picked up run {run_id}")
        try:
            process_job(job)
        except Exception:
            traceback.print_exc()
            print(f"[worker] job {run_id} failed unexpectedly; continuing")
        print(f"[worker] finished run {run_id}")
```

- [ ] **Step 5: Run tests to verify they pass, then the full non-docker suite**

Run: `pytest tests/test_worker.py -v`
Expected: both PASS

Run: `pytest -m "not docker" -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add faraday/orchestrator/worker.py tests/test_worker.py
git commit -m "fix: a malformed job or transient DB error must not crash the worker loop"
```

---

## Task 6: Cap the uncompressed size of an uploaded BYO-eval archive (zip-bomb guard)

**Root cause:** `faraday/evals_io.py::_safe_extract` checks the *compressed* archive size (`MAX_ARCHIVE_BYTES = 5 * 1024 * 1024`) and the member count (`MAX_MEMBERS = 500`), then calls `zf.extractall(dest)` unconditionally. A small, highly-compressible archive (e.g. tens of megabytes of a repeated byte) stays comfortably under the 5 MB compressed cap while expanding to far more on disk — a classic decompression bomb — and nothing currently stops `extractall` from writing all of it.

**Files:**
- Modify: `faraday/evals_io.py`
- Test: `tests/test_evals_io.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_evals_io.py`:

```python
def test_install_rejects_a_decompression_bomb(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("tasks/u001-a/task.yaml", _TASK_YAML.format(tid="u001-a"))
        zf.writestr("tasks/u001-a/files/bomb.bin", b"0" * (60 * 1024 * 1024))
    data = buf.getvalue()
    assert len(data) < 1024 * 1024  # compresses to well under the 5 MB archive cap

    with pytest.raises(SpecError):
        install_eval_archive(data, "myeval", tmp_path)
    assert not (tmp_path / "myeval").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_evals_io.py -k bomb -v`
Expected: FAIL — no `SpecError` is raised (the archive installs successfully today)

- [ ] **Step 3: Add the uncompressed-size guard**

In `faraday/evals_io.py`, find:

```python
_EVAL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
MAX_MEMBERS = 500
```

Replace with:

```python
_EVAL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
MAX_MEMBERS = 500
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
```

Find:

```python
def _safe_extract(data: bytes, dest: Path) -> None:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise SpecError(f"archive too large (> {MAX_ARCHIVE_BYTES} bytes)")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise SpecError(f"not a valid zip archive: {e}") from e
    names = zf.namelist()
    if len(names) > MAX_MEMBERS:
        raise SpecError(f"archive has too many entries (> {MAX_MEMBERS})")
    dest_resolved = dest.resolve()
    for name in names:
        target = (dest / name).resolve()
        if not target.is_relative_to(dest_resolved):
            raise SpecError(f"archive entry escapes destination: {name!r}")
    zf.extractall(dest)
```

Replace with:

```python
def _safe_extract(data: bytes, dest: Path) -> None:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise SpecError(f"archive too large (> {MAX_ARCHIVE_BYTES} bytes)")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise SpecError(f"not a valid zip archive: {e}") from e
    infos = zf.infolist()
    if len(infos) > MAX_MEMBERS:
        raise SpecError(f"archive has too many entries (> {MAX_MEMBERS})")
    total_uncompressed = sum(info.file_size for info in infos)
    if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
        raise SpecError(
            f"archive expands to too much data "
            f"(> {MAX_UNCOMPRESSED_BYTES} bytes uncompressed)"
        )
    dest_resolved = dest.resolve()
    for info in infos:
        target = (dest / info.filename).resolve()
        if not target.is_relative_to(dest_resolved):
            raise SpecError(f"archive entry escapes destination: {info.filename!r}")
    zf.extractall(dest)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_evals_io.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add faraday/evals_io.py tests/test_evals_io.py
git commit -m "fix: reject decompression-bomb BYO-eval archives"
```

---

## Task 7 (low priority): Reuse one Redis connection instead of one per call

**Root cause:** `faraday/queue.py::connection()` calls `redis.Redis.from_url(...)` fresh on every invocation, and `enqueue`, `dequeue`, and `publish_event` each call `connection()`. `worker.main()`'s poll loop calls `dequeue()` every `poll_timeout_s` (default 5s) forever, so the worker opens a brand-new connection/pool to Redis on every tick instead of reusing one. This is a resource/efficiency issue, not a correctness bug.

**Files:**
- Modify: `faraday/queue.py`
- Test: `tests/test_queue.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_queue.py`:

```python
"""queue.connection() should reuse a single Redis client instead of one per call."""

from __future__ import annotations

from faraday import queue as queue_mod


class _FakeRedis:
    pass


def test_connection_is_cached_across_calls(monkeypatch) -> None:
    created = []

    def _fake_from_url(url, decode_responses=True):
        client = _FakeRedis()
        created.append(client)
        return client

    monkeypatch.setattr(queue_mod, "_client", None, raising=False)
    monkeypatch.setattr(queue_mod.redis.Redis, "from_url", staticmethod(_fake_from_url))

    first = queue_mod.connection()
    second = queue_mod.connection()

    assert first is second
    assert len(created) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_queue.py -v`
Expected: FAIL — `first is second` is `False` (a new client is built every call today)

- [ ] **Step 3: Cache the client**

In `faraday/queue.py`, find:

```python
from __future__ import annotations

import json

import redis

from faraday.config import EVENTS_CHANNEL, QUEUE_KEY, REDIS_URL


def connection() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)
```

Replace with:

```python
from __future__ import annotations

import json

import redis

from faraday.config import EVENTS_CHANNEL, QUEUE_KEY, REDIS_URL

_client: redis.Redis | None = None


def connection() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _client
```

- [ ] **Step 4: Run tests to verify they pass, then the full non-docker suite**

Run: `pytest tests/test_queue.py -v`
Expected: PASS

Run: `pytest -m "not docker" -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add faraday/queue.py tests/test_queue.py
git commit -m "perf: reuse a single Redis client instead of one per call"
```

---

## Task 8: Refresh the stale "What's next" section in `docs/DECISIONS.md`

**Root cause:** `docs/DECISIONS.md`'s "What's next" section lists the real LLM agent, sandbox hardening flags, and BYO-eval web upload as *not yet built*. `README.md`'s "Status" section confirms all three have shipped. Leaving the stale text risks a reader (or a future contributor) duplicating work that already exists.

**Files:**
- Modify: `docs/DECISIONS.md`

- [ ] **Step 1: Update the section**

Find:

```
## What's next

Real LLM agent (exercise the cost path end-to-end), sandbox hardening flags,
web upload for BYO-evals, an always-on deployment, and an egress proxy — see
`docs/byo-quickstart.md` and the project plan.
```

Replace with:

```
## What's next

Shipped since this was written: the real LLM agent, sandbox hardening flags,
and web upload for BYO-evals (see `docs/byo-quickstart.md`). Still open: an
egress-allowlist proxy for the agent container's outbound network (see
`docs/security.md`), Alembic migrations once there's a leaderboard worth
preserving, and moving the worker into `docker compose` (currently host-only
by design, see above).
```

- [ ] **Step 2: Commit**

```bash
git add docs/DECISIONS.md
git commit -m "docs: refresh DECISIONS.md's stale roadmap section"
```

---

## Self-review

- **Coverage:** All 8 findings from the audit have a task (7 code fixes + 1 doc fix). The one additional item found (`cli.py` default posture for `--no-shell-graders`) was investigated and confirmed to be intentional/documented behavior, not a bug — explicitly called out above so it isn't silently dropped.
- **Placeholders:** none — every step has literal code or literal doc text, no "add error handling" or "similar to Task N" placeholders.
- **Type/name consistency:** `_grader_context` (Task 1) is consumed by `_grade_safely`'s call site (Task 3) with matching signature; `_wait_for_agent`'s `(timed_out, wait_error, exit_code)` tuple (Task 4) matches the unpacking at its call site and the new `wait_error` branch in the status `if/elif` chain. `GraderOutcome` is imported in Task 3 before `_grade_safely` uses it. Tasks 1, 3, and 4 all touch the same region of `faraday/orchestrator/runner.py` and are written to be applied **in order** — each task's "Find" text matches the file state left by the previous task.
