# scripted-agent

A keyless reference agent. It uses **no network and no model API key**; its job is
to give the leaderboard a meaningful non-zero baseline and the trajectory viewer
real data.

- **shell-mini** — every task is solved with a real, deterministic transform
  (dedupe, CSV filter, JSON deep-merge, INI→JSON, link extraction, …).
- **gaia-mini** — knowledge questions are answered from a small built-in table.
  `g011` (17²) and `g014` (ten in binary) are genuinely computed. This is a
  demo/reference baseline, **not** a real leaderboard contender.

The solver core (`solve.solve(task_root, task_id)`) operates on a plain workspace
directory, so it is unit-tested without Docker in `tests/test_scripted_agent.py`.
