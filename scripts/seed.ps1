# Populate a fresh leaderboard by submitting a baseline set of runs.
# Requires the API (faraday serve / compose `api`) + a `faraday worker` running.
# Talks to the HTTP API directly - no need for `faraday` on PATH.
param(
    [string]$Api = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Submit-All($agentDir, $evals) {
    $agent = Join-Path $root "agents/$agentDir"
    foreach ($e in $evals) {
        Get-ChildItem -Directory (Join-Path $root "evals/$e/tasks") | ForEach-Object {
            $body = @{ task = $_.FullName; agent = $agent } | ConvertTo-Json -Compress
            Invoke-RestMethod -Method Post -Uri "$Api/api/runs" -ContentType "application/json" -Body $body | Out-Null
        }
        Write-Host "queued $agentDir x $e"
    }
}

# scripted-agent: real solver for shell-mini + datawrangle-mini, canned gaia-mini
Submit-All "scripted-agent" @("shell-mini", "gaia-mini", "datawrangle-mini")
# dummy-agent: only ever solves t001 - an honest low baseline
Submit-All "dummy-agent" @("shell-mini")

Write-Host "seeded - open $Api/#/"
