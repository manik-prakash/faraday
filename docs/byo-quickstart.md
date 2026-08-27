# Bring your own agent + eval — 5 steps

You have an agent and a set of tasks. Here's the whole loop. (Reference copies live
in `examples/agent-template/` and `examples/sample-eval/`.)

Assumes the platform is running: `docker compose up -d --build` + `bench worker` on
the host (see `docs/deploy.md`).

## 1. Write your agent

Any Docker image that, on start, does:

```
read   /task/task.json        -> { "instruction", "input_files", "limits": {...} }
work   (you have network; model keys arrive as env vars — see below)
write  /task/output/           -> your result files
write  /task/output/trajectory.jsonl   (one JSON object per line)
write  /task/output/usage.json (optional: {"model","input_tokens","output_tokens"})
exit 0
```

Full contract: `docs/agent-contract.md`. Minimal example: `examples/agent-template/`.

## 2. Push the image

```powershell
docker build -t ghcr.io/you/my-agent:v1 examples/agent-template
docker push ghcr.io/you/my-agent:v1
```

## 3. Point a 3-line manifest at it

`my-agent/agent.yaml` — no repo checkout, no build context:

```yaml
id: my-agent
name: My Agent
image: ghcr.io/you/my-agent:v1
```

## 4. Bring your eval

A directory of tasks (schema: `docs/task-spec.md`):

```
my-eval/
└── tasks/
    ├── m001-thing/task.yaml        # + files/ , + grader.sh for script-exit
    └── m002-other/task.yaml
```

Install it:

```powershell
bench eval add ./my-eval --name my-eval
# or, against a remote instance, from the web UI's "Evals" panel (upload a .zip of tasks/)
```

A public instance rejects `script-exit` (shell) graders in uploaded evals unless it
sets `BENCH_ALLOW_UPLOADED_SCRIPT_GRADERS=1`. `bench eval add` trusts local zips
(`--no-shell-graders` to opt out).

## 5. Run it

```powershell
bench submit --task evals/my-eval/tasks/m001-thing --agent ./my-agent `
  --env OPENAI_API_KEY=sk-...        # keys go to the agent container only; names logged, not values
```

Watch it on `http://localhost:8000/#/` — queue → container → score → step through the
trajectory → cost (if the agent reported `usage.json`).
