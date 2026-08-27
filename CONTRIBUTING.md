# Contributing

## Add a task

Create `evals/<eval>/tasks/<id>/task.yaml` (schema: `docs/task-spec.md`). Put static
inputs in `files/`; for state checks add a `grader.sh` and use the `script-exit`
grader. Validate:

```powershell
python -c "from faraday.spec import load_task; load_task('evals/<eval>/tasks/<id>')"
```

## Add an agent

Any Docker image following `docs/agent-contract.md`: read `/task/task.json`, write
`/task/output/`, append `/task/output/trajectory.jsonl`, optionally
`/task/output/usage.json`. See `agents/dummy-agent/` (minimal) and
`agents/scripted-agent/` (keyless reference solver).

## Dev loop

```powershell
pip install -e ".[dev]"
ruff check faraday/ tests/ agents/
pytest -m "not docker"          # add a Docker daemon + drop the filter for E2E
```

Every change is test-first: write the failing test, watch it fail, then implement.
