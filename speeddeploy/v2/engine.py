"""V2 deployment engine and backend selection.

Two deployment strategies are supported:

* **In-place** (default): the repository is cloned/updated directly in
  ``spec.path`` and services are restarted in place.
* **Releases** (``releases.enabled: true``): every deploy builds a fresh
  ``releases/<timestamp>`` checkout with its own virtualenv, then an atomic
  ``current`` symlink swap activates it. A failed post-deploy healthcheck rolls
  the symlink back automatically, and ``rollback`` reactivates the previous
  release on demand.

Both strategies render an optional ``.env`` file and back up the configured
database before running migrations.
"""

from __future__ import annotations

import shlex
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from jinja2 import Environment, PackageLoader
from rich.console import Console

from .backup import backup_database
from .envfile import write_env_file
from .executor import Executor, ExecutorError, LocalExecutor, SSHExecutor
from .health import HealthcheckError, run_healthcheck
from .models import ProjectSpec
from . import releases as rel

console = Console()

_TEMPLATE_ENV = Environment(
    loader=PackageLoader("speeddeploy", "templates"),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)

_PYTHON_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_DJANGO_REQUIREMENT_RE = re.compile(
    r"(?i)^django\s*([<>=!~]{1,2})\s*([0-9]+(?:\.[0-9]+){0,2})"
)

LocalChangePolicy = Literal["keep", "discard"]
_IGNORED_WORKTREE_PREFIXES = ("venv/", "staticfiles/", "media/", ".speeddeploy/")
_STATE_DIR_NAME = ".speeddeploy"
_REQ_HASH_FILE = "requirements.hash"
_COLLECTSTATIC_HASH_FILE = "collectstatic.hash"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


@dataclass(frozen=True, slots=True)
class DeployContext:
    """Resolved paths for one deployment operation.

    ``work_dir`` / ``build_venv`` / ``state_dir`` / ``backup_dir`` describe where
    code is built for *this* operation. ``app_dir`` / ``runtime_venv`` /
    ``static_dir`` / ``media_dir`` / ``env_file`` / ``socket`` are the *stable*
    paths referenced by the systemd unit and web server config (the ``current``
    symlink in release mode), so those configs survive symlink swaps unchanged.
    """

    spec: ProjectSpec
    work_dir: Path
    build_venv: Path
    state_dir: Path
    backup_dir: Path
    app_dir: Path
    runtime_venv: Path
    static_dir: Path
    media_dir: Path
    env_file: Path
    socket: Path
    use_cache: bool
    release_dir: Path | None = None

    @property
    def build_venv_bin(self) -> Path:
        return self.build_venv / "bin"


def _render_template(template_name: str, ctx: DeployContext) -> str:
    spec = ctx.spec
    template = _TEMPLATE_ENV.get_template(template_name)
    return template.render(
        project=spec.project,
        domain=spec.domain,
        repo=spec.repo,
        path=str(ctx.app_dir),
        app_dir=str(ctx.app_dir),
        socket=str(ctx.socket),
        user=spec.user,
        group=spec.group,
        wsgi=spec.wsgi,
        python=spec.python,
        venv=str(ctx.runtime_venv),
        static_dir=str(ctx.static_dir),
        media_dir=str(ctx.media_dir),
        workers=spec.workers,
        target=spec.target,
        connection=spec.connection,
        env_file=str(ctx.env_file) if spec.env else "",
    )


def _requirements_file(ctx: DeployContext) -> Path:
    return ctx.work_dir / "requirements.txt"


def _requirements_cache_file(ctx: DeployContext) -> Path:
    return ctx.state_dir / _REQ_HASH_FILE


def _collectstatic_cache_file(ctx: DeployContext) -> Path:
    return ctx.state_dir / _COLLECTSTATIC_HASH_FILE


def _write_if_changed(executor: Executor, path: Path, content: str, *, sudo: bool = False, mode: str = "0644") -> bool:
    if executor.path_exists(path):
        try:
            current = executor.capture(["cat", str(path)], sudo=sudo)
        except ExecutorError:
            current = None
        else:
            if current == content:
                return False
    executor.write_text(path, content, sudo=sudo, mode=mode)
    return True


def _read_cached_text(executor: Executor, path: Path, *, sudo: bool = False) -> str | None:
    if not executor.path_exists(path):
        return None
    try:
        return executor.capture(["cat", str(path)], sudo=sudo)
    except ExecutorError:
        return None


def _file_sha256(executor: Executor, path: Path, ctx: DeployContext) -> str:
    output = executor.capture(["sha256sum", str(path)], cwd=ctx.work_dir, as_user=ctx.spec.user)
    return output.split()[0].strip()


