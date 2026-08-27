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
5. *(optional)* Write **`/task/output/usage.json`** for cost tracking — a single object
   `{"model": "gpt-4o", "input_tokens": 1234, "output_tokens": 567}`. The platform
   multiplies the token counts by its price table (`bench/pricing.py`) to compute
   `cost_usd`. Omit the file if you have no usage to report; a non-object payload,
   negative counts, or a missing `model` are ignored.

Exit 0 on success. The grader inspects `/task/output/`; logs are captured from stdout/stderr.

## Model API keys / environment

Bring your own keys. Pass them at submit time and the platform injects them into the
**agent container only** (never the task-env container):

```
bench submit --task ... --agent ... --env OPENAI_API_KEY=sk-... --env-file .env
# or in the API body:  {"task": "...", "agent": "...", "env": {"OPENAI_API_KEY": "sk-..."}}
```

Only variables whose name ends in `_API_KEY` or starts with a known provider prefix
(`OPENAI_`, `ANTHROPIC_`, `GEMINI_`, `MISTRAL_`, `BENCH_`, …) are accepted; anything
else is rejected. The platform records only the variable **names** (`meta.env_keys`),
never their values.

## Starting points

- **`examples/agent-template/`** — copy this, edit one function.
- `agents/dummy-agent/` — stdlib-only, solves `t001-hello`.
- `agents/llm-agent/` — a real BYO-key agent (one OpenAI/Anthropic call).

```dockerfile
FROM python:3.12-slim
WORKDIR /agent
COPY solve.py .
ENTRYPOINT ["python", "/agent/solve.py"]
```

## Resource limits

Containers get the task's CPU/memory limits and hard timeout. On timeout your container
is killed; partial outputs still get graded.
