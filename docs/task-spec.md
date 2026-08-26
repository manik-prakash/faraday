# Task Spec (`task.yaml`)

Every benchmark task is a directory:

```
evals/<bench>/tasks/<task-id>/
├── task.yaml
└── files/            # static input files copied into /task/input
```

## Schema

| Field | Required | Notes |
|---|---|---|
| `id` | yes | slug (`^[a-z0-9][a-z0-9-]*$`) |
| `name` | yes | display name |
| `description` | no | |
| `version` | no | default `"1"` |
| `instruction` | yes | what the agent must do (also embedded in `/task/task.json`) |
| `env.image` | one of | prebuilt image ref, e.g. `python:3.12-slim` |
| `env.build` | one of | build context dir (relative to task dir) for a custom environment image |
| `files[]` | no | `src` (relative to task dir) → `dest` (relative path under `/task/input`) |
| `grader` | yes | see below |
| `limits.cpus` | no | default 1.0 |
| `limits.memory_mb` | no | default 512 |
| `limits.timeout_s` | no | default 300 |

## Graders

Deterministic graders run host-side against the run workspace after the agent exits.

```yaml
grader:
  type: file-match      # exact (trimmed) or contains match of file contents
  path: output/report.txt
  expect: "142"
  mode: exact           # exact | contains
```

```yaml
grader:
  type: file-regex      # re.search with DOTALL over file contents
  path: output/result.json
  pattern: '"status":\s*"ok"'
```

## Runtime layout inside containers

Both containers mount the same workspace at `/task`:

```
/task
├── task.json        # machine-readable task info for the agent
├── input/           # declared files
└── output/          # agent writes results + trajectory.jsonl here
```

The task-env container runs `sleep infinity` with **no network**; it is the task's
environment holder. The agent container has network access (for model APIs) and
read-write access to `/task`.

## Statuses a run can produce

`passed`, `failed` (agent exited 0 but grader failed), `agent_error` (nonzero exit),
`timeout`.
