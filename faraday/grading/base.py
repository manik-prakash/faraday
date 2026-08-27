from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faraday.spec import GraderSpec


@dataclass
class GraderOutcome:
    score: float
    passed: bool
    detail: str


@dataclass
class GraderContext:
    workspace: Path
    task_dir: Path
    docker_client: Any = None
    task_container: Any = None
    timeout_s: int = 60


class BaseGrader(ABC):
    def __init__(self, spec: GraderSpec) -> None:
        self.spec = spec

    @abstractmethod
    def grade(self, ctx: GraderContext) -> GraderOutcome: ...
