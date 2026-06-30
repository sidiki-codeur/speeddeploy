"""Persistent deployment state for V2 projects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .executor import Executor, ExecutorError


STATE_FILE_NAME = "state.json"


@dataclass(frozen=True, slots=True)
class DeploymentState:
    """Serialized snapshot of the last deployment attempt."""

    project: str
    branch: str
    strategy: str
    status: str
    last_deploy_at: str
    current_release: str | None = None
    previous_release: str | None = None
    last_commit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "branch": self.branch,
            "strategy": self.strategy,
            "status": self.status,
            "last_deploy_at": self.last_deploy_at,
            "current_release": self.current_release,
            "previous_release": self.previous_release,
            "last_commit": self.last_commit,
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "DeploymentState":
        return cls(
            project=str(data.get("project", "")),
            branch=str(data.get("branch", "")),
            strategy=str(data.get("strategy", "")),
            status=str(data.get("status", "")),
            last_deploy_at=str(data.get("last_deploy_at", "")),
            current_release=str(data["current_release"]).strip() if data.get("current_release") else None,
            previous_release=str(data["previous_release"]).strip() if data.get("previous_release") else None,
            last_commit=str(data["last_commit"]).strip() if data.get("last_commit") else None,
        )


def state_file(state_dir: Path) -> Path:
    return state_dir / STATE_FILE_NAME


def read_state(executor: Executor, state_dir: Path) -> DeploymentState | None:
    path = state_file(state_dir)
    if not executor.path_exists(path):
        return None
    try:
        payload = executor.capture(["cat", str(path)], sudo=True)
    except ExecutorError:
        return None
    if not payload.strip():
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    try:
        return DeploymentState.from_mapping(data)
    except (TypeError, ValueError, KeyError):
        return None


def write_state(executor: Executor, state_dir: Path, state: DeploymentState) -> None:
    payload = json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    executor.run(["mkdir", "-p", str(state_dir)], sudo=True)
    executor.write_text(state_file(state_dir), payload, sudo=True, mode="0640")
