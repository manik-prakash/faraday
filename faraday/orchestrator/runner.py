from __future__ import annotations

import json
import shutil
import stat
import tempfile
import time
from pathlib import Path

import docker
from docker.errors import APIError, DockerException, ImageNotFound
from requests.exceptions import ReadTimeout

from faraday.exceptions import DockerUnavailable, RunnerError
from faraday.grading import run_grader
from faraday.grading.base import GraderContext, GraderOutcome
from faraday.spec import AgentManifest, TaskSpec, dump_task_json, load_agent, load_task
from faraday.store.artifacts import RunLayout, RunResult, make_run_id, utcnow_iso

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_AGENT_ERROR = "agent_error"
STATUS_TIMEOUT = "timeout"

# Applied to every container we launch: strip capabilities, block privilege
# escalation, cap process count, read-only rootfs with a small writable /tmp.
# The task workspace stays writable via its own `rw` bind mount.
_HARDENING: dict = {
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges"],
    "pids_limit": 256,
    "read_only": True,
    "tmpfs": {"/tmp": "rw,size=64m"},
}
# uid:gid the agent runs as (nobody) — it must not run as root inside the sandbox.
_AGENT_USER = "65534:65534"


def _make_world_writable(root: Path) -> None:
    """So a non-root agent can write into the bind-mounted workspace."""
    add = stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH
    for path in (root, *root.rglob("*")):
        try:
            mode = path.stat().st_mode | add
            if path.is_dir():
                mode |= stat.S_IXGRP | stat.S_IXOTH
            path.chmod(mode)
        except OSError:
            pass


def _client() -> docker.DockerClient:
    try:
        client = docker.from_env()
        client.ping()
        return client
    except (DockerException, APIError) as e:
        raise DockerUnavailable(
            f"Docker is not reachable (is Docker Desktop running?): {e}"
        ) from e


def _mount_path(p: Path) -> str:
    return p.as_posix()


def _ensure_image(
    client: docker.DockerClient,
    image: str | None,
    build_context: Path | None,
    tag: str | None,
) -> str:
    if build_context is not None and tag is not None:
        try:
            client.images.build(path=str(build_context), tag=tag, rm=True)
        except APIError as e:
            raise RunnerError(f"image build failed for {tag}: {e}") from e
        return tag
    assert image is not None
    try:
        client.images.get(image)
    except ImageNotFound:
        try:
            client.images.pull(image)
        except APIError as e:
            raise RunnerError(f"image pull failed for {image}: {e}") from e
    return image


