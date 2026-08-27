"""The agent container receives BYO env vars; the task-env container never does."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench.orchestrator.runner import LocalRunner
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
