"""Configuration loading and validation for SpeedDeploy."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .paths import as_posix_text


class ConfigError(ValueError):
    """Raised when a project configuration file is invalid."""


@dataclass(frozen=True, slots=True)
class DeploymentTarget:
    """Deployment target hints for future multi-platform support."""

    os: str = "linux"
    init_system: str = "systemd"
    web_server: str = "apache"
    app_server: str = "gunicorn"
    ssl_provider: str = "certbot"
    package_manager: str = "apt"


@dataclass(frozen=True, slots=True)
class ConfigTemplate:
    """Values used to scaffold a new project configuration file."""

    project: str
    domain: str
    repo: str
    path: Path
    user: str = "django"
    group: str = "www-data"
    wsgi: str = "config.wsgi:application"
    python: str = "python3"
    venv: Path | None = None
    static_dir: Path | None = None
    media_dir: Path | None = None
    workers: int = 3
    target: DeploymentTarget = field(default_factory=DeploymentTarget)

    def to_yaml_data(self) -> dict[str, Any]:
        """Serialize the template to a YAML-friendly mapping."""
        venv = self.venv or (self.path / "venv")
        static_dir = self.static_dir or (self.path / "staticfiles")
        media_dir = self.media_dir or (self.path / "media")
        return {
            "project": self.project,
            "domain": self.domain,
            "repo": self.repo,
            "path": as_posix_text(self.path),
            "user": self.user,
            "group": self.group,
            "wsgi": self.wsgi,
            "python": self.python,
            "venv": as_posix_text(venv),
            "static_dir": as_posix_text(static_dir),
            "media_dir": as_posix_text(media_dir),
            "workers": self.workers,
            "target": {
                "os": self.target.os,
                "init_system": self.target.init_system,
                "web_server": self.target.web_server,
                "app_server": self.target.app_server,
                "ssl_provider": self.target.ssl_provider,
                "package_manager": self.target.package_manager,
            },
        }


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
    target: DeploymentTarget = field(default_factory=DeploymentTarget)
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

    base_dir = projects_dir or (Path.cwd() / "projects")
    return base_dir / f"{candidate.name}.yml"


def _flatten_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Support both flat YAML and the legacy nested `project:` mapping."""
    project_block = data.get("project")
    if isinstance(project_block, dict):
        merged = dict(project_block)
        merged.update({key: value for key, value in data.items() if key != "project"})
        if "project" not in merged and "name" in merged:
            merged["project"] = merged["name"]
        return merged
    return data


def _extract_target(data: dict[str, Any]) -> tuple[DeploymentTarget, dict[str, Any]]:
    """Extract target hints and return the remaining mapping."""
    target_block = data.get("target")
    target_data = dict(target_block) if isinstance(target_block, dict) else {}

    target = DeploymentTarget(
        os=str(target_data.get("os", data.get("os", "linux"))),
        init_system=str(target_data.get("init_system", data.get("init_system", "systemd"))),
        web_server=str(target_data.get("web_server", data.get("web_server", "apache"))),
        app_server=str(target_data.get("app_server", data.get("app_server", "gunicorn"))),
        ssl_provider=str(target_data.get("ssl_provider", data.get("ssl_provider", "certbot"))),
        package_manager=str(target_data.get("package_manager", data.get("package_manager", "apt"))),
    )

    remaining = {key: value for key, value in data.items() if key != "target"}
    return target, remaining


def render_config_template(template: ConfigTemplate) -> str:
    """Render a project configuration template as YAML."""
    yaml_text = yaml.safe_dump(
        template.to_yaml_data(),
        sort_keys=False,
        default_flow_style=False,
    ).rstrip()
    return f"{yaml_text}\n"


def load_config(project: str | Path, projects_dir: Path | None = None) -> ProjectConfig:
    """Load, validate and normalize a project YAML file."""
    config_path = resolve_config_path(project, projects_dir=projects_dir)
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError("The YAML file must contain a mapping.")

    data = _flatten_mapping(data)
    target, data = _extract_target(data)

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        joined = ", ".join(missing)
        raise ConfigError(f"Missing YAML field(s): {joined}")

    try:
        workers = int(data["workers"])
    except (TypeError, ValueError) as exc:
        raise ConfigError("The `workers` field must be an integer.") from exc
    if workers < 1:
        raise ConfigError("The `workers` field must be greater than or equal to 1.")

    known_keys = set(REQUIRED_FIELDS) | {
        "project_root",
        "manage_py",
        "target",
        "os",
        "init_system",
        "web_server",
        "app_server",
        "ssl_provider",
        "package_manager",
    }
    extras = {key: value for key, value in data.items() if key not in known_keys}
    base_dir = config_path.parent

    def _resolve_path(value: Any) -> Path:
        raw = str(value).strip()
        if not raw:
            raise ConfigError("Path values cannot be empty.")
        normalized = raw.replace("\\", "/")
        if normalized.startswith("/"):
            return PurePosixPath(normalized)
        return PurePosixPath(as_posix_text(base_dir)) / PurePosixPath(normalized)

    def _require_text(key: str) -> str:
        raw = data[key]
        if raw is None:
            raise ConfigError(f"The `{key}` field cannot be empty.")
        value = str(raw).strip()
        if not value:
            raise ConfigError(f"The `{key}` field cannot be empty.")
        return value

    return ProjectConfig(
        project=_require_text("project"),
        domain=_require_text("domain"),
        repo=_require_text("repo"),
        path=_resolve_path(_require_text("path")),
        user=_require_text("user"),
        group=_require_text("group"),
        wsgi=_require_text("wsgi"),
        python=_require_text("python"),
        venv=_resolve_path(_require_text("venv")),
        static_dir=_resolve_path(_require_text("static_dir")),
        media_dir=_resolve_path(_require_text("media_dir")),
        workers=workers,
        target=target,
        extras=extras,
    )