def _project_tree_hash(executor: Executor, ctx: DeployContext) -> str:
    script = """
set -e
find . \
  -path './.git' -prune -o \
  -path './.speeddeploy' -prune -o \
  -path './venv' -prune -o \
  -path './staticfiles' -prune -o \
  -path './media' -prune -o \
  -path './__pycache__' -prune -o \
  -path './node_modules' -prune -o \
  -type f -print0 \
| sort -z \
| xargs -0 sha256sum \
| sha256sum \
| awk '{print $1}'
""".strip()
    return executor.capture(["bash", "-lc", script], cwd=ctx.work_dir, as_user=ctx.spec.user).strip()


def build_plan(spec: ProjectSpec) -> list[str]:
    steps = [
        f"Select backend: {spec.connection.backend}",
        f"Install system packages via {spec.target.package_manager}",
    ]
    if spec.releases.enabled:
        steps.append(f"Prepare release layout under {spec.path}")
        steps.append(f"Create new release from {spec.repo} (branch {spec.branch})")
        steps.append("Link shared static/media/.env into the release")
    else:
        steps.append(f"Prepare directory: {spec.path}")
        steps.append(f"Clone or update repository: {spec.repo} (branch {spec.branch})")
    if spec.env:
        steps.append(f"Render environment file ({len(spec.env)} var(s))")
    steps.append("Check Python and Django version compatibility")
    steps.append(f"Create virtualenv and install dependencies")
    if spec.database.enabled:
        steps.append(f"Back up {spec.database.engine} database before migrations")
    steps.append("Run Django migrations and collectstatic")
    steps.append(f"Render Gunicorn service: {spec.service_name}.service")
    if spec.target.web_server == "apache":
        steps.append(f"Render Apache vhost: {spec.project}.conf")
    elif spec.target.web_server == "nginx":
        steps.append(f"Render Nginx site: {spec.project}.conf")
    else:
        steps.append(f"Render web server config: {spec.target.web_server}")
    if spec.releases.enabled:
        steps.append("Activate release via atomic 'current' symlink swap")
    steps.append(f"Restart services for {spec.project}")
    if spec.healthcheck.enabled:
        if spec.releases.enabled:
            steps.append("Run healthcheck (auto-rollback on failure)")
        else:
            steps.append("Run healthcheck")
    if spec.target.ssl_provider not in {"", "none", "disabled"}:
        steps.append(f"Provision SSL via {spec.target.ssl_provider}")
    if spec.releases.enabled:
        steps.append(f"Prune old releases (keep {spec.releases.keep})")
    return steps


def _select_executor(spec: ProjectSpec, dry_run: bool = False) -> Executor:
    backend = (spec.connection.backend or "local").lower()
    if backend == "local":
        return LocalExecutor(dry_run=dry_run)
    if backend == "ssh":
        host = spec.connection.host
        if not host:
            raise ExecutorError("SSH backend requires `connection.host`.")
        return SSHExecutor(
            host=host,
            user=spec.connection.user or spec.user,
            port=spec.connection.port,
            identity_file=spec.connection.identity_file,
            dry_run=dry_run,
        )
    raise ExecutorError(f"Unsupported backend: {backend}")


def _system_packages(spec: ProjectSpec) -> list[str]:
    manager = spec.target.package_manager.lower()
    base_packages = {
        "apt": ["git", "python3-venv", "python3-pip"],
        "dnf": ["git", "python3", "python3-pip", "python3-virtualenv"],
        "yum": ["git", "python3", "python3-pip", "python3-virtualenv"],
        "apk": ["git", "python3", "py3-pip", "py3-virtualenv"],
        "pacman": ["git", "python", "python-pip", "python-virtualenv"],
    }.get(manager, ["git", "python3-venv", "python3-pip"])

    web_packages = {
        "apt": {"apache": "apache2", "nginx": "nginx"},
        "dnf": {"apache": "httpd", "nginx": "nginx"},
        "yum": {"apache": "httpd", "nginx": "nginx"},
        "apk": {"apache": "apache2", "nginx": "nginx"},
        "pacman": {"apache": "apache", "nginx": "nginx"},
    }.get(manager, {"apache": "apache2", "nginx": "nginx"})

    certbot_packages = {
        "apt": {"apache": ("certbot", "python3-certbot-apache"), "nginx": ("certbot", "python3-certbot-nginx")},
        "dnf": {"apache": ("certbot", "python3-certbot-apache"), "nginx": ("certbot", "python3-certbot-nginx")},
        "yum": {"apache": ("certbot", "python3-certbot-apache"), "nginx": ("certbot", "python3-certbot-nginx")},
        "apk": {"apache": ("certbot", "certbot-apache"), "nginx": ("certbot", "certbot-nginx")},
        "pacman": {"apache": ("certbot", "python-certbot-apache"), "nginx": ("certbot", "python-certbot-nginx")},
    }.get(manager, {"apache": ("certbot", "python3-certbot-apache"), "nginx": ("certbot", "python3-certbot-nginx")})

    db_packages = {
        "apt": {"postgres": ("postgresql-client",), "mysql": ("default-mysql-client",), "sqlite": ("sqlite3",)},
        "dnf": {"postgres": ("postgresql",), "mysql": ("mariadb",), "sqlite": ("sqlite",)},
        "yum": {"postgres": ("postgresql",), "mysql": ("mariadb",), "sqlite": ("sqlite",)},
        "apk": {"postgres": ("postgresql-client",), "mysql": ("mariadb-client",), "sqlite": ("sqlite",)},
        "pacman": {"postgres": ("postgresql-libs",), "mysql": ("mariadb-clients",), "sqlite": ("sqlite",)},
    }.get(manager, {"postgres": ("postgresql-client",), "mysql": ("default-mysql-client",), "sqlite": ("sqlite3",)})

    packages = list(base_packages)
    web_server = spec.target.web_server.lower()
    if web_server in web_packages:
        packages.append(web_packages[web_server])
    if spec.target.ssl_provider == "certbot" and web_server in certbot_packages:
        packages.extend(certbot_packages[web_server])
    elif spec.target.ssl_provider == "certbot":
        packages.append("certbot")
    if spec.database.enabled:
        packages.extend(db_packages.get(spec.database.engine.lower(), ()))
    return packages


