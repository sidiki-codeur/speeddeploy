"""Deployment orchestration."""

from __future__ import annotations

from rich.console import Console

from .apache import render_apache_config
from .config import ProjectConfig
from .django import create_venv, django_prepare
from .gunicorn import render_gunicorn_service, restart_gunicorn
from .runner import run

console = Console()


class DeploymentError(RuntimeError):
    """Raised when a deployment step cannot continue safely."""


def _prepare_directory(config: ProjectConfig) -> None:
    """Create the target directory and ensure it is writable by the deployment user."""
    run(["mkdir", "-p", str(config.path)], sudo=True)
    run(["chown", "-R", f"{config.user}:{config.group}", str(config.path)], sudo=True)
    run(["chmod", "-R", "775", str(config.path)], sudo=True)


def init_project(config: ProjectConfig) -> None:
    """Prepare the target directory structure."""
    _prepare_directory(config)
    console.print(f"[green]Dossier préparé : {config.path}[/green]")


def clone_or_update(config: ProjectConfig) -> None:
    """Clone the repository if needed, otherwise pull the latest changes."""
    path = config.path
    _prepare_directory(config)

    if (path / ".git").exists():
        run(["git", "pull"], cwd=path)
    else:
        if path.exists():
            if not path.is_dir():
                raise DeploymentError(f"Le chemin {path} existe mais n'est pas un dossier.")
            if any(path.iterdir()):
                raise DeploymentError(
                    f"Le dossier {path} existe déjà et n'est pas vide. "
                    "Déplacez-le ou videz-le avant le clonage."
                )
        run(["git", "clone", config.repo, str(path)], cwd=path.parent)

    run(["chown", "-R", f"{config.user}:{config.group}", str(config.path)], sudo=True)
    console.print("[green]Code source prêt.[/green]")


def full_deploy(config: ProjectConfig) -> None:
    """Run the complete deployment pipeline."""
    clone_or_update(config)
    create_venv(config)
    django_prepare(config)
    render_gunicorn_service(config)
    render_apache_config(config)
    restart_gunicorn(config)
    console.print(f"[bold green]Déploiement terminé : http://{config.domain}[/bold green]")


def update_project(config: ProjectConfig) -> None:
    """Update code and refresh runtime services."""
    clone_or_update(config)
    create_venv(config)
    django_prepare(config)
    render_gunicorn_service(config)
    render_apache_config(config)
    restart_gunicorn(config)
    console.print(f"[bold green]Mise à jour terminée : {config.domain}[/bold green]")
