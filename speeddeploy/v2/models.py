"""V2 deployment models and YAML helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from ..paths import as_posix_text


class V2ConfigError(ValueError):
    """Raised when a V2 project configuration file is invalid."""


SUPPORTED_BACKENDS = {"local", "ssh"}
SUPPORTED_WEB_SERVERS = {"apache", "nginx"}
SUPPORTED_APP_SERVERS = {"gunicorn"}
SUPPORTED_SSL_PROVIDERS = {"certbot", "none", "disabled"}
SUPPORTED_PACKAGE_MANAGERS = {"apt", "dnf", "yum", "apk", "pacman"}
SUPPORTED_DB_ENGINES = {"none", "postgres", "mysql", "sqlite"}
_DB_ENGINE_ALIASES = {"postgresql": "postgres", "pg": "postgres", "mariadb": "mysql"}
DEFAULT_EXPECT_STATUS = (200, 204, 301, 302, 308)


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: Any, field_name: str, *, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    if value is None:
        value = default
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise V2ConfigError(f"The `{field_name}` field must be an integer.") from exc
    if minimum is not None and result < minimum:
        raise V2ConfigError(f"The `{field_name}` field must be >= {minimum}.")
    if maximum is not None and result > maximum:
        raise V2ConfigError(f"The `{field_name}` field must be <= {maximum}.")
    return result


@dataclass(frozen=True, slots=True)
class ConnectionSpec:
    """Connection details for local or SSH deployment."""

    backend: str = "local"
    host: str | None = None
    port: int = 22
    user: str | None = None
    identity_file: Path | None = None


@dataclass(frozen=True, slots=True)
class ReleasesSpec:
    """Atomic release-based deployment settings."""

    enabled: bool = False
    keep: int = 5


@dataclass(frozen=True, slots=True)
class HealthcheckSpec:
    """Post-deployment HTTP healthcheck settings."""

    enabled: bool = True
    path: str = "/"
    host: str | None = None
    port: int | None = None
    expect_status: tuple[int, ...] = DEFAULT_EXPECT_STATUS
    timeout: int = 10
    retries: int = 5
    delay: int = 3


@dataclass(frozen=True, slots=True)
class SSLSpec:
    """Certbot provisioning options."""

    enabled: bool = True
    email: str | None = None
    redirect: bool = True
    staging: bool = False
    agree_tos: bool = True


@dataclass(frozen=True, slots=True)
class SystemPackagesSpec:
    """System package installation policy."""

    install: bool = True


@dataclass(frozen=True, slots=True)
class SystemUserSpec:
    """Optional system user provisioning settings."""

    create: bool = False
    shell: str = "/usr/sbin/nologin"
    home: PurePosixPath | None = None


@dataclass(frozen=True, slots=True)
class DatabaseSpec:
    """Database backup settings used before running migrations."""

    engine: str = "none"
    name: str | None = None
    user: str | None = None
    password: str | None = None
    host: str = "localhost"
    port: int | None = None
    sqlite_path: str = "db.sqlite3"
    keep: int = 5

    @property
    def enabled(self) -> bool:
        return self.engine.lower() not in {"", "none"}


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
    branch: str
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
    releases: ReleasesSpec = field(default_factory=ReleasesSpec)
    healthcheck: HealthcheckSpec = field(default_factory=HealthcheckSpec)
    ssl: SSLSpec = field(default_factory=SSLSpec)
    system_packages: SystemPackagesSpec = field(default_factory=SystemPackagesSpec)
    system_user: SystemUserSpec = field(default_factory=SystemUserSpec)
    database: DatabaseSpec = field(default_factory=DatabaseSpec)
    env: dict[str, str] = field(default_factory=dict)
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

    @property
    def releases_dir(self) -> Path:
        return self.path / "releases"

    @property
    def shared_dir(self) -> Path:
        return self.path / "shared"

    @property
    def current_link(self) -> Path:
        return self.path / "current"

    @property
    def socket_path(self) -> Path:
        return self.path / "gunicorn.sock"


@dataclass(frozen=True, slots=True)
class ProjectTemplate:
    """Template values used to scaffold a V2 config file."""

    project: str
    domain: str
    repo: str
    path: Path
    branch: str = "main"
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
    releases: ReleasesSpec = field(default_factory=ReleasesSpec)
    healthcheck: HealthcheckSpec = field(default_factory=HealthcheckSpec)
    ssl: SSLSpec = field(default_factory=SSLSpec)
    system_packages: SystemPackagesSpec = field(default_factory=SystemPackagesSpec)
    system_user: SystemUserSpec = field(default_factory=SystemUserSpec)
    database: DatabaseSpec = field(default_factory=DatabaseSpec)
    env: dict[str, str] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_yaml_data(self) -> dict[str, Any]:
        venv = self.venv or (self.path / "venv")
        static_dir = self.static_dir or (self.path / "staticfiles")
        media_dir = self.media_dir or (self.path / "media")
        data = {
            "project": self.project,
            "domain": self.domain,
            "repo": self.repo,
            "branch": self.branch,
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
            "connection": {
                "backend": self.connection.backend,
                "host": self.connection.host,
                "port": self.connection.port,
                "user": self.connection.user,
                "identity_file": as_posix_text(self.connection.identity_file) if self.connection.identity_file else None,
            },
            "releases": {
                "enabled": self.releases.enabled,
                "keep": self.releases.keep,
            },
            "healthcheck": {
                "enabled": self.healthcheck.enabled,
                "path": self.healthcheck.path,
                "host": self.healthcheck.host,
                "port": self.healthcheck.port,
                "expect_status": list(self.healthcheck.expect_status),
                "timeout": self.healthcheck.timeout,
                "retries": self.healthcheck.retries,
                "delay": self.healthcheck.delay,
            },
            "ssl": {
                "enabled": self.ssl.enabled,
                "email": self.ssl.email,
                "redirect": self.ssl.redirect,
                "staging": self.ssl.staging,
                "agree_tos": self.ssl.agree_tos,
            },
            "system_packages": {
                "install": self.system_packages.install,
            },
            "system_user": {
                "create": self.system_user.create,
                "shell": self.system_user.shell,
                "home": as_posix_text(self.system_user.home) if self.system_user.home else None,
            },
            "database": {
                "engine": self.database.engine,
                "name": self.database.name,
                "user": self.database.user,
                "password": self.database.password,
                "host": self.database.host,
                "port": self.database.port,
                "sqlite_path": self.database.sqlite_path,
                "keep": self.database.keep,
            },
            "env": dict(self.env),
        }
        for key, value in self.extras.items():
            if key not in data:
                data[key] = value
        return data


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

    def resolve_posix_path(key: str) -> Path:
        raw_value = require_text(key)
        normalized = raw_value.replace("\\", "/")
        if normalized.startswith("/"):
            return PurePosixPath(normalized)
        return PurePosixPath(as_posix_text(base_dir)) / PurePosixPath(normalized)

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

    releases_section = _read_section(data, "releases")
    releases = ReleasesSpec(
        enabled=_as_bool(releases_section.get("enabled", False)),
        keep=_as_int(releases_section.get("keep", 5), "releases.keep", default=5, minimum=1),
    )

    healthcheck_section = _read_section(data, "healthcheck")
    expect_raw = healthcheck_section.get("expect_status")
    if isinstance(expect_raw, (list, tuple)):
        try:
            expect_status = tuple(int(item) for item in expect_raw) or DEFAULT_EXPECT_STATUS
        except (TypeError, ValueError) as exc:
            raise V2ConfigError("The `healthcheck.expect_status` field must contain integers.") from exc
    elif expect_raw is not None:
        expect_status = (_as_int(expect_raw, "healthcheck.expect_status", default=200),)
    else:
        expect_status = DEFAULT_EXPECT_STATUS
    healthcheck = HealthcheckSpec(
        enabled=_as_bool(healthcheck_section.get("enabled", True), default=True),
        path=str(healthcheck_section.get("path", "/")) or "/",
        host=str(healthcheck_section["host"]).strip() if healthcheck_section.get("host") else None,
        port=_as_int(healthcheck_section["port"], "healthcheck.port", default=80, minimum=1, maximum=65535) if healthcheck_section.get("port") else None,
        expect_status=expect_status,
        timeout=_as_int(healthcheck_section.get("timeout", 10), "healthcheck.timeout", default=10, minimum=1),
        retries=_as_int(healthcheck_section.get("retries", 5), "healthcheck.retries", default=5, minimum=1),
        delay=_as_int(healthcheck_section.get("delay", 3), "healthcheck.delay", default=3, minimum=0),
    )

    ssl_section = _read_section(data, "ssl")
    ssl = SSLSpec(
        enabled=_as_bool(ssl_section.get("enabled", True), default=True),
        email=str(ssl_section["email"]).strip() if ssl_section.get("email") else None,
        redirect=_as_bool(ssl_section.get("redirect", True), default=True),
        staging=_as_bool(ssl_section.get("staging", False)),
        agree_tos=_as_bool(ssl_section.get("agree_tos", True), default=True),
    )

    system_packages_section = _read_section(data, "system_packages")
    system_packages = SystemPackagesSpec(
        install=_as_bool(system_packages_section.get("install", True), default=True),
    )

    system_user_section = _read_section(data, "system_user")
    system_user_home_value = system_user_section.get("home")
    if system_user_home_value:
        normalized_home = str(system_user_home_value).replace("\\", "/")
        if normalized_home.startswith("/"):
            system_user_home = PurePosixPath(normalized_home)
        else:
            system_user_home = PurePosixPath(as_posix_text(base_dir)) / PurePosixPath(normalized_home)
    else:
        system_user_home = None
    system_user = SystemUserSpec(
        create=_as_bool(system_user_section.get("create", False), default=False),
        shell=str(system_user_section.get("shell", "/usr/sbin/nologin")) or "/usr/sbin/nologin",
        home=system_user_home,
    )

    database_section = _read_section(data, "database")
    db_engine = str(database_section.get("engine", "none")).strip().lower() or "none"
    db_engine = _DB_ENGINE_ALIASES.get(db_engine, db_engine)
    if db_engine not in SUPPORTED_DB_ENGINES:
        raise V2ConfigError(f"Unsupported database engine: {db_engine}")
    database = DatabaseSpec(
        engine=db_engine,
        name=str(database_section["name"]).strip() if database_section.get("name") else None,
        user=str(database_section["user"]).strip() if database_section.get("user") else None,
        password=str(database_section["password"]) if database_section.get("password") is not None else None,
        host=str(database_section.get("host", "localhost")) or "localhost",
        port=_as_int(database_section["port"], "database.port", default=5432, minimum=1, maximum=65535) if database_section.get("port") else None,
        sqlite_path=str(database_section.get("sqlite_path", "db.sqlite3")) or "db.sqlite3",
        keep=_as_int(database_section.get("keep", 5), "database.keep", default=5, minimum=1),
    )
    if db_engine in {"postgres", "mysql"} and not database.name:
        raise V2ConfigError(f"The `database.name` field is required when engine is `{db_engine}`.")

    env_section = data.get("env")
    if env_section is None:
        env: dict[str, str] = {}
    elif isinstance(env_section, dict):
        env = {str(key): "" if value is None else str(value) for key, value in env_section.items()}
    else:
        raise V2ConfigError("The `env` field must be a mapping of KEY: value pairs.")

    known = set(required) | {"branch", "target", "connection", "releases", "healthcheck", "ssl", "system_packages", "system_user", "database", "env", "os", "init_system", "web_server", "app_server", "ssl_provider", "package_manager", "backend", "host", "port", "identity_file"}
    extras = {key: value for key, value in data.items() if key not in known}

    return ProjectSpec(
        project=require_text("project"),
        domain=require_text("domain"),
        repo=require_text("repo"),
        branch=str(data.get("branch", "main")).strip() or "main",
        path=resolve_posix_path("path"),
        user=require_text("user"),
        group=require_text("group"),
        wsgi=require_text("wsgi"),
        python=require_text("python"),
        venv=resolve_posix_path("venv"),
        static_dir=resolve_posix_path("static_dir"),
        media_dir=resolve_posix_path("media_dir"),
        workers=workers,
        target=target,
        connection=connection,
        releases=releases,
        healthcheck=healthcheck,
        ssl=ssl,
        system_packages=system_packages,
        system_user=system_user,
        database=database,
        env=env,
        extras=extras,
    )