def _install_packages(executor: Executor, spec: ProjectSpec) -> None:
    packages = _system_packages(spec)
    manager = spec.target.package_manager.lower()
    if manager == "apt":
        executor.run(["apt-get", "update"], sudo=True)
        executor.run(["apt-get", "install", "-y", *packages], sudo=True)
        return
    if manager == "dnf":
        executor.run(["dnf", "install", "-y", *packages], sudo=True)
        return
    if manager == "yum":
        executor.run(["yum", "install", "-y", *packages], sudo=True)
        return
    if manager == "apk":
        executor.run(["apk", "add", *packages], sudo=True)
        return
    if manager == "pacman":
        executor.run(["pacman", "-Sy", "--noconfirm", *packages], sudo=True)
        return
    raise ExecutorError(f"Unsupported package manager: {manager}")


def _prepare_paths(executor: Executor, spec: ProjectSpec) -> None:
    executor.run(["mkdir", "-p", str(spec.path)], sudo=True)
    executor.run(["chown", "-R", f"{spec.user}:{spec.group}", str(spec.path)], sudo=True)
    executor.run(["chmod", "-R", "775", str(spec.path)], sudo=True)


def _normalize_worktree_ownership(executor: Executor, spec: ProjectSpec) -> None:
    if not executor.path_exists(spec.path):
        return
    executor.run(["chown", "-R", f"{spec.user}:{spec.group}", str(spec.path)], sudo=True)


def _ensure_git_safe_directory(executor: Executor, spec: ProjectSpec, work_dir: Path) -> None:
    if not executor.path_exists(work_dir / ".git"):
        return

    try:
        configured = executor.capture(
            ["git", "config", "--global", "--get-all", "safe.directory"],
            cwd=work_dir,
            as_user=spec.user,
        )
    except ExecutorError:
        configured = ""
    if str(work_dir) in {line.strip() for line in configured.splitlines() if line.strip()}:
        return

    executor.run(
        ["git", "config", "--global", "--add", "safe.directory", str(work_dir)],
        cwd=work_dir,
        as_user=spec.user,
    )


def _git_worktree_dirty(executor: Executor, spec: ProjectSpec) -> list[str]:
    status = executor.capture(["git", "status", "--porcelain"], cwd=spec.path, as_user=spec.user)
    dirty_entries: list[str] = []
    for line in status.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if path.startswith(_IGNORED_WORKTREE_PREFIXES):
            continue
        dirty_entries.append(line)
    return dirty_entries


def _requirements_cache_matches(executor: Executor, ctx: DeployContext) -> bool:
    requirements_path = _requirements_file(ctx)
    if not executor.path_exists(requirements_path):
        return False
    cached = _read_cached_text(executor, _requirements_cache_file(ctx))
    if cached is None:
        return False
    return cached.strip() == _file_sha256(executor, requirements_path, ctx)


def _store_requirements_cache(executor: Executor, ctx: DeployContext) -> None:
    requirements_path = _requirements_file(ctx)
    if not executor.path_exists(requirements_path):
        return
    executor.run(["mkdir", "-p", str(ctx.state_dir)], sudo=True)
    executor.run(["chown", "-R", f"{ctx.spec.user}:{ctx.spec.group}", str(ctx.state_dir)], sudo=True)
    executor.write_text(_requirements_cache_file(ctx), f"{_file_sha256(executor, requirements_path, ctx)}\n", sudo=True)


