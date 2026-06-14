"""V2 deployment engine and backend selection."""

from __future__ import annotations

import shlex
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from jinja2 import Environment, PackageLoader
from rich.console import Console

from .executor import Executor, ExecutorError, LocalExecutor, SSHExecutor
from .models import ProjectSpec

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


def _render_template(template_name: str, spec: ProjectSpec) -> str:
    template = _TEMPLATE_ENV.get_template(template_name)
    return template.render(
        project=spec.project,
        domain=spec.domain,
        repo=spec.repo,
        path=str(spec.path),
        user=spec.user,
        group=spec.group,
        wsgi=spec.wsgi,
        python=spec.python,
        venv=str(spec.venv),
        static_dir=str(spec.static_dir),
        media_dir=str(spec.media_dir),
        workers=spec.workers,
        target=spec.target,
        connection=spec.connection,
    )


def _state_dir(spec: ProjectSpec) -> Path:
    return spec.path / _STATE_DIR_NAME


def _requirements_file(spec: ProjectSpec) -> Path:
    return spec.path / "requirements.txt"


def _requirements_cache_file(spec: ProjectSpec) -> Path:
    return _state_dir(spec) / _REQ_HASH_FILE


def _collectstatic_cache_file(spec: ProjectSpec) -> Path:
    return _state_dir(spec) / _COLLECTSTATIC_HASH_FILE


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


def _file_sha256(executor: Executor, path: Path, spec: ProjectSpec) -> str:
    output = executor.capture(["sha256sum", str(path)], cwd=spec.path, as_user=spec.user)
    return output.split()[0].strip()


def _project_tree_hash(executor: Executor, spec: ProjectSpec) -> str:
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
    return executor.capture(["bash", "-lc", script], cwd=spec.path, as_user=spec.user).strip()


def build_plan(spec: ProjectSpec) -> list[str]:
    steps = [
        f"Select backend: {spec.connection.backend}",
        f"Install system packages via {spec.target.package_manager}",
        f"Prepare directory: {spec.path}",
        f"Clone or update repository: {spec.repo} (branch {spec.branch})",
        "Check Python and Django version compatibility",
        f"Create virtualenv: {spec.venv}",
        "Reuse dependency cache when requirements.txt is unchanged",
        "Reuse collectstatic cache when project tree is unchanged",
        "Install Python dependencies",
        "Run Django migrations and collectstatic",
        f"Render Gunicorn service: {spec.service_name}.service",
    ]
    if spec.target.web_server == "apache":
        steps.append(f"Render Apache vhost: {spec.project}.conf")
    elif spec.target.web_server == "nginx":
        steps.append(f"Render Nginx site: {spec.project}.conf")
    else:
        steps.append(f"Render web server config: {spec.target.web_server}")

    if spec.target.ssl_provider not in {"", "none", "disabled"}:
        steps.append(f"Provision SSL via {spec.target.ssl_provider}")
    steps.append(f"Restart services for {spec.project}")
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

    packages = list(base_packages)
    web_server = spec.target.web_server.lower()
    if web_server in web_packages:
        packages.append(web_packages[web_server])
    if spec.target.ssl_provider == "certbot" and web_server in certbot_packages:
        packages.extend(certbot_packages[web_server])
    elif spec.target.ssl_provider == "certbot":
        packages.append("certbot")
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


