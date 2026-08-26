from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from bench.spec import GraderSpec


@dataclass
class GraderOutcome:
    score: float
    passed: bool
    detail: str


class BaseGrader(ABC):
    def __init__(self, spec: GraderSpec) -> None:
        self.spec = spec

    @abstractmethod
    def grade(self, workspace: Path) -> GraderOutcome: ...