def _collectstatic_cache_matches(executor: Executor, ctx: DeployContext) -> bool:
    cached = _read_cached_text(executor, _collectstatic_cache_file(ctx))
    if cached is None:
        return False
    try:
        current = _project_tree_hash(executor, ctx)
    except ExecutorError:
        return False
    return cached.strip() == current


def _store_collectstatic_cache(executor: Executor, ctx: DeployContext) -> None:
    try:
        current = _project_tree_hash(executor, ctx)
    except ExecutorError:
        return
    executor.run(["mkdir", "-p", str(ctx.state_dir)], sudo=True)
    executor.run(["chown", "-R", f"{ctx.spec.user}:{ctx.spec.group}", str(ctx.state_dir)], sudo=True)
    executor.write_text(_collectstatic_cache_file(ctx), f"{current}\n", sudo=True)


def _stash_worktree(executor: Executor, spec: ProjectSpec) -> None:
    dirty_entries = _git_worktree_dirty(executor, spec)
    if not dirty_entries:
        return

    if getattr(executor, "dry_run", False):
        console.print(
            "[yellow][dry-run] Would stash local changes before updating: "
            f"{', '.join(dirty_entries[:5])}[/yellow]"
        )
        return

    console.print("[yellow]Local Git changes detected. SpeedDeploy will create a stash.[/yellow]")
    executor.run(
        [
            "git",
            "stash",
            "push",
            "-u",
            "-m",
            "speeddeploy auto-stash",
        ],
        cwd=spec.path,
        as_user=spec.user,
    )


def _unstash_worktree(executor: Executor, spec: ProjectSpec) -> None:
    if getattr(executor, "dry_run", False):
        console.print("[yellow][dry-run] Would restore the last stash[/yellow]")
        return
    executor.run(["git", "stash", "pop"], cwd=spec.path, as_user=spec.user)


def _discard_worktree(executor: Executor, spec: ProjectSpec) -> None:
    if getattr(executor, "dry_run", False):
        console.print("[yellow][dry-run] Would discard local Git changes[/yellow]")
        return
    console.print("[yellow]Local Git changes detected. SpeedDeploy will discard them before updating.[/yellow]")
    executor.run(["git", "reset", "--hard", "HEAD"], cwd=spec.path, as_user=spec.user)
    executor.run(
        ["git", "clean", "-fd", "-e", "venv", "-e", "staticfiles", "-e", "media", "-e", ".speeddeploy"],
        cwd=spec.path,
        as_user=spec.user,
    )


def _parse_python_version(output: str) -> tuple[int, int, int] | None:
    match = _PYTHON_VERSION_RE.search(output)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _parse_django_requirement(requirements_path: Path) -> tuple[str, tuple[int, ...]] | None:
    if not requirements_path.exists():
        return None

    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "--", "git+", "http://", "https://")):
            continue
        match = _DJANGO_REQUIREMENT_RE.match(line)
        if not match:
            continue
        operator = match.group(1)
        version = tuple(int(part) for part in match.group(2).split("."))
        return operator, version
    return None


def _ensure_python_django_compatibility(executor: Executor, ctx: DeployContext) -> None:
    spec = ctx.spec
    if getattr(executor, "dry_run", False):
        console.print("[yellow][dry-run] Would check Python/Django compatibility[/yellow]")
        return

    requirements_path = ctx.work_dir / "requirements.txt"
    django_requirement = _parse_django_requirement(requirements_path)
    if django_requirement is None:
        return

    operator, required_version = django_requirement
    python_output = executor.capture([spec.python, "--version"], cwd=ctx.work_dir)
    python_version = _parse_python_version(python_output)
    if python_version is None:
        raise ExecutorError(f"Unable to detect Python version from: {python_output or spec.python}")

    django_major = required_version[0]
    django_minor = required_version[1] if len(required_version) > 1 else 0

    if django_major >= 6 and python_version < (3, 12, 0):
        raise ExecutorError(
            "Incompatible Python/Django combination detected. "
            f"{requirements_path} requires Django {django_major}.{django_minor} {operator} "
            f"{'.'.join(str(part) for part in required_version)}, but {spec.python} reports "
            f"Python {python_version[0]}.{python_version[1]}.{python_version[2]}. "
            "Django 6.x requires Python >= 3.12. "
            "Install Python 3.12 on the server or lower the Django version in the project requirements."
        )


def _search_project_file(executor: Executor, ctx: DeployContext, needle: str) -> str:
    quoted = shlex.quote(needle)
    command = [
        "bash",
        "-lc",
        (
            "grep -R -n -m 1 "
            "--exclude-dir=.git "
            "--exclude-dir=venv "
            "--exclude-dir=__pycache__ "
            "--exclude-dir=node_modules "
            f"{quoted} . || true"
        ),
    ]
    return executor.capture(command, cwd=ctx.work_dir)


