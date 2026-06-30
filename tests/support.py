"""Shared helpers for the test suite."""

from __future__ import annotations

import bootstrap_tests  # noqa: F401

from pathlib import Path, PurePosixPath
from typing import Any

from speeddeploy.config import ConfigTemplate, DeploymentTarget as V1DeploymentTarget
from speeddeploy.v2.models import (
    ConnectionSpec,
    DatabaseSpec,
    DeploymentTarget,
    HealthcheckSpec,
    ProjectSpec,
    ProjectTemplate,
    ReleasesSpec,
)


class FakeExecutor:
    """Simple in-memory executor used by unit tests."""

    def __init__(
        self,
        *,
        dry_run: bool = False,
        capture_responses: list[str] | tuple[str, ...] | None = None,
        existing_paths: list[Path | str] | tuple[Path | str, ...] | None = None,
        empty_dirs: list[Path | str] | tuple[Path | str, ...] | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.commands: list[dict[str, Any]] = []
        self.captures: list[dict[str, Any]] = []
        self.writes: list[dict[str, Any]] = []
        self._capture_responses = list(capture_responses or [])
        self._existing_paths = {str(Path(path)) for path in (existing_paths or [])}
        self._empty_dirs = {str(Path(path)) for path in (empty_dirs or [])}

    def run(self, command, *, cwd=None, sudo=False, as_user=None):
        self.commands.append(
            {
                "command": [str(part) for part in command],
                "cwd": str(cwd) if cwd is not None else None,
                "sudo": sudo,
                "as_user": as_user,
            }
        )

    def capture(self, command, *, cwd=None, sudo=False, as_user=None):
        self.captures.append(
            {
                "command": [str(part) for part in command],
                "cwd": str(cwd) if cwd is not None else None,
                "sudo": sudo,
                "as_user": as_user,
            }
        )
        if self._capture_responses:
            return self._capture_responses.pop(0)
        return ""

    def write_text(self, path, content, *, sudo=False, mode="0644"):
        self.writes.append(
            {
                "path": str(path),
                "content": content,
                "sudo": sudo,
                "mode": mode,
            }
        )
        self._existing_paths.add(str(Path(path)))

    def kind(self) -> str:
        return "fake"

    def path_exists(self, path) -> bool:
        return str(Path(path)) in self._existing_paths

    def is_empty_dir(self, path) -> bool:
        key = str(Path(path))
        if key in self._empty_dirs:
            return True
        return key not in self._existing_paths


def make_v1_template() -> ConfigTemplate:
    return ConfigTemplate(
        project="demo",
        domain="demo.example.com",
        repo="https://example.com/demo.git",
        path=PurePosixPath("/srv/demo"),
        user="django",
        group="www-data",
        wsgi="config.wsgi:application",
        python="python3",
        workers=3,
        target=V1DeploymentTarget(),
    )


def make_v2_template() -> ProjectTemplate:
    return ProjectTemplate(
        project="demo",
        domain="demo.example.com",
        repo="https://example.com/demo.git",
        branch="main",
        path=PurePosixPath("/srv/demo"),
        user="django",
        group="www-data",
        wsgi="config.wsgi:application",
        python="python3",
        venv=PurePosixPath("/srv/demo/venv"),
        static_dir=PurePosixPath("/srv/demo/staticfiles"),
        media_dir=PurePosixPath("/srv/demo/media"),
        workers=3,
        target=DeploymentTarget(),
        connection=ConnectionSpec(),
        releases=ReleasesSpec(),
        healthcheck=HealthcheckSpec(),
        database=DatabaseSpec(),
    )
