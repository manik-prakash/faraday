# Bring Your Own Eval

Ship a set of tasks and run any agent against them, right next to the built-in evals.

## Layout

An eval is a directory of tasks (see `docs/task-spec.md` for `task.yaml`):

```
my-eval/
└── tasks/
    ├── m001-thing/
    │   ├── task.yaml
    │   ├── files/            # optional inputs
    │   └── grader.sh         # optional, for script-exit graders
    └── m002-other/
        └── task.yaml
```

## Install it

**CLI** (local, no server needed):

```powershell
faraday eval add ./my-eval --name my-eval        # a directory containing tasks/
faraday eval add ./my-eval.zip --name my-eval    # or a .zip of the same
faraday eval list                                # sync + show every registered eval
```

**API**:

```powershell
Compress-Archive -Path my-eval/tasks -DestinationPath my-eval.zip
curl.exe --data-binary "@my-eval.zip" "http://127.0.0.1:8000/api/evals?name=my-eval"
```

Either path validates every `task.yaml` (rejecting the whole archive on the first
error, naming the offending task), copies it under `evals/<name>/`, and registers
the tasks. Names must be lowercase letters, digits, and hyphens. Archives are capped
at 5 MB / 500 entries and path-traversal entries are refused.

**Shell graders in uploads:** `script-exit` graders run arbitrary bash in the
(network-`none`) task-env container. The API and remote installs **reject** them
unless `FARADAY_ALLOW_UPLOADED_SCRIPT_GRADERS=1`. `faraday eval add` trusts local zips;
pass `--no-shell-graders` to opt out.

Try it: `faraday eval add ./examples/sample-eval --name sample` (two file-match tasks).

## Run against it

```powershell
faraday submit --task evals/my-eval/tasks/m001-thing --agent agents/my-agent
```

The leaderboard groups results by eval name.