def _read_usage(workspace: Path) -> dict | None:
    path = workspace / "output" / "usage.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    model = data.get("model")
    input_tokens = data.get("input_tokens")
    output_tokens = data.get("output_tokens")
    if not isinstance(model, str):
        return None
    for count in (input_tokens, output_tokens):
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            return None
    return {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def _grade_safely(grader_spec, ctx: GraderContext) -> GraderOutcome:
    """Run the grader; never let a container/infra crash skip result.save()."""
    try:
        return run_grader(grader_spec, ctx)
    except Exception as e:
        return GraderOutcome(
            score=0.0, passed=False, detail=f"grader crashed: {type(e).__name__}: {e}"
        )


def _wait_for_agent(agent, timeout_s: int) -> tuple[bool, str | None, int]:
    """Wait for the agent container; tell a real timeout apart from a Docker error.

    Returns ``(timed_out, wait_error, exit_code)``.
    """
    try:
        wait_status = agent.wait(timeout=timeout_s)
        return False, None, int(wait_status.get("StatusCode", -1))
    except ReadTimeout:
        try:
            agent.kill()
        except APIError:
            pass
        return True, None, -1
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", -1


def _capture_agent_log(agent) -> bytes:
    """Fetch the agent's log; a dead/removed container must not raise here."""
    try:
        return agent.logs(stdout=True, stderr=True, timestamps=True)
    except (APIError, DockerException) as e:
        return f"[faraday] could not fetch agent logs: {type(e).__name__}: {e}\n".encode()


class LocalRunner:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.client = _client()

    def run(
        self,
        task_dir: Path,
        agent_dir: Path,
        run_id: str | None = None,
        env: dict[str, str] | None = None,
    ) -> tuple[RunResult, Path]:
        spec, tdir = load_task(task_dir)
        manifest, adir = load_agent(agent_dir)

        if run_id is None:
            run_id = make_run_id()
        layout = RunLayout(self.project_root, run_id).create()

        task_ref = _ensure_image(
            self.client,
            spec.env.image,
            tdir / spec.env.build if spec.env.build else None,
            None if spec.env.image else f"faraday/task-{spec.id}:{spec.version}",
        )
        agent_ref = _ensure_image(
            self.client,
            manifest.image,
            adir / manifest.build if manifest.build else None,
            manifest.tag,
        )

        started = utcnow_iso()
        t0 = time.monotonic()
        staging = Path(tempfile.mkdtemp(prefix=f"faraday-{run_id}-"))
        workspace = staging / "workspace"
        (workspace / "input").mkdir(parents=True)
        (workspace / "output").mkdir(parents=True)

        input_files: list[str] = []
        for f in spec.files:
            dest = workspace / "input" / f.dest
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tdir / f.src, dest)
            input_files.append(f.dest)
        dump_task_json(spec, workspace, input_files)
        shutil.copy2(tdir / "task.yaml", layout.run_dir / "task.yaml")
        _make_world_writable(workspace)

        net = self.client.networks.create(f"faraday-net-{run_id}", driver="bridge")
        task_env = None
        agent = None
        timed_out = False
        wait_error: str | None = None
        rc = -1
        try:
            task_env = self._start_task_env(task_ref, workspace, run_id, spec)
            agent = self._start_agent(
                agent_ref, workspace, run_id, spec, manifest, net.id, env=env
            )
            timed_out, wait_error, rc = _wait_for_agent(agent, spec.limits.timeout_s)
            (layout.logs_dir / "agent.log").write_bytes(_capture_agent_log(agent))

            usage = _read_usage(workspace)
            outcome = _grade_safely(
                spec.grader, self._grader_context(spec, workspace, tdir, task_env)
            )
            _copy_tree(workspace / "output", layout.output_dir)
        finally:
            for container in (agent, task_env):
                if container is not None:
                    try:
                        container.remove(force=True)
                    except APIError:
                        pass
            try:
                net.remove()
            except APIError:
                pass

        if wait_error:
            status = STATUS_AGENT_ERROR
            detail = f"agent container error: {wait_error}; {outcome.detail}"
        elif timed_out:
            status = STATUS_TIMEOUT
            detail = f"agent exceeded {spec.limits.timeout_s}s limit; {outcome.detail}"
        elif rc != 0:
            status = STATUS_AGENT_ERROR
            detail = f"agent exited with code {rc}; see runs/{run_id}/logs/agent.log"
        elif outcome.passed:
            status = STATUS_PASSED
            detail = outcome.detail
        else:
            status = STATUS_FAILED
            detail = outcome.detail

        finished = utcnow_iso()
        duration = round(time.monotonic() - t0, 3)
        result = RunResult(
            run_id=run_id,
            task_id=spec.id,
            agent_id=manifest.id,
            status=status,
            score=outcome.score,
            passed=outcome.passed,
            duration_s=duration,
            detail=detail,
            started_at=started,
            finished_at=finished,
            meta={
                "images": {"task": task_ref, "agent": agent_ref},
                "grader": spec.grader.model_dump(),
                "limits": spec.limits.model_dump(),
                "exit_code": rc,
                "env_keys": sorted(env or {}),
            },
            usage=usage,
        )
        result.save(layout.run_dir)
        shutil.rmtree(staging, ignore_errors=True)
        return result, layout.run_dir

    def _limits_kwargs(self, spec: TaskSpec) -> dict:
        return {
            "mem_limit": f"{spec.limits.memory_mb}m",
            "nano_cpus": int(spec.limits.cpus * 1e9),
        }

    def _grader_context(
        self, spec: TaskSpec, workspace: Path, task_dir: Path, task_container
    ) -> GraderContext:
        return GraderContext(
            workspace=workspace,
            task_dir=task_dir,
            docker_client=self.client,
            task_container=task_container,
            timeout_s=spec.limits.timeout_s,
        )

    def _start_task_env(
        self, image_ref: str, workspace: Path, run_id: str, spec: TaskSpec
    ):
        try:
            return self.client.containers.run(
                image_ref,
                command="sleep infinity",
                detach=True,
                name=f"{run_id}-taskenv",
                network_mode="none",
                volumes={
                    _mount_path(workspace): {"bind": "/task", "mode": "rw"}
                },
                **_HARDENING,
                **self._limits_kwargs(spec),
            )
        except APIError as e:
            raise RunnerError(
                f"failed to start task-env container (check Docker Desktop file "
                f"sharing for the temp drive): {e}"
            ) from e

    def _start_agent(
        self,
        image_ref: str,
        workspace: Path,
        run_id: str,
        spec: TaskSpec,
        manifest: AgentManifest,
        network_id: str,
        env: dict[str, str] | None = None,
    ):
        kwargs: dict = {
            "detach": True,
            "name": f"{run_id}-agent",
            "network": network_id,
            "working_dir": "/task",
            "user": _AGENT_USER,
            "volumes": {_mount_path(workspace): {"bind": "/task", "mode": "rw"}},
            **_HARDENING,
            **self._limits_kwargs(spec),
        }
        if env:
            kwargs["environment"] = dict(env)
        if manifest.entrypoint:
            kwargs["entrypoint"] = list(manifest.entrypoint)
        try:
            return self.client.containers.run(image_ref, **kwargs)
        except APIError as e:
            raise RunnerError(f"failed to start agent container: {e}") from e
