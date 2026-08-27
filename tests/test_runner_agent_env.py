"""The agent container receives BYO env vars; the task-env container never does."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench.orchestrator.runner import LocalRunner, _ensure_image
from bench.spec import AgentManifest, TaskSpec


class _FakeContainers:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, image, **kwargs):
        self.calls.append({"image": image, **kwargs})
        return object()


class _FakeClient:
    def __init__(self) -> None:
        self.containers = _FakeContainers()


@pytest.fixture
def runner() -> LocalRunner:
    r = object.__new__(LocalRunner)
    r.client = _FakeClient()
    return r


def _spec() -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "id": "t001-hello",
            "name": "x",
            "instruction": "go",
            "grader": {"type": "file-match", "path": "output/r.txt", "expect": "1"},
        }
    )


def _manifest() -> AgentManifest:
    return AgentManifest(id="a", name="A", image="img:latest")


def test_agent_container_gets_env(runner: LocalRunner, tmp_path: Path) -> None:
    runner._start_agent(
        "agent:img", tmp_path, "rid", _spec(), _manifest(), "net", env={"OPENAI_API_KEY": "sk-x"}
    )
    call = runner.client.containers.calls[-1]
    assert call["environment"] == {"OPENAI_API_KEY": "sk-x"}


def test_agent_container_without_env_passes_none_or_empty(runner: LocalRunner, tmp_path: Path) -> None:
    runner._start_agent("agent:img", tmp_path, "rid", _spec(), _manifest(), "net", env=None)
    call = runner.client.containers.calls[-1]
    assert not call.get("environment")


def test_task_env_container_never_gets_env(runner: LocalRunner, tmp_path: Path) -> None:
    runner._start_task_env("task:img", tmp_path, "rid", _spec())
    call = runner.client.containers.calls[-1]
    assert "environment" not in call


# --- sandbox hardening -------------------------------------------------------

def test_agent_container_is_locked_down(runner: LocalRunner, tmp_path: Path) -> None:
    runner._start_agent("agent:img", tmp_path, "rid", _spec(), _manifest(), "net")
    call = runner.client.containers.calls[-1]
    assert call["cap_drop"] == ["ALL"]
    assert "no-new-privileges" in call["security_opt"]
    assert call["pids_limit"] and call["pids_limit"] <= 512
    assert call["read_only"] is True
    assert "/tmp" in call["tmpfs"]
    assert str(call["user"]).startswith("65534")  # runs as nobody, not root


def test_task_env_container_is_locked_down(runner: LocalRunner, tmp_path: Path) -> None:
    runner._start_task_env("task:img", tmp_path, "rid", _spec())
    call = runner.client.containers.calls[-1]
    assert call["cap_drop"] == ["ALL"]
    assert "no-new-privileges" in call["security_opt"]
    assert call["pids_limit"]
    assert call["network_mode"] == "none"  # unchanged: task env has no network


def test_agent_still_gets_task_bind_mount_writable(runner: LocalRunner, tmp_path: Path) -> None:
    # read-only rootfs must not stop the agent writing results to /task
    runner._start_agent("agent:img", tmp_path, "rid", _spec(), _manifest(), "net")
    call = runner.client.containers.calls[-1]
    (bind,) = call["volumes"].values()
    assert bind == {"bind": "/task", "mode": "rw"}


# --- bring-your-own-agent by prebuilt image --------------------------------

class _FakeImages:
    def __init__(self, present: bool) -> None:
        self.present = present
        self.built = False
        self.pulled: list[str] = []

    def get(self, ref):
        from docker.errors import ImageNotFound

        if self.present:
            return object()
        raise ImageNotFound(ref)

    def build(self, **kw):
        self.built = True
        return object(), []

    def pull(self, ref):
        self.pulled.append(ref)
        return object()


class _ImgClient:
    def __init__(self, present: bool) -> None:
        self.images = _FakeImages(present)


def test_prebuilt_image_is_used_as_is_never_built() -> None:
    client = _ImgClient(present=True)
    ref = _ensure_image(client, "ghcr.io/someone/agent:v1", None, None)
    assert ref == "ghcr.io/someone/agent:v1"
    assert client.images.built is False
    assert client.images.pulled == []


def test_missing_prebuilt_image_is_pulled_not_built() -> None:
    client = _ImgClient(present=False)
    ref = _ensure_image(client, "ghcr.io/someone/agent:v1", None, None)
    assert ref == "ghcr.io/someone/agent:v1"
    assert client.images.built is False
    assert client.images.pulled == ["ghcr.io/someone/agent:v1"]
