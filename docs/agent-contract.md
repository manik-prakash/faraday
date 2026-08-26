# Agent Contract (`agent.yaml`)

An agent is any Docker image that follows this protocol.

## Manifest

```
agents/my-agent/
├── agent.yaml
├── Dockerfile
└── ...agent code
```

| Field | Required | Notes |
|---|---|---|
| `id` | yes | slug |
| `name` | yes | display name |
| `version` | no | default `0.1.0` |
| `image` | one of | already-built image ref |
| `build` | one of | build context dir (relative to agent dir) |
| `tag` | required with `build` | tag to apply to the built image |
| `entrypoint` | no | override container entrypoint |

## Protocol

When your container starts, the platform mounts the task workspace at **`/task`** and
sets working dir `/task`. Your job:

1. Read `/task/task.json` — contains `instruction`, `input_files`, `limits.timeout_s`
2. Do the task (call your LLM, use tools, whatever — you have network access)
3. Write outputs to **`/task/output/`**
4. Append trajectory events to **`/task/output/trajectory.jsonl`** — one JSON object
   per line: `{"ts": ..., "action": "...", "detail": {...}}`

Exit 0 on success. The grader inspects `/task/output/`; logs are captured from stdout/stderr.

## Minimal reference implementation

See `agents/dummy-agent/` — a stdlib-only Python agent that solves `t001-hello`.

```dockerfile
FROM python:3.12-slim
WORKDIR /agent
COPY solve.py .
ENTRYPOINT ["python", "/agent/solve.py"]
```

## Resource limits

Containers get the task's CPU/memory limits and hard timeout. On timeout your container
is killed; partial outputs still get graded.
