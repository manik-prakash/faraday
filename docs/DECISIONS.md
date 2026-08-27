# Design decisions

Why `faraday` is built the way it is, and what the tradeoffs were.

## Sandboxing: Docker, not gVisor / Firecracker / a managed sandbox

The platform runs **untrusted agent code** (a stranger's Docker image) and
**untrusted eval code** (an uploaded `grader.sh`). Options considered:

| Option | Verdict |
|---|---|
| **Docker + resource limits + no-new-privileges + cap-drop + non-root + read-only rootfs** | **Chosen.** Zero extra infra, reproducible, runs identically on a laptop and a Linux box. Good enough for classmate/demo scale. |
| gVisor / Kata / Firecracker microVMs | Stronger isolation, but adds a kernel/runtime dependency and Linux-host complexity for a solo project. The right move *if this ever accepts public submissions at scale* — noted in `docs/security.md`. |
| Managed sandbox (E2B / Modal) | No infra to run, but a paid dependency and less to talk about in an infra interview. The whole point was to build the orchestration layer. |

The agent container keeps **network access** (it needs to reach model APIs). The
honest mitigation is an egress-allowlist proxy; that's documented as the next step,
not built.

## Grading: deterministic first, LLM-judge never (so far)

Every grader (`file-match`, `file-regex`, `json-field`, `script-exit`) is
deterministic and runs host-side or in the network-`none` task-env container.
Reasons: reproducibility (an LLM judge introduces variance and cost into the
*scoring*), debuggability (the run detail shows exactly why something failed), and
trust (a public leaderboard needs scores that reproduce). `script-exit` covers the
cases exact-match can't by letting a task ship a verification script.

## Worker runs on the host, not in `docker compose`

The worker launches **sibling** containers (task-env + agent) via the host Docker
daemon and bind-mounts a per-run staging directory into them. A worker running
*inside* a container would hand the daemon paths only it can see. So `docker
compose up` runs Postgres + Redis + the API/UI; the worker is a separate host
process. A DinD or shared-staging-volume setup could containerize it later; it
wasn't worth the path-mapping complexity now.

## No schema migrations (yet)

`faraday db-init --reset` drops and recreates. Fine while the project is pre-data and
solo. Alembic is the obvious upgrade the moment there's a leaderboard worth
preserving.

## Two reference agents

- `dummy-agent` — 40 lines, solves exactly one task. Proves the contract and shows
  an honest near-zero baseline on the board.
- `scripted-agent` — keyless, genuinely solves every `shell-mini` and
  `datawrangle-mini` task with real transforms; answers `gaia-mini` from a **labeled
  built-in table** (it's a reference/demo baseline, not a leaderboard contender).
  This keeps the board populated and gives the trajectory viewer real data without
  needing an API key in CI.

## BYO API keys: names, never values

Keys are passed at submit time, forwarded only to the **agent** container, and the
platform records only the variable *names* (`meta.env_keys`). An allowlist
(`*_API_KEY` or a known provider prefix) rejects everything else so a submitter
can't smuggle in `LD_PRELOAD` or `PATH`.

## What's next

Real LLM agent (exercise the cost path end-to-end), sandbox hardening flags,
web upload for BYO-evals, an always-on deployment, and an egress proxy — see
`docs/byo-quickstart.md` and the project plan.
