from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from bench.exceptions import SpecError


def _safe_rel_path(p: str) -> str:
    path = Path(p)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe path: {p!r}")
    return path.as_posix()


class Limits(BaseModel):
    cpus: float = Field(default=1.0, gt=0, le=64)
    memory_mb: int = Field(default=512, ge=64, le=65536)
    timeout_s: int = Field(default=300, ge=1, le=7200)


class TaskFile(BaseModel):
    src: str
    dest: str

    @field_validator("dest")
    @classmethod
    def _safe_dest(cls, v: str) -> str:
        return _safe_rel_path(v)


class EnvSpec(BaseModel):
    image: str | None = None
    build: str | None = None

    @model_validator(mode="after")
    def _one_source(self) -> "EnvSpec":
        if not self.image and not self.build:
            raise ValueError("env requires either 'image' or 'build'")
        if self.image and self.build:
            raise ValueError("env cannot have both 'image' and 'build'")
        return self


class FileMatchGrader(BaseModel):
    type: Literal["file-match"]
    path: str
    expect: str
    mode: Literal["exact", "contains"] = "exact"

    @field_validator("path")
    @classmethod
    def _safe(cls, v: str) -> str:
        return _safe_rel_path(v)


class FileRegexGrader(BaseModel):
    type: Literal["file-regex"]
    path: str
    pattern: str

    @field_validator("path")
    @classmethod
    def _safe(cls, v: str) -> str:
        return _safe_rel_path(v)


GraderSpec = Annotated[
    Union[FileMatchGrader, FileRegexGrader],
    Field(discriminator="type"),
]


class TaskSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str
    description: str = ""
    version: str = "1"
    instruction: str = Field(min_length=1)
    env: EnvSpec = Field(default_factory=lambda: EnvSpec(image="python:3.12-slim"))
    files: list[TaskFile] = Field(default_factory=list)
    grader: GraderSpec
    limits: Limits = Field(default_factory=Limits)

    def task_json(self, input_files: list[str]) -> dict:
        return {
            "task_id": self.id,
            "name": self.name,
            "instruction": self.instruction,
            "input_files": input_files,
            "limits": {"timeout_s": self.limits.timeout_s},
        }


class AgentManifest(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str
    version: str = "0.1.0"
    image: str | None = None
    build: str | None = None
    tag: str | None = None
    entrypoint: list[str] | None = None

    @model_validator(mode="after")
    def _one_source(self) -> "AgentManifest":
        if not self.image and not self.build:
            raise ValueError("agent requires either 'image' or 'build'")
        if self.build and not self.tag:
            raise ValueError("agent with 'build' requires a 'tag'")
        return self


def load_yaml_model(path: Path, model_cls: type[BaseModel]):
    if not path.is_file():
        raise SpecError(f"not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise SpecError(f"invalid YAML in {path}: {e}") from e
    try:
        return model_cls.model_validate(data)
    except Exception as e:
        raise SpecError(f"invalid {model_cls.__name__} in {path}: {e}") from e


def load_task(task_dir: Path) -> tuple[TaskSpec, Path]:
    task_dir = Path(task_dir).resolve()
    spec = load_yaml_model(task_dir / "task.yaml", TaskSpec)
    for f in spec.files:
        if not (task_dir / f.src).is_file():
            raise SpecError(f"task file missing: {f.src}")
    return spec, task_dir


def load_agent(agent_dir: Path) -> tuple[AgentManifest, Path]:
    agent_dir = Path(agent_dir).resolve()
    manifest = load_yaml_model(agent_dir / "agent.yaml", AgentManifest)
    if manifest.build and not (agent_dir / manifest.build).exists():
        raise SpecError(f"build context missing: {manifest.build}")
    return manifest, agent_dir


def dump_task_json(spec: TaskSpec, workspace: Path, input_files: list[str]) -> None:
    (workspace / "task.json").write_text(
        json.dumps(spec.task_json(input_files), indent=2), encoding="utf-8"
    )