def _ensure_git_safe_directory(executor: Executor, spec: ProjectSpec) -> None:
    if not executor.path_exists(spec.path / ".git"):
        return

    try:
        configured = executor.capture(
            ["git", "config", "--global", "--get-all", "safe.directory"],
            cwd=spec.path,
            as_user=spec.user,
        )
    except ExecutorError:
        configured = ""
    if str(spec.path) in {line.strip() for line in configured.splitlines() if line.strip()}:
        return

    executor.run(
        ["git", "config", "--global", "--add", "safe.directory", str(spec.path)],
        cwd=spec.path,
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


def _requirements_cache_matches(executor: Executor, spec: ProjectSpec) -> bool:
    requirements_path = _requirements_file(spec)
    if not executor.path_exists(requirements_path):
        return False
    cached = _read_cached_text(executor, _requirements_cache_file(spec))
    if cached is None:
        return False
    return cached.strip() == _file_sha256(executor, requirements_path, spec)


def _store_requirements_cache(executor: Executor, spec: ProjectSpec) -> None:
    requirements_path = _requirements_file(spec)
    if not executor.path_exists(requirements_path):
        return
    state_dir = _state_dir(spec)
    executor.run(["mkdir", "-p", str(state_dir)], cwd=spec.path, as_user=spec.user)
    executor.write_text(_requirements_cache_file(spec), f"{_file_sha256(executor, requirements_path, spec)}\n", sudo=False)


def _collectstatic_cache_matches(executor: Executor, spec: ProjectSpec) -> bool:
    cached = _read_cached_text(executor, _collectstatic_cache_file(spec))
    if cached is None:
        return False
    try:
        current = _project_tree_hash(executor, spec)
    except ExecutorError:
        return False
    return cached.strip() == current


def _store_collectstatic_cache(executor: Executor, spec: ProjectSpec) -> None:
    try:
        current = _project_tree_hash(executor, spec)
    except ExecutorError:
        return
    state_dir = _state_dir(spec)
    executor.run(["mkdir", "-p", str(state_dir)], cwd=spec.path, as_user=spec.user)
    executor.write_text(_collectstatic_cache_file(spec), f"{current}\n", sudo=False)


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
            "--",
            ".",
            ":(exclude)venv",
            ":(exclude)staticfiles",
            ":(exclude)media",
            ":(exclude).speeddeploy",
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


def _ensure_python_django_compatibility(executor: Executor, spec: ProjectSpec) -> None:
    if getattr(executor, "dry_run", False):
        console.print("[yellow][dry-run] Would check Python/Django compatibility[/yellow]")
        return

    requirements_path = spec.path / "requirements.txt"
    django_requirement = _parse_django_requirement(requirements_path)
    if django_requirement is None:
        return

    operator, required_version = django_requirement
    python_output = executor.capture([spec.python, "--version"], cwd=spec.path)
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


def _search_project_file(executor: Executor, spec: ProjectSpec, needle: str) -> str:
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
    return executor.capture(command, cwd=spec.path)


def _preflight_django_settings(executor: Executor, spec: ProjectSpec) -> None:
    if getattr(executor, "dry_run", False):
        console.print("[yellow][dry-run] Would verify STATIC_ROOT and DEFAULT_AUTO_FIELD[/yellow]")
        return

    static_root_hit = _search_project_file(executor, spec, "STATIC_ROOT")
    if not static_root_hit:
        raise ExecutorError(
            "Le projet ne declare pas `STATIC_ROOT`. "
            "Ajoute par exemple `STATIC_ROOT = BASE_DIR / 'staticfiles'` dans le fichier de settings "
            "avant de lancer `collectstatic`."
        )

    auto_field_hit = _search_project_file(executor, spec, "DEFAULT_AUTO_FIELD")
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
        _ensure_git_safe_directory(executor, spec)
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
    _ensure_git_safe_directory(executor, spec)
    executor.run(["chown", "-R", f"{spec.user}:{spec.group}", str(spec.path)], sudo=True)


def _create_venv(executor: Executor, spec: ProjectSpec) -> None:
    requirements_path = _requirements_file(spec)
    if not executor.path_exists(requirements_path):
        raise ExecutorError(f"Missing requirements file: {requirements_path}")

    venv_python = spec.venv_bin / "python"
    if executor.path_exists(venv_python) and _requirements_cache_matches(executor, spec):
        console.print("[green]Virtualenv already up to date. Skipping dependency install.[/green]")
        return

    executor.run([spec.python, "-m", "venv", str(spec.venv)], cwd=spec.path)
    executor.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], cwd=spec.path)
    executor.run([str(spec.venv_bin / "pip"), "install", "-r", "requirements.txt"], cwd=spec.path)
    _store_requirements_cache(executor, spec)
    _normalize_worktree_ownership(executor, spec)


def _django_steps(executor: Executor, spec: ProjectSpec) -> None:
    executor.run([str(spec.venv_bin / "python"), "manage.py", "migrate"], cwd=spec.path)
    if _collectstatic_cache_matches(executor, spec):
        console.print("[green]collectstatic cache hit. Skipping static collection.[/green]")
        _normalize_worktree_ownership(executor, spec)
        return
    executor.run([str(spec.venv_bin / "python"), "manage.py", "collectstatic", "--noinput"], cwd=spec.path)
    _store_collectstatic_cache(executor, spec)
    _normalize_worktree_ownership(executor, spec)


def _render_gunicorn(executor: Executor, spec: ProjectSpec) -> bool:
    content = _render_template("gunicorn.service.j2", spec)
    changed = _write_if_changed(executor, Path("/etc/systemd/system") / f"{spec.project}.service", content, sudo=True)
    executor.run(["systemctl", "daemon-reload"], sudo=True)
    executor.run(["systemctl", "enable", f"{spec.project}.service"], sudo=True)
    return changed


