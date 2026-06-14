"""V2 deployment models and YAML helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class V2ConfigError(ValueError):
    """Raised when a V2 project configuration file is invalid."""


SUPPORTED_BACKENDS = {"local", "ssh"}
SUPPORTED_WEB_SERVERS = {"apache", "nginx"}
SUPPORTED_APP_SERVERS = {"gunicorn"}
SUPPORTED_SSL_PROVIDERS = {"certbot", "none", "disabled"}
SUPPORTED_PACKAGE_MANAGERS = {"apt", "dnf", "yum", "apk", "pacman"}


@dataclass(frozen=True, slots=True)
class ConnectionSpec:
    """Connection details for local or SSH deployment."""

    backend: str = "local"
    host: str | None = None
    port: int = 22
    user: str | None = None
    identity_file: Path | None = None


@dataclass(frozen=True, slots=True)
class DeploymentTarget:
    """Target environment settings."""

    os: str = "linux"
    init_system: str = "systemd"
    web_server: str = "apache"
    app_server: str = "gunicorn"
    ssl_provider: str = "certbot"
    package_manager: str = "apt"


@dataclass(frozen=True, slots=True)
class ProjectSpec:
    """Normalized V2 project specification."""

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
    connection: ConnectionSpec = field(default_factory=ConnectionSpec)
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def service_name(self) -> str:
        return self.project

    @property
    def venv_bin(self) -> Path:
        return self.venv / "bin"

    @property
    def web_service_name(self) -> str:
        return f"{self.project}.{self.target.web_server}"


@dataclass(frozen=True, slots=True)
class ProjectTemplate:
    """Template values used to scaffold a V2 config file."""

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
    connection: ConnectionSpec = field(default_factory=ConnectionSpec)

    def to_yaml_data(self) -> dict[str, Any]:
        venv = self.venv or (self.path / "venv")
        static_dir = self.static_dir or (self.path / "staticfiles")
        media_dir = self.media_dir or (self.path / "media")
        return {
            "project": self.project,
            "domain": self.domain,
            "repo": self.repo,
            "path": str(self.path),
            "user": self.user,
            "group": self.group,
            "wsgi": self.wsgi,
            "python": self.python,
            "venv": str(venv),
            "static_dir": str(static_dir),
            "media_dir": str(media_dir),
            "workers": self.workers,
            "target": {
                "os": self.target.os,
                "init_system": self.target.init_system,
                "web_server": self.target.web_server,
                "app_server": self.target.app_server,
                "ssl_provider": self.target.ssl_provider,
                "package_manager": self.target.package_manager,
            },
            "connection": {
                "backend": self.connection.backend,
                "host": self.connection.host,
                "port": self.connection.port,
                "user": self.connection.user,
                "identity_file": str(self.connection.identity_file) if self.connection.identity_file else None,
            },
        }


def _resolve_path(value: Any, base_dir: Path) -> Path:
    candidate = Path(str(value)).expanduser()
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def _normalize_mapping(data: dict[str, Any]) -> dict[str, Any]:
    project_block = data.get("project")
    if isinstance(project_block, dict):
        merged = dict(project_block)
        merged.update({key: value for key, value in data.items() if key != "project"})
        if "project" not in merged and "name" in merged:
            merged["project"] = merged["name"]
        return merged
    return data


def _read_section(data: dict[str, Any], section: str) -> dict[str, Any]:
    value = data.get(section)
    return dict(value) if isinstance(value, dict) else {}


def render_project_spec(template: ProjectTemplate) -> str:
    return yaml.safe_dump(template.to_yaml_data(), sort_keys=False, default_flow_style=False)


def load_project_spec(project: str | Path, projects_dir: Path | None = None) -> ProjectSpec:
    path = Path(project)
    config_path = path if path.suffix.lower() in {".yml", ".yaml"} or path.exists() else (projects_dir or (Path.cwd() / "projects")) / f"{path.name}.yml"
    if not config_path.exists():
        raise V2ConfigError(f"Configuration file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise V2ConfigError("The YAML file must contain a mapping.")

    data = _normalize_mapping(raw)
    target_section = _read_section(data, "target")
    connection_section = _read_section(data, "connection")
    base_dir = config_path.parent

    required = ("project", "domain", "repo", "path", "user", "group", "wsgi", "python", "venv", "static_dir", "media_dir", "workers")
    missing = [field for field in required if field not in data]
    if missing:
        raise V2ConfigError(f"Missing YAML field(s): {', '.join(missing)}")

    try:
        workers = int(data["workers"])
    except (TypeError, ValueError) as exc:
        raise V2ConfigError("The `workers` field must be an integer.") from exc
    if workers < 1:
        raise V2ConfigError("The `workers` field must be greater than or equal to 1.")

    def require_text(key: str) -> str:
        raw_value = data[key]
        if raw_value is None:
            raise V2ConfigError(f"The `{key}` field cannot be empty.")
        value = str(raw_value).strip()
        if not value:
            raise V2ConfigError(f"The `{key}` field cannot be empty.")
        return value

    target = DeploymentTarget(
        os=str(target_section.get("os", "linux")),
        init_system=str(target_section.get("init_system", "systemd")),
        web_server=str(target_section.get("web_server", "apache")),
        app_server=str(target_section.get("app_server", "gunicorn")),
        ssl_provider=str(target_section.get("ssl_provider", "certbot")),
        package_manager=str(target_section.get("package_manager", "apt")),
    )
    if target.web_server.lower() not in SUPPORTED_WEB_SERVERS:
        raise V2ConfigError(f"Unsupported web server: {target.web_server}")
    if target.app_server.lower() not in SUPPORTED_APP_SERVERS:
        raise V2ConfigError(f"Unsupported app server: {target.app_server}")
    if target.ssl_provider.lower() not in SUPPORTED_SSL_PROVIDERS:
        raise V2ConfigError(f"Unsupported SSL provider: {target.ssl_provider}")
    if target.package_manager.lower() not in SUPPORTED_PACKAGE_MANAGERS:
        raise V2ConfigError(f"Unsupported package manager: {target.package_manager}")
    if target.init_system.lower() != "systemd":
        raise V2ConfigError("V2 currently supports systemd only.")

    backend_value = str(connection_section.get("backend", "local")).strip().lower() or "local"
    if backend_value not in SUPPORTED_BACKENDS:
        raise V2ConfigError(f"Unsupported backend: {backend_value}")

    try:
        port = int(connection_section.get("port", 22))
    except (TypeError, ValueError) as exc:
        raise V2ConfigError("The `connection.port` field must be an integer.") from exc
    if port < 1 or port > 65535:
        raise V2ConfigError("The `connection.port` field must be between 1 and 65535.")

    identity_file_value = connection_section.get("identity_file")
    if identity_file_value:
        identity_candidate = Path(identity_file_value).expanduser()
        identity_file = identity_candidate if identity_candidate.is_absolute() else (base_dir / identity_candidate).resolve()
    else:
        identity_file = None

    connection = ConnectionSpec(
        backend=backend_value,
        host=str(connection_section["host"]).strip() if connection_section.get("host") else None,
        port=port,
        user=str(connection_section["user"]).strip() if connection_section.get("user") else None,
        identity_file=identity_file,
    )
    if connection.backend == "ssh" and not connection.host:
        raise V2ConfigError("The `connection.host` field is required when backend is `ssh`.")

    known = set(required) | {"target", "connection", "os", "init_system", "web_server", "app_server", "ssl_provider", "package_manager", "backend", "host", "port", "identity_file"}
    extras = {key: value for key, value in data.items() if key not in known}

    return ProjectSpec(
        project=require_text("project"),
        domain=require_text("domain"),
        repo=require_text("repo"),
        path=_resolve_path(require_text("path"), base_dir),
        user=require_text("user"),
        group=require_text("group"),
        wsgi=require_text("wsgi"),
        python=require_text("python"),
        venv=_resolve_path(require_text("venv"), base_dir),
        static_dir=_resolve_path(require_text("static_dir"), base_dir),
        media_dir=_resolve_path(require_text("media_dir"), base_dir),
        workers=workers,
        target=target,
        connection=connection,
        extras=extras,
    )