def _preflight_django_settings(executor: Executor, ctx: DeployContext) -> None:
    if getattr(executor, "dry_run", False):
        console.print("[yellow][dry-run] Would verify STATIC_ROOT and DEFAULT_AUTO_FIELD[/yellow]")
        return

    static_root_hit = _search_project_file(executor, ctx, "STATIC_ROOT")
    if not static_root_hit:
        raise ExecutorError(
            "Le projet ne declare pas `STATIC_ROOT`. "
            "Ajoute par exemple `STATIC_ROOT = BASE_DIR / 'staticfiles'` dans le fichier de settings "
            "avant de lancer `collectstatic`."
        )

    auto_field_hit = _search_project_file(executor, ctx, "DEFAULT_AUTO_FIELD")
    if not auto_field_hit:
        console.print(
            "[yellow]Avertissement: `DEFAULT_AUTO_FIELD` n est pas detecte. "
            "Ajoute `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` dans les settings "
            "pour supprimer les warnings de migrations.[/yellow]"
        )


def _clone_or_update(executor: Executor, spec: ProjectSpec, *, local_changes: LocalChangePolicy = "keep") -> None:
    git_dir = spec.path / ".git"
    if executor.path_exists(git_dir):
        _normalize_worktree_ownership(executor, spec)
        _ensure_git_safe_directory(executor, spec, spec.path)
        dirty_entries = _git_worktree_dirty(executor, spec)
        if dirty_entries:
            if local_changes == "discard":
                _discard_worktree(executor, spec)
            else:
                _stash_worktree(executor, spec)
        current_branch = executor.capture(["git", "branch", "--show-current"], cwd=spec.path, as_user=spec.user).strip()
        if current_branch != spec.branch:
            executor.run(["git", "fetch", "origin", spec.branch], cwd=spec.path, as_user=spec.user)
            executor.run(["git", "checkout", "-B", spec.branch, f"origin/{spec.branch}"], cwd=spec.path, as_user=spec.user)
        else:
            executor.run(["git", "pull", "origin", spec.branch], cwd=spec.path, as_user=spec.user)
        if dirty_entries and local_changes == "keep":
            _unstash_worktree(executor, spec)
        executor.run(["chown", "-R", f"{spec.user}:{spec.group}", str(spec.path)], sudo=True)
        return

    if executor.path_exists(spec.path) and not executor.is_empty_dir(spec.path):
        raise ExecutorError(
            f"The deployment path {spec.path} already exists and is not empty. "
            "Choose an empty directory or a clean target."
        )

    executor.run(["git", "clone", "--branch", spec.branch, "--single-branch", spec.repo, str(spec.path)], cwd=spec.path.parent, as_user=spec.user)
    _ensure_git_safe_directory(executor, spec, spec.path)
    executor.run(["chown", "-R", f"{spec.user}:{spec.group}", str(spec.path)], sudo=True)


def _create_venv(executor: Executor, ctx: DeployContext) -> None:
    spec = ctx.spec
    venv_python = ctx.build_venv_bin / "python"
    if getattr(executor, "dry_run", False):
        executor.run([spec.python, "-m", "venv", str(ctx.build_venv)], cwd=ctx.work_dir, as_user=spec.user)
        executor.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], cwd=ctx.work_dir, as_user=spec.user)
        executor.run([str(ctx.build_venv_bin / "pip"), "install", "-r", "requirements.txt"], cwd=ctx.work_dir, as_user=spec.user)
        return

    requirements_path = _requirements_file(ctx)
    if not executor.path_exists(requirements_path):
        raise ExecutorError(f"Missing requirements file: {requirements_path}")

    if ctx.use_cache and executor.path_exists(venv_python) and _requirements_cache_matches(executor, ctx):
        console.print("[green]Virtualenv already up to date. Skipping dependency install.[/green]")
        return

    if executor.path_exists(ctx.build_venv):
        console.print(f"[yellow]Existing virtualenv detected at {ctx.build_venv}. Rebuilding it.[/yellow]")
        executor.run(["rm", "-rf", str(ctx.build_venv)], sudo=True)

    executor.run([spec.python, "-m", "venv", str(ctx.build_venv)], cwd=ctx.work_dir, as_user=spec.user)
    executor.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], cwd=ctx.work_dir, as_user=spec.user)
    executor.run([str(ctx.build_venv_bin / "pip"), "install", "-r", "requirements.txt"], cwd=ctx.work_dir, as_user=spec.user)
    if ctx.use_cache:
        _store_requirements_cache(executor, ctx)