def _render_web_server(executor: Executor, spec: ProjectSpec) -> bool:
    if spec.target.web_server == "apache":
        content = _render_template("apache.conf.j2", spec)
        changed = _write_if_changed(executor, Path("/etc/apache2/sites-available") / f"{spec.project}.conf", content, sudo=True)
        executor.run(["a2enmod", "proxy", "proxy_http", "headers"], sudo=True)
        executor.run(["a2ensite", f"{spec.project}.conf"], sudo=True)
        executor.run(["apache2ctl", "configtest"], sudo=True)
        return changed
    if spec.target.web_server == "nginx":
        content = _render_template("nginx.conf.j2", spec)
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

    def plan(self) -> list[str]:
        return build_plan(self.spec)

    def doctor(self, *, fix: bool = False) -> None:
        console.print(f"[bold]Project:[/bold] {self.spec.project}")
        console.print(f"[bold]Domain:[/bold] {self.spec.domain}")
        console.print(f"[bold]Branch:[/bold] {self.spec.branch}")
        console.print(f"[bold]Connection backend:[/bold] {self.spec.connection.backend}")
        if self.spec.connection.backend == "ssh":
            console.print(f"[bold]SSH host:[/bold] {self.spec.connection.host or 'unset'}")
            console.print(f"[bold]SSH user:[/bold] {self.spec.connection.user or self.spec.user}")
        console.print(f"[bold]Executor:[/bold] {self.executor.kind()}")
        console.print(f"[bold]Web server:[/bold] {self.spec.target.web_server}")
        console.print(f"[bold]App server:[/bold] {self.spec.target.app_server}")
        console.print(f"[bold]OS:[/bold] {self.spec.target.os}")
        console.print(f"[bold]Init system:[/bold] {self.spec.target.init_system}")
        console.print(f"[bold]Package manager:[/bold] {self.spec.target.package_manager}")
        if self.executor.path_exists(self.spec.path / ".git"):
            dirty_entries = _git_worktree_dirty(self.executor, self.spec)
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
        targets = [self.spec.path, self.spec.venv, self.spec.static_dir, self.spec.media_dir]
        seen: set[Path] = set()
        for target in targets:
            candidate = Path(target)
            if candidate in seen or not self.executor.path_exists(candidate):
                continue
            seen.add(candidate)
            self.executor.run(["chown", "-R", f"{self.spec.user}:{self.spec.group}", str(candidate)], sudo=True)
        _ensure_git_safe_directory(self.executor, self.spec)
        console.print("[green]Ownership and Git safety issues repaired.[/green]")

    def _sync_code(self, *, local_changes: LocalChangePolicy = "keep") -> None:
        _clone_or_update(self.executor, self.spec, local_changes=local_changes)
        _ensure_python_django_compatibility(self.executor, self.spec)
        _preflight_django_settings(self.executor, self.spec)
        _create_venv(self.executor, self.spec)
        _django_steps(self.executor, self.spec)

    def deploy(self, *, local_changes: LocalChangePolicy = "keep") -> None:
        _prepare_paths(self.executor, self.spec)
        _install_packages(self.executor, self.spec)
        self._sync_code(local_changes=local_changes)
        self.update_conf(restart=False)
        self.update_cert()
        self.restart()

    def update_code(self, *, local_changes: LocalChangePolicy = "keep") -> None:
        self._sync_code(local_changes=local_changes)
        self.restart()

    def update_conf(self, *, restart: bool = True) -> None:
        gunicorn_changed = _render_gunicorn(self.executor, self.spec)
        web_changed = _render_web_server(self.executor, self.spec)
        if restart:
            if gunicorn_changed or web_changed:
                self.restart()
            else:
                console.print("[green]Configuration already up to date.[/green]")

    def update(self, *, local_changes: LocalChangePolicy = "keep") -> None:
        self._sync_code(local_changes=local_changes)
        self.update_conf(restart=False)
        self.update_cert()
        self.restart()

    def update_cert(self) -> None:
        _provision_ssl(self.executor, self.spec)
        _reload_web_server(self.executor, self.spec)

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
        self.executor.run([str(self.spec.venv_bin / "python"), "manage.py", "createsuperuser"], cwd=self.spec.path)


def build_engine(spec: ProjectSpec, *, dry_run: bool = False) -> DeploymentEngine:
    executor = _select_executor(spec, dry_run=dry_run)
    return DeploymentEngine(spec=spec, executor=executor)
