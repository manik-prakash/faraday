from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from faraday.env_policy import sanitize_agent_env
from faraday.exceptions import FaradayError
from faraday.orchestrator import LocalRunner

app = typer.Typer(name="faraday", no_args_is_help=True, add_completion=False)
run_app = typer.Typer(no_args_is_help=True)
eval_app = typer.Typer(no_args_is_help=True)
app.add_typer(run_app, name="run")
app.add_typer(eval_app, name="eval")
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
    env: list[str] = typer.Option(
        [], "--env", help="KEY=VALUE passed to the agent container (repeatable)"
    ),
    env_file: Path | None = typer.Option(
        None, "--env-file", help="dotenv-style file of KEY=VALUE lines for the agent"
    ),
) -> None:
    """Run one agent against one task entirely locally via Docker."""
    project_root = _find_project_root()
    try:
        agent_env = _collect_env(env, env_file)
    except (ValueError, FaradayError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2) from None
    try:
        runner = LocalRunner(project_root)
    except FaradayError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2) from None
    with console.status("[bold blue]running…[/bold blue]"):
        try:
            result, run_dir = runner.run(task, agent, env=agent_env or None)
        except FaradayError as e:
            console.print(f"[red]run failed: {e}[/red]")
            raise typer.Exit(code=2) from None
    _print_result(result, run_dir)
    raise typer.Exit(code=0 if result.passed else 1)


def _parse_pair(item: str) -> tuple[str, str]:
    if "=" not in item:
        raise ValueError(f"expected KEY=VALUE, got {item!r}")
    key, value = item.split("=", 1)
    return key.strip(), value


def _collect_env(pairs: list[str], env_file: Path | None) -> dict[str, str]:
    """Merge --env-file then inline --env KEY=VALUE pairs, then apply the allowlist."""
    env: dict[str, str] = {}
    if env_file is not None:
        for raw in Path(env_file).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, value = _parse_pair(line)
            env[key] = value
    for item in pairs or []:
        key, value = _parse_pair(item)
        env[key] = value
    return sanitize_agent_env(env)


def _find_project_root() -> Path:
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "faraday").is_dir() and (candidate / "pyproject.toml").is_file():
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
    console.print(Panel(table, title="faraday run", expand=False))


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
def db_init(
    reset: bool = typer.Option(False, "--reset", help="Drop all tables first"),
) -> None:
    """Create database tables."""
    from faraday.store.db import init_db

    try:
        if reset:
            from faraday.store.db import Base, get_engine

            Base.metadata.drop_all(get_engine())
            console.print("[yellow]dropped existing tables[/yellow]")
        init_db()
    except Exception as e:
        console.print(f"[red]db init failed (is postgres up?): {e}[/red]")
        raise typer.Exit(code=2) from None
    console.print("[green]database initialized[/green]")


@eval_app.command("list")
def eval_list() -> None:
    """Sync every task under evals/ into the registry and list the evals."""
    from faraday.config import EVALS_DIR
    from faraday.evals_io import iter_task_dirs, sync_task_registry
    from faraday.store.db import get_sessionmaker

    try:
        SessionLocal = get_sessionmaker()
        with SessionLocal() as session:
            added = sync_task_registry(session, EVALS_DIR)
            session.commit()
    except Exception as e:  # surfaced to the user
        console.print(f"[red]registry sync failed (is postgres up?): {e}[/red]")
        raise typer.Exit(code=2) from None

    counts: dict[str, int] = {}
    for d in iter_task_dirs(EVALS_DIR):
        counts[d.parent.parent.name] = counts.get(d.parent.parent.name, 0) + 1
    table = Table(title=f"evals ({added} newly registered)")
    table.add_column("eval")
    table.add_column("tasks", justify="right")
    for name in sorted(counts):
        table.add_row(name, str(counts[name]))
    console.print(table)


@eval_app.command("add")
def eval_add(
    path: Path = typer.Argument(..., help="A .zip archive or a directory containing tasks/"),
    name: str = typer.Option(..., "--name", help="Eval name (lowercase, digits, hyphens)"),
    no_shell_graders: bool = typer.Option(
        False, "--no-shell-graders", help="Reject script-exit graders in this eval"
    ),
) -> None:
    """Install a bring-your-own-eval into evals/<name>/ and register its tasks."""
    from faraday.config import EVALS_DIR
    from faraday.evals_io import install_eval_archive, pack_eval_dir, sync_task_registry
    from faraday.store.db import get_sessionmaker

    path = path.expanduser()
    data = pack_eval_dir(path) if path.is_dir() else path.read_bytes()
    try:
        ids = install_eval_archive(
            data, name, EVALS_DIR, allow_script_graders=not no_shell_graders
        )
    except FaradayError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2) from None
    try:
        SessionLocal = get_sessionmaker()
        with SessionLocal() as session:
            sync_task_registry(session, EVALS_DIR)
            session.commit()
    except Exception as e:  # registry is best-effort here
        console.print(
            f"[yellow]installed {len(ids)} task(s); registry sync failed: {e}[/yellow]"
        )
        raise typer.Exit(code=0) from None
    console.print(
        f"[green]installed eval '{name}' with {len(ids)} task(s): {', '.join(ids)}[/green]"
    )


@app.command("serve")
def serve(
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Start the API server (serves web/dist when built)."""
    import uvicorn

    from faraday.config import API_HOST

    uvicorn.run("faraday.api.main:app", host=API_HOST, port=port)


@app.command("worker")
def worker() -> None:
    """Start a worker that consumes the run queue."""
    from faraday.orchestrator.worker import main as worker_main

    worker_main()


@app.command("submit")
def submit(
    task: Path = typer.Option(..., "--task", help="Task directory containing task.yaml"),
    agent: Path = typer.Option(..., "--agent", help="Agent directory containing agent.yaml"),
    api: str = typer.Option("http://127.0.0.1:8000", "--api"),
    env: list[str] = typer.Option(
        [], "--env", help="KEY=VALUE forwarded to the agent container (repeatable)"
    ),
    env_file: Path | None = typer.Option(
        None, "--env-file", help="dotenv-style file of KEY=VALUE lines for the agent"
    ),
) -> None:
    """Submit a run through the API queue (requires server + worker)."""
    import httpx

    try:
        agent_env = _collect_env(env, env_file)
    except (ValueError, FaradayError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2) from None

    payload = {
        "task": str(task.expanduser().resolve()),
        "agent": str(agent.expanduser().resolve()),
    }
    if agent_env:
        payload["env"] = agent_env
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
