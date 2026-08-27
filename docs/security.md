# Security & threat model

`faraday` runs **untrusted code** from two sources: agent images (submitters) and
uploaded evals (their `grader.sh`). This is what's done about it.

## Agent container

| Control | How |
|---|---|
| No root | runs as uid `65534` (`nobody`) |
| No capabilities | `cap_drop: ["ALL"]` |
| No privilege escalation | `security_opt: ["no-new-privileges"]` |
| Read-only root FS | `read_only: true`; only `/task` (the run workspace) and a 64 MB `tmpfs` `/tmp` are writable |
| Fork-bomb limit | `pids_limit: 256` |
| CPU / memory | per-task `nano_cpus` + `mem_limit` from `task.yaml` `limits` |
| Timeout | hard kill at `limits.timeout_s`; partial output still graded |
| Isolation from the task-env | separate per-run bridge network |

**Still open:** the agent keeps outbound network (it needs model APIs). A hostile
agent can exfiltrate the task inputs or call arbitrary hosts. The real fix is an
egress-allowlist proxy (model endpoints only) — not built. Also: Docker is a shared
kernel; a kernel-level escape is out of scope for this project. A public deployment
that accepts arbitrary submissions should move agents to a microVM (gVisor / Kata /
Firecracker).

## Task-env container

Runs the eval's `grader.sh`. `network_mode: none`, `cap_drop: ["ALL"]`,
`no-new-privileges`, `read_only` + `tmpfs /tmp`, `pids_limit`. It stays root
(grader scripts occasionally need it) but is declawed by the above.

## Uploaded evals

`POST /api/evals` (and `faraday eval add` from a remote) validate every `task.yaml`
and **reject `script-exit` (shell) graders by default** — set
`FARADAY_ALLOW_UPLOADED_SCRIPT_GRADERS=1` to allow them. Archives are capped at 5 MB /
500 entries; path-traversal entries are refused; a bad task rejects the whole
archive, leaving nothing installed.

## BYO API keys

Passed at submit time, forwarded to the **agent** container only (never the
task-env), and only variable **names** are recorded (`meta.env_keys`) — never
values. An allowlist (`*_API_KEY` or a known provider prefix) blocks smuggling
`LD_PRELOAD`, `PATH`, etc.

## Not addressed (by design, for a solo project)

Auth / rate limiting on the API, reward-hacking / anti-cheat detection, resource
quotas per submitter, secrets management beyond env vars.