def _django_steps(executor: Executor, ctx: DeployContext, *, timestamp: str) -> None:
    spec = ctx.spec
    backup_database(executor, spec, backup_dir=ctx.backup_dir, work_dir=ctx.work_dir, timestamp=timestamp)
    executor.run([str(ctx.build_venv_bin / "python"), "manage.py", "migrate"], cwd=ctx.work_dir, as_user=spec.user)
    if ctx.use_cache and _collectstatic_cache_matches(executor, ctx):
        console.print("[green]collectstatic cache hit. Skipping static collection.[/green]")
        return
    executor.run([str(ctx.build_venv_bin / "python"), "manage.py", "collectstatic", "--noinput"], cwd=ctx.work_dir, as_user=spec.user)
    if ctx.use_cache:
        _store_collectstatic_cache(executor, ctx)


def _render_gunicorn(executor: Executor, ctx: DeployContext) -> bool:
    spec = ctx.spec
    content = _render_template("gunicorn.service.j2", ctx)
    changed = _write_if_changed(executor, Path("/etc/systemd/system") / f"{spec.project}.service", content, sudo=True)
    executor.run(["systemctl", "daemon-reload"], sudo=True)
    executor.run(["systemctl", "enable", f"{spec.project}.service"], sudo=True)
    return changed


def _render_web_server(executor: Executor, ctx: DeployContext) -> bool:
    spec = ctx.spec
    if spec.target.web_server == "apache":
        content = _render_template("apache.conf.j2", ctx)
        changed = _write_if_changed(executor, Path("/etc/apache2/sites-available") / f"{spec.project}.conf", content, sudo=True)
        executor.run(["a2enmod", "proxy", "proxy_http", "headers"], sudo=True)
        executor.run(["a2ensite", f"{spec.project}.conf"], sudo=True)
        executor.run(["apache2ctl", "configtest"], sudo=True)
        return changed
    if spec.target.web_server == "nginx":
        content = _render_template("nginx.conf.j2", ctx)
        changed = _write_if_changed(executor, Path("/etc/nginx/sites-available") / f"{spec.project}.conf", content, sudo=True)
        executor.run(["ln", "-sf", f"/etc/nginx/sites-available/{spec.project}.conf", f"/etc/nginx/sites-enabled/{spec.project}.conf"], sudo=True)
        executor.run(["nginx", "-t"], sudo=True)
        return changed
    raise ExecutorError(f"Unsupported web server: {spec.target.web_server}")


def _provision_ssl(executor: Executor, spec: ProjectSpec) -> None:
    if spec.target.ssl_provider in {"", "none", "disabled"}:
        return
    if spec.target.web_server == "apache":
        executor.run(["certbot", "--apache", "-d", spec.domain], sudo=True)
        return
    if spec.target.web_server == "nginx":
        executor.run(["certbot", "--nginx", "-d", spec.domain], sudo=True)
        return
    executor.run(["certbot", "--standalone", "-d", spec.domain], sudo=True)


def _reload_web_server(executor: Executor, spec: ProjectSpec) -> None:
    if spec.target.web_server == "apache":
        executor.run(["systemctl", "reload", "apache2"], sudo=True)
        return
    if spec.target.web_server == "nginx":
        executor.run(["systemctl", "reload", "nginx"], sudo=True)
        return


