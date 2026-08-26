from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from bench.exceptions import BenchError
from bench.orchestrator import LocalRunner
from bench.store.artifacts import RunLayout

app = typer.Typer(name="bench", no_args_is_help=True, add_completion=False)
run_app = typer.Typer(no_args_is_help=True)
app.add_typer(run_app, name="run")
console = Console()

STATUS_STYLES = {
    "passed": "bold green",
    "failed": "bold red",
    "agent_error": "bold yellow",
    "timeout": "bold magenta",
}


@run_app.command("local")
def run_local(
    task: Path = typer.Option(..., "--task", help="Task directory containing task.yaml"),
    agent: Path = typer.Option(
        Path("agents/dummy-agent"), "--agent", help="Agent directory containing agent.yaml"
    ),
) -> None:
    """Run one agent against one task entirely locally via Docker."""
    project_root = _find_project_root()
    try:
        runner = LocalRunner(project_root)
    except BenchError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2) from None
    with console.status("[bold blue]running…[/bold blue]"):
        try:
            result, run_dir = runner.run(task, agent)
        except BenchError as e:
            console.print(f"[red]run failed: {e}[/red]")
            raise typer.Exit(code=2) from None
    _print_result(result, run_dir)
    raise typer.Exit(code=0 if result.passed else 1)


def _find_project_root() -> Path:
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "bench").is_dir() and (candidate / "pyproject.toml").is_file():
            return candidate
    return cwd


def _print_result(result, run_dir: Path) -> None:
    style = STATUS_STYLES.get(result.status, "white")
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_row("run id", result.run_id)
    table.add_row("task", result.task_id)
    table.add_row("agent", result.agent_id)
    table.add_row("status", f"[{style}]{result.status}[/{style}]")
    table.add_row("score", f"{result.score:.1f}")
    table.add_row("duration", f"{result.duration_s:.1f}s")
    table.add_row("detail", result.detail)
    table.add_row("artifacts", str(run_dir))
    console.print(Panel(table, title="bench run", expand=False))


@app.command("runs")
def runs() -> None:
    """List recent local runs."""
    project_root = _find_project_root()
    layout_parent = project_root / "runs"
    if not layout_parent.exists():
        console.print("no runs yet")
        return
    table = Table(title="recent runs")
    table.add_column("run id")
    table.add_column("task")
    table.add_column("agent")
    table.add_column("status")
    table.add_column("score", justify="right")
    for run_dir in sorted(layout_parent.iterdir())[-15:]:
        result_file = run_dir / "result.json"
        if not result_file.is_file():
            continue
        import json

        data = json.loads(result_file.read_text(encoding="utf-8"))
        style = STATUS_STYLES.get(data["status"], "white")
        table.add_row(
            data["run_id"],
            data["task_id"],
            data["agent_id"],
            f"[{style}]{data['status']}[/{style}]",
            f"{data['score']:.1f}",
        )
    console.print(table)


@app.command("db-init")
def db_init() -> None:
    """Create database tables."""
    from bench.store.db import init_db

    try:
        init_db()
    except Exception as e:
        console.print(f"[red]db init failed (is postgres up?): {e}[/red]")
        raise typer.Exit(code=2) from None
    console.print("[green]database initialized[/green]")


@app.command("serve")
def serve(
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Start the API server (serves web/dist when built)."""
    import uvicorn

    from bench.config import API_HOST

    uvicorn.run("bench.api.main:app", host=API_HOST, port=port)


@app.command("worker")
def worker() -> None:
    """Start a worker that consumes the run queue."""
    from bench.orchestrator.worker import main as worker_main

    worker_main()


@app.command("submit")
def submit(
    task: Path = typer.Option(..., "--task", help="Task directory containing task.yaml"),
    agent: Path = typer.Option(..., "--agent", help="Agent directory containing agent.yaml"),
    api: str = typer.Option("http://127.0.0.1:8000", "--api"),
) -> None:
    """Submit a run through the API queue (requires server + worker)."""
    import httpx

    payload = {
        "task": str(task.expanduser().resolve()),
        "agent": str(agent.expanduser().resolve()),
    }
    try:
        resp = httpx.post(f"{api}/api/runs", json=payload, timeout=30)
    except httpx.HTTPError as e:
        console.print(f"[red]could not reach API at {api}: {e}[/red]")
        raise typer.Exit(code=2) from None
    if resp.status_code >= 400:
        console.print(f"[red]submit failed ({resp.status_code}): {resp.text}[/red]")
        raise typer.Exit(code=2) from None
    data = resp.json()
    console.print(
        Panel(
            f"run id   {data['run_id']}\n"
            f"status   {data['status']}\n"
            f"api      {api}/api/runs/{data['run_id']}\n"
            f"ui       {api}/#/runs/{data['run_id']}",
            title="submitted",
            expand=False,
        )
    )


if __name__ == "__main__":
    app()
