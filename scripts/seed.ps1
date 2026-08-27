# Submit a baseline set of runs so a fresh leaderboard is populated.
# Requires: `bench serve` + `bench worker` running.
param(
    [string]$Api = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Submit-All($agent, $evals) {
    foreach ($e in $evals) {
        Get-ChildItem -Directory "$root/evals/$e/tasks" | ForEach-Object {
            bench submit --task $_.FullName --agent "$root/agents/$agent" --api $Api
        }
    }
}

# scripted-agent: real solver for shell-mini + datawrangle-mini, canned gaia-mini
Submit-All "scripted-agent" @("shell-mini", "gaia-mini", "datawrangle-mini")
# dummy-agent: only ever solves t001 — shows an honest low baseline
Submit-All "dummy-agent" @("shell-mini")

Write-Host "seeded — open $Api/#/"
