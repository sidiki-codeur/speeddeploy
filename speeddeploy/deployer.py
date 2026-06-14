"""Deployment orchestration."""

from __future__ import annotations

from rich.console import Console

from .apache import render_apache_config
from .config import ProjectConfig
from .django import create_venv, django_prepare
from .gunicorn import render_gunicorn_service, restart_gunicorn
from .runner import is_dry_run, run

console = Console()


class DeploymentError(RuntimeError):
    """Raised when a deployment step cannot continue safely."""


def build_deployment_plan(config: ProjectConfig) -> list[str]:
    """Return the ordered deployment steps for a project."""
    steps = [
        f"Prepare target directory: {config.path}",
        f"Clone or update repository: {config.repo}",
        f"Create virtual environment: {config.venv}",
        "Run Django migrations and collectstatic",
        f"Render Gunicorn service: {config.service_name}.service",
        f"Render Apache vhost: {config.project}.conf",
        f"Restart Gunicorn service: {config.service_name}.service",
    ]
    if config.target.ssl_provider:
        steps.append(f"Optional SSL provisioning: {config.target.ssl_provider}")
    return steps


def _prepare_directory(config: ProjectConfig) -> None:
    """Create the target directory and make it writable by the deployment user."""
    run(["mkdir", "-p", str(config.path)], sudo=True)
    run(["chown", "-R", f"{config.user}:{config.group}", str(config.path)], sudo=True)
    run(["chmod", "-R", "775", str(config.path)], sudo=True)


def init_project(config: ProjectConfig) -> None:
    """Prepare the target directory structure."""
    _prepare_directory(config)
    if not is_dry_run():
        console.print(f"[green]Target directory prepared: {config.path}[/green]")


def clone_or_update(config: ProjectConfig) -> None:
    """Clone the repository if needed, otherwise pull the latest changes."""
    path = config.path
    _prepare_directory(config)

    if (path / ".git").exists():
        run(["git", "pull"], cwd=path)
    else:
        if path.exists():
            if not path.is_dir():
                raise DeploymentError(f"The path {path} exists but is not a directory.")
            if any(path.iterdir()):
                raise DeploymentError(
                    f"The directory {path} already exists and is not empty. "
                    "Move it or empty it before cloning."
                )
        run(["git", "clone", config.repo, str(path)], cwd=path.parent)

    run(["chown", "-R", f"{config.user}:{config.group}", str(config.path)], sudo=True)
    if not is_dry_run():
        console.print("[green]Source code ready.[/green]")


def full_deploy(config: ProjectConfig) -> None:
    """Run the complete deployment pipeline."""
    clone_or_update(config)
    create_venv(config)
    django_prepare(config)
    render_gunicorn_service(config)
    render_apache_config(config)
    restart_gunicorn(config)
    if not is_dry_run():
        console.print(f"[bold green]Deployment finished: http://{config.domain}[/bold green]")


def update_project(config: ProjectConfig) -> None:
    """Update code and refresh runtime services."""
    clone_or_update(config)
    create_venv(config)
    django_prepare(config)
    render_gunicorn_service(config)
    render_apache_config(config)
    restart_gunicorn(config)
    if not is_dry_run():
        console.print(f"[bold green]Update finished: {config.domain}[/bold green]")
