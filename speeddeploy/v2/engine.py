"""V2 deployment engine and backend selection."""

from __future__ import annotations

from dataclasses import dataclass
import shlex
import re
from pathlib import Path

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


def build_plan(spec: ProjectSpec) -> list[str]:
    steps = [
        f"Select backend: {spec.connection.backend}",
        f"Install system packages via {spec.target.package_manager}",
        f"Prepare directory: {spec.path}",
        f"Clone or update repository: {spec.repo}",
        "Check Python and Django version compatibility",
        f"Create virtualenv: {spec.venv}",
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


def _ensure_git_safe_directory(executor: Executor, spec: ProjectSpec) -> None:
    if not executor.path_exists(spec.path / ".git"):
        return

    configured = executor.capture(["git", "config", "--global", "--get-all", "safe.directory"], cwd=spec.path)
    if str(spec.path) in {line.strip() for line in configured.splitlines() if line.strip()}:
        return

    executor.run(["git", "config", "--global", "--add", "safe.directory", str(spec.path)], cwd=spec.path)


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


def _clone_or_update(executor: Executor, spec: ProjectSpec) -> None:
    git_dir = spec.path / ".git"
    if executor.path_exists(git_dir):
        _ensure_git_safe_directory(executor, spec)
        executor.run(["git", "pull"], cwd=spec.path, sudo=False)
        executor.run(["chown", "-R", f"{spec.user}:{spec.group}", str(spec.path)], sudo=True)
        return

    if executor.path_exists(spec.path) and not executor.is_empty_dir(spec.path):
        raise ExecutorError(
            f"The deployment path {spec.path} already exists and is not empty. "
            "Choose an empty directory or a clean target."
        )

    executor.run(["git", "clone", spec.repo, str(spec.path)], cwd=spec.path.parent, sudo=False)
    _ensure_git_safe_directory(executor, spec)
    executor.run(["chown", "-R", f"{spec.user}:{spec.group}", str(spec.path)], sudo=True)


def _create_venv(executor: Executor, spec: ProjectSpec) -> None:
    executor.run([spec.python, "-m", "venv", str(spec.venv)], cwd=spec.path)
    executor.run([str(spec.venv_bin / "python"), "-m", "pip", "install", "--upgrade", "pip"], cwd=spec.path)
    executor.run([str(spec.venv_bin / "pip"), "install", "-r", "requirements.txt"], cwd=spec.path)


def _django_steps(executor: Executor, spec: ProjectSpec) -> None:
    executor.run([str(spec.venv_bin / "python"), "manage.py", "migrate"], cwd=spec.path)
    executor.run([str(spec.venv_bin / "python"), "manage.py", "collectstatic", "--noinput"], cwd=spec.path)


def _render_gunicorn(executor: Executor, spec: ProjectSpec) -> None:
    content = _render_template("gunicorn.service.j2", spec)
    executor.write_text(Path("/etc/systemd/system") / f"{spec.project}.service", content, sudo=True)
    executor.run(["systemctl", "daemon-reload"], sudo=True)
    executor.run(["systemctl", "enable", f"{spec.project}.service"], sudo=True)


def _render_web_server(executor: Executor, spec: ProjectSpec) -> None:
    if spec.target.web_server == "apache":
        content = _render_template("apache.conf.j2", spec)
        executor.write_text(Path("/etc/apache2/sites-available") / f"{spec.project}.conf", content, sudo=True)
        executor.run(["a2enmod", "proxy", "proxy_http", "headers"], sudo=True)
        executor.run(["a2ensite", f"{spec.project}.conf"], sudo=True)
        executor.run(["apache2ctl", "configtest"], sudo=True)
        executor.run(["systemctl", "reload", "apache2"], sudo=True)
        return
    if spec.target.web_server == "nginx":
        content = _render_template("nginx.conf.j2", spec)
        executor.write_text(Path("/etc/nginx/sites-available") / f"{spec.project}.conf", content, sudo=True)
        executor.run(["ln", "-sf", f"/etc/nginx/sites-available/{spec.project}.conf", f"/etc/nginx/sites-enabled/{spec.project}.conf"], sudo=True)
        executor.run(["nginx", "-t"], sudo=True)
        executor.run(["systemctl", "reload", "nginx"], sudo=True)
        return
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


@dataclass(slots=True)
class DeploymentEngine:
    """High-level deployment orchestration for V2."""

    spec: ProjectSpec
    executor: Executor

    def plan(self) -> list[str]:
        return build_plan(self.spec)

    def doctor(self) -> None:
        console.print(f"[bold]Project:[/bold] {self.spec.project}")
        console.print(f"[bold]Domain:[/bold] {self.spec.domain}")
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
        for idx, step in enumerate(self.plan(), start=1):
            console.print(f"{idx}. {step}")

    def deploy(self) -> None:
        _prepare_paths(self.executor, self.spec)
        _install_packages(self.executor, self.spec)
        _clone_or_update(self.executor, self.spec)
        _ensure_python_django_compatibility(self.executor, self.spec)
        _preflight_django_settings(self.executor, self.spec)
        _create_venv(self.executor, self.spec)
        _django_steps(self.executor, self.spec)
        _render_gunicorn(self.executor, self.spec)
        _render_web_server(self.executor, self.spec)
        _provision_ssl(self.executor, self.spec)
        self.restart()

    def update(self) -> None:
        _clone_or_update(self.executor, self.spec)
        _ensure_python_django_compatibility(self.executor, self.spec)
        _preflight_django_settings(self.executor, self.spec)
        _create_venv(self.executor, self.spec)
        _django_steps(self.executor, self.spec)
        _render_gunicorn(self.executor, self.spec)
        _render_web_server(self.executor, self.spec)
        _provision_ssl(self.executor, self.spec)
        self.restart()

    def restart(self) -> None:
        self.executor.run(["systemctl", "restart", f"{self.spec.project}.service"], sudo=True)
        if self.spec.target.web_server == "apache":
            self.executor.run(["systemctl", "reload", "apache2"], sudo=True)
        elif self.spec.target.web_server == "nginx":
            self.executor.run(["systemctl", "reload", "nginx"], sudo=True)

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
