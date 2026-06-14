"""Django project helpers."""

from __future__ import annotations

from rich.console import Console

from .config import ProjectConfig
from .runner import is_dry_run, run

console = Console()


def create_venv(config: ProjectConfig) -> None:
    """Create the virtual environment and install Python dependencies."""
    run([config.python, "-m", "venv", str(config.venv)], cwd=config.path)
    run([str(config.venv_bin / "python"), "-m", "pip", "install", "--upgrade", "pip"], cwd=config.path)
    run([str(config.venv_bin / "pip"), "install", "-r", "requirements.txt"], cwd=config.path)
    run(["chown", "-R", f"{config.user}:{config.group}", str(config.path)], sudo=True)
    if not is_dry_run():
        console.print("[green]Python environment installed.[/green]")


def migrate(config: ProjectConfig) -> None:
    """Run Django database migrations."""
    run([str(config.venv_bin / "python"), "manage.py", "migrate"], cwd=config.path)


def collectstatic(config: ProjectConfig) -> None:
    """Collect Django static files."""
    run([str(config.venv_bin / "python"), "manage.py", "collectstatic", "--noinput"], cwd=config.path)


def django_prepare(config: ProjectConfig) -> None:
    """Run the Django preparation steps."""
    migrate(config)
    collectstatic(config)
    if not is_dry_run():
        console.print("[green]Migrations and static files completed.[/green]")


def createsuperuser(config: ProjectConfig) -> None:
    """Create a Django superuser interactively."""
    run([str(config.venv_bin / "python"), "manage.py", "createsuperuser"], cwd=config.path)