@dataclass(slots=True)
class DeploymentEngine:
    """High-level deployment orchestration for V2."""

    spec: ProjectSpec
    executor: Executor

    def _context(self, release_dir: Path | None = None) -> DeployContext:
        spec = self.spec
        if spec.releases.enabled:
            shared = spec.shared_dir
            app_dir = spec.current_link
            runtime_venv = app_dir / "venv"
            state_dir = shared / _STATE_DIR_NAME
            backup_dir = shared / "backups"
            static_dir = shared / "staticfiles"
            media_dir = shared / "media"
            env_file = shared / ".env"
            if release_dir is not None:
                work_dir = release_dir
                build_venv = release_dir / "venv"
            else:
                work_dir = app_dir
                build_venv = runtime_venv
            return DeployContext(
                spec=spec,
                work_dir=work_dir,
                build_venv=build_venv,
                state_dir=state_dir,
                backup_dir=backup_dir,
                app_dir=app_dir,
                runtime_venv=runtime_venv,
                static_dir=static_dir,
                media_dir=media_dir,
                env_file=env_file,
                socket=spec.socket_path,
                use_cache=False,
                release_dir=release_dir,
            )
        return DeployContext(
            spec=spec,
            work_dir=spec.path,
            build_venv=spec.venv,
            state_dir=spec.path / _STATE_DIR_NAME,
            backup_dir=spec.path / "backups",
            app_dir=spec.path,
            runtime_venv=spec.venv,
            static_dir=spec.static_dir,
            media_dir=spec.media_dir,
            env_file=spec.path / ".env",
            socket=spec.socket_path,
            use_cache=True,
        )

    def plan(self) -> list[str]:
        return build_plan(self.spec)

    def doctor(self, *, fix: bool = False) -> None:
        spec = self.spec
        console.print(f"[bold]Project:[/bold] {spec.project}")
        console.print(f"[bold]Domain:[/bold] {spec.domain}")
        console.print(f"[bold]Branch:[/bold] {spec.branch}")
        console.print(f"[bold]Strategy:[/bold] {'releases' if spec.releases.enabled else 'in-place'}")
        console.print(f"[bold]Connection backend:[/bold] {spec.connection.backend}")
        if spec.connection.backend == "ssh":
            console.print(f"[bold]SSH host:[/bold] {spec.connection.host or 'unset'}")
            console.print(f"[bold]SSH user:[/bold] {spec.connection.user or spec.user}")
        console.print(f"[bold]Executor:[/bold] {self.executor.kind()}")
        console.print(f"[bold]Web server:[/bold] {spec.target.web_server}")
        console.print(f"[bold]App server:[/bold] {spec.target.app_server}")
        console.print(f"[bold]Database backups:[/bold] {spec.database.engine}")
        console.print(f"[bold]Healthcheck:[/bold] {'enabled' if spec.healthcheck.enabled else 'disabled'}")
        console.print(f"[bold]Env vars:[/bold] {len(spec.env)}")
        if spec.releases.enabled:
            names, current = self.release_overview()
            console.print(f"[bold]Releases:[/bold] {len(names)} (keep {spec.releases.keep})")
            console.print(f"[bold]Current release:[/bold] {current or 'none'}")
        elif self.executor.path_exists(spec.path / ".git"):
            dirty_entries = _git_worktree_dirty(self.executor, spec)
            if dirty_entries:
                console.print("[yellow]Local Git changes detected:[/yellow]")
                for entry in dirty_entries[:10]:
                    console.print(f"  - {entry}")
            else:
                console.print("[green]Git worktree clean.[/green]")
        if fix:
            self.fix()
        for idx, step in enumerate(self.plan(), start=1):
            console.print(f"{idx}. {step}")

    def fix(self) -> None:
        spec = self.spec
        ctx = self._context()
        targets = [spec.path, spec.venv, spec.static_dir, spec.media_dir, ctx.state_dir]
        if spec.releases.enabled:
            targets = [spec.path, spec.shared_dir, ctx.state_dir]
        seen: set[Path] = set()
        for target in targets:
            candidate = Path(target)
            if candidate in seen or not self.executor.path_exists(candidate):
                continue
            seen.add(candidate)
            self.executor.run(["chown", "-R", f"{spec.user}:{spec.group}", str(candidate)], sudo=True)
        if not spec.releases.enabled:
            _ensure_git_safe_directory(self.executor, spec, spec.path)
        console.print("[green]Ownership and Git safety issues repaired.[/green]")

    # -- in-place strategy -------------------------------------------------

    def _sync_code(self, *, local_changes: LocalChangePolicy = "keep", timestamp: str) -> None:
        ctx = self._context()
        _clone_or_update(self.executor, self.spec, local_changes=local_changes)
        write_env_file(self.executor, self.spec, ctx.env_file)
        _ensure_python_django_compatibility(self.executor, ctx)
        _preflight_django_settings(self.executor, ctx)
        _create_venv(self.executor, ctx)
        _django_steps(self.executor, ctx, timestamp=timestamp)
        _normalize_worktree_ownership(self.executor, self.spec)

    def _run_healthcheck(self) -> None:
        try:
            run_healthcheck(self.executor, self.spec)
        except HealthcheckError as exc:
            raise ExecutorError(str(exc)) from exc

    # -- release strategy --------------------------------------------------

    def _deploy_release(self) -> None:
        spec = self.spec
        executor = self.executor
        timestamp = _timestamp()
        release_dir = spec.releases_dir / timestamp
        ctx = self._context(release_dir)

        rel.ensure_release_layout(executor, spec)
        _install_packages(executor, spec)
        rel.create_release(executor, spec, release_dir)
        _ensure_git_safe_directory(executor, spec, release_dir)
        write_env_file(executor, spec, ctx.env_file)
        rel.link_shared(executor, spec, release_dir, link_env=bool(spec.env))
        _ensure_python_django_compatibility(executor, ctx)
        _preflight_django_settings(executor, ctx)
        _create_venv(executor, ctx)
        _django_steps(executor, ctx, timestamp=timestamp)
        executor.run(["chown", "-R", f"{spec.user}:{spec.group}", str(release_dir)], sudo=True)
        executor.run(["chown", "-R", f"{spec.user}:{spec.group}", str(spec.shared_dir)], sudo=True)

        previous = rel.current_release(executor, spec)
        render_ctx = self._context()
        _render_gunicorn(executor, render_ctx)
        _render_web_server(executor, render_ctx)
        rel.switch_current(executor, spec, release_dir)
        self.restart()

        try:
            run_healthcheck(executor, spec)
        except HealthcheckError as exc:
            if previous is not None and previous != release_dir:
                console.print(f"[red]Healthcheck failed. Rolling back to {previous.name}.[/red]")
                rel.switch_current(executor, spec, previous)
                self.restart()
                raise ExecutorError(
                    f"Deployment healthcheck failed; rolled back to release {previous.name}. {exc}"
                ) from exc
            raise ExecutorError(
                f"Deployment healthcheck failed and no previous release is available to roll back to. {exc}"
            ) from exc

        self.update_cert()
        rel.prune_releases(executor, spec, protect={previous.name} if previous else set())
        console.print(f"[bold green]Release {timestamp} is live: https://{spec.domain}[/bold green]")

    def rollback(self) -> None:
        spec = self.spec
        executor = self.executor
        if not spec.releases.enabled:
            raise ExecutorError("Rollback requires `releases.enabled: true` in the project config.")
        target = rel.previous_release(executor, spec)
        if target is None:
            raise ExecutorError("No previous release is available to roll back to.")
        console.print(f"[yellow]Rolling back to release {target.name}...[/yellow]")
        rel.switch_current(executor, spec, target)
        self.restart()
        try:
            run_healthcheck(executor, spec)
        except HealthcheckError as exc:
            console.print(f"[yellow]Warning: healthcheck still failing after rollback: {exc}[/yellow]")
        console.print(f"[bold green]Rolled back to release {target.name}.[/bold green]")

    def release_overview(self) -> tuple[list[str], str | None]:
        names = rel.list_releases(self.executor, self.spec)
        current = rel.current_release(self.executor, self.spec)
        return names, current.name if current else None

    # -- shared operations -------------------------------------------------

    def deploy(self, *, local_changes: LocalChangePolicy = "keep") -> None:
        if self.spec.releases.enabled:
            self._deploy_release()
            return
        timestamp = _timestamp()
        _prepare_paths(self.executor, self.spec)
        _install_packages(self.executor, self.spec)
        self._sync_code(local_changes=local_changes, timestamp=timestamp)
        self.update_conf(restart=False)
        self.update_cert()
        self.restart()
        self._run_healthcheck()

    def update_code(self, *, local_changes: LocalChangePolicy = "keep") -> None:
        if self.spec.releases.enabled:
            self._deploy_release()
            return
        timestamp = _timestamp()
        self._sync_code(local_changes=local_changes, timestamp=timestamp)
        self.restart()
        self._run_healthcheck()

    def update_conf(self, *, restart: bool = True) -> None:
        ctx = self._context()
        gunicorn_changed = _render_gunicorn(self.executor, ctx)
        web_changed = _render_web_server(self.executor, ctx)
        if restart:
            if gunicorn_changed or web_changed:
                self.restart()
                self._run_healthcheck()
            else:
                console.print("[green]Configuration already up to date.[/green]")

    def update(self, *, local_changes: LocalChangePolicy = "keep") -> None:
        if self.spec.releases.enabled:
            self._deploy_release()
            return
        timestamp = _timestamp()
        self._sync_code(local_changes=local_changes, timestamp=timestamp)
        self.update_conf(restart=False)
        self.update_cert()
        self.restart()
        self._run_healthcheck()

    def update_cert(self) -> None:
        _provision_ssl(self.executor, self.spec)
        _reload_web_server(self.executor, self.spec)

    def backup_now(self) -> None:
        spec = self.spec
        if not spec.database.enabled:
            raise ExecutorError("No database is configured (set `database.engine`).")
        ctx = self._context()
        backup_database(
            self.executor,
            spec,
            backup_dir=ctx.backup_dir,
            work_dir=ctx.app_dir,
            timestamp=_timestamp(),
        )

    def restart(self) -> None:
        self.executor.run(["systemctl", "restart", f"{self.spec.project}.service"], sudo=True)
        _reload_web_server(self.executor, self.spec)

    def status(self) -> None:
        self.executor.run(["systemctl", "status", f"{self.spec.project}.service", "--no-pager"], sudo=True)

    def logs(self) -> None:
        self.executor.run(["journalctl", "-u", f"{self.spec.project}.service", "-n", "100", "--no-pager"], sudo=True)

    def ssl(self) -> None:
        _provision_ssl(self.executor, self.spec)

    def superuser(self) -> None:
        ctx = self._context()
        self.executor.run([str(ctx.runtime_venv / "bin" / "python"), "manage.py", "createsuperuser"], cwd=ctx.app_dir, as_user=self.spec.user)


def build_engine(spec: ProjectSpec, *, dry_run: bool = False) -> DeploymentEngine:
    executor = _select_executor(spec, dry_run=dry_run)
    return DeploymentEngine(spec=spec, executor=executor)
