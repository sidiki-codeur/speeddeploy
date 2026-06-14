"""Configuration loading and validation for SpeedDeploy."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when a project configuration file is invalid."""


REQUIRED_FIELDS = (
    "project",
    "domain",
    "repo",
    "path",
    "user",
    "group",
    "wsgi",
    "python",
    "venv",
    "static_dir",
    "media_dir",
    "workers",
)


@dataclass(slots=True, frozen=True)
class ProjectConfig:
    """Normalized project configuration."""

    project: str
    domain: str
    repo: str
    path: Path
    user: str
    group: str
    wsgi: str
    python: str
    venv: Path
    static_dir: Path
    media_dir: Path
    workers: int
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def service_name(self) -> str:
        return self.project

    @property
    def venv_bin(self) -> Path:
        return self.venv / "bin"

    @property
    def manage_py(self) -> Path:
        return self.path / "manage.py"


def resolve_config_path(project: str | Path, projects_dir: Path | None = None) -> Path:
    """Resolve a project name or file path to a YAML file."""
    candidate = Path(project)
    if candidate.suffix.lower() in {".yml", ".yaml"} or candidate.exists():
        return candidate

    base_dir = projects_dir or Path.cwd() / "projects"
    return base_dir / f"{candidate.name}.yml"


def _flatten_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Support both flat YAML and the older nested `project:` mapping."""
    project_block = data.get("project")
    if isinstance(project_block, dict):
        merged = dict(project_block)
        merged.update({key: value for key, value in data.items() if key != "project"})
        if "project" not in merged and "name" in merged:
            merged["project"] = merged["name"]
        return merged
    return data


def load_config(project: str | Path, projects_dir: Path | None = None) -> ProjectConfig:
    """Load, validate and normalize a project YAML file."""
    config_path = resolve_config_path(project, projects_dir=projects_dir)
    if not config_path.exists():
        raise ConfigError(f"Fichier de configuration introuvable: {config_path}")

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError("Le fichier YAML doit contenir une mapping.")

    data = _flatten_mapping(data)
    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        joined = ", ".join(missing)
        raise ConfigError(f"Champ(s) manquant(s) dans le YAML: {joined}")

    try:
        workers = int(data["workers"])
    except (TypeError, ValueError) as exc:
        raise ConfigError("Le champ `workers` doit être un entier.") from exc
    if workers < 1:
        raise ConfigError("Le champ `workers` doit être supérieur ou égal à 1.")

    known_keys = set(REQUIRED_FIELDS) | {"project_root", "ssl", "manage_py"}
    extras = {key: value for key, value in data.items() if key not in known_keys}

    return ProjectConfig(
        project=str(data["project"]),
        domain=str(data["domain"]),
        repo=str(data["repo"]),
        path=Path(data["path"]).expanduser(),
        user=str(data["user"]),
        group=str(data["group"]),
        wsgi=str(data["wsgi"]),
        python=str(data["python"]),
        venv=Path(data["venv"]).expanduser(),
        static_dir=Path(data["static_dir"]).expanduser(),
        media_dir=Path(data["media_dir"]).expanduser(),
        workers=workers,
        extras=extras,
    )
