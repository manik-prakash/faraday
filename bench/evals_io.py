"""Bring-your-own-eval: install a task archive and sync the task registry."""

from __future__ import annotations

import io
import re
import shutil
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

from bench.exceptions import SpecError
from bench.spec import load_task

_EVAL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
MAX_MEMBERS = 500


def pack_eval_dir(src: Path) -> bytes:
    """Zip a directory (expected to contain ``tasks/<id>/…``) into archive bytes."""
    src = Path(src)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(src).as_posix())
    return buf.getvalue()


def iter_task_dirs(evals_root: Path) -> Iterator[Path]:
    """Yield every ``evals/<bench>/tasks/<task-id>`` directory under ``evals_root``."""
    for bench_dir in sorted(p for p in Path(evals_root).iterdir() if p.is_dir()):
        tasks = bench_dir / "tasks"
        if not tasks.is_dir():
            continue
        yield from (d for d in sorted(tasks.iterdir()) if (d / "task.yaml").is_file())


def _safe_extract(data: bytes, dest: Path) -> None:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise SpecError(f"archive too large (> {MAX_ARCHIVE_BYTES} bytes)")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise SpecError(f"not a valid zip archive: {e}") from e
    names = zf.namelist()
    if len(names) > MAX_MEMBERS:
        raise SpecError(f"archive has too many entries (> {MAX_MEMBERS})")
    dest_resolved = dest.resolve()
    for name in names:
        target = (dest / name).resolve()
        if not target.is_relative_to(dest_resolved):
            raise SpecError(f"archive entry escapes destination: {name!r}")
    zf.extractall(dest)


def install_eval_archive(
    data: bytes, name: str, evals_root: Path, *, allow_script_graders: bool = False
) -> list[str]:
    """Extract a ``tasks/<id>/…`` zip into ``evals_root/<name>/`` and validate it.

    Returns the installed task ids. Raises :class:`SpecError` (leaving nothing
    behind) if the name is bad, the archive is unsafe, it contains no task, any
    ``task.yaml`` fails to load, or — unless ``allow_script_graders`` — a task
    ships a ``script-exit`` (arbitrary shell) grader.
    """
    if not _EVAL_NAME.match(name):
        raise SpecError(f"invalid eval name: {name!r} (use lowercase letters, digits, hyphens)")

    staging = Path(tempfile.mkdtemp(prefix=f"bench-eval-{name}-"))
    try:
        _safe_extract(data, staging)
        task_root = staging / "tasks"
        task_dirs = (
            [d for d in sorted(task_root.iterdir()) if (d / "task.yaml").is_file()]
            if task_root.is_dir()
            else []
        )
        if not task_dirs:
            raise SpecError("archive contains no tasks/<id>/task.yaml entries")
        ids: list[str] = []
        for d in task_dirs:
            try:
                spec, _ = load_task(d)
            except SpecError as e:
                raise SpecError(f"task '{d.name}': {e}") from e
            if spec.grader.type == "script-exit" and not allow_script_graders:
                raise SpecError(
                    f"task '{d.name}' ships a script-exit (shell) grader; this instance "
                    "does not accept shell graders in uploaded evals "
                    "(set BENCH_ALLOW_UPLOADED_SCRIPT_GRADERS=1 to allow)"
                )
            ids.append(spec.id)

        final = Path(evals_root) / name
        if final.exists():
            shutil.rmtree(final)
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(task_root, final / "tasks")
        return ids
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def sync_task_registry(session, evals_root: Path) -> int:
    """Upsert a ``Task`` row for every task dir under ``evals_root``.

    Returns the number of rows inserted (existing rows are left untouched).
    """
    from bench.store.db import Task

    inserted = 0
    for task_dir in iter_task_dirs(evals_root):
        spec, tdir = load_task(task_dir)
        if session.query(Task).filter_by(slug=spec.id).one_or_none() is not None:
            continue
        session.add(
            Task(
                slug=spec.id,
                name=spec.name,
                description=spec.description,
                bench_name=tdir.parent.parent.name,
                version=spec.version,
                instruction=spec.instruction,
                grader=spec.grader.model_dump(),
                limits=spec.limits.model_dump(),
            )
        )
        inserted += 1
    return inserted
