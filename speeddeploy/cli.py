"""CLI entry point for SpeedDeploy."""

from __future__ import annotations

from collections.abc import Callable

import typer
from rich.console import Console

from .config import ConfigError, load_config
from .deployer import DeploymentError, clone_or_update, full_deploy, init_project, update_project
from .django import create_venv, createsuperuser, django_prepare
from .gunicorn import logs_gunicorn, render_gunicorn_service, restart_gunicorn, status_gunicorn
from .apache import render_apache_config
from .runner import CommandError, run
from .ssl import install_ssl

app = typer.Typer(add_completion=False, help="SpeedDeploy deployment CLI.")
console = Console()


def _get_config(project: str):
    try:
        return load_config(project)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _execute(action: Callable[[], None]) -> None:
    try:
        action()
    except (CommandError, DeploymentError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command("init")
def init_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: init_project(config))


@app.command("clone")
def clone_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: clone_or_update(config))


@app.command("venv")
def venv_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: create_venv(config))


@app.command("django")
def django_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: django_prepare(config))


@app.command("gunicorn")
def gunicorn_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: render_gunicorn_service(config))


@app.command("apache")
def apache_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: render_apache_config(config))


@app.command("deploy")
def deploy_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: full_deploy(config))


@app.command("update")
def update_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: update_project(config))


@app.command("restart")
def restart_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: restart_gunicorn(config))
    _execute(lambda: run(["systemctl", "reload", "apache2"], sudo=True))


@app.command("status")
def status_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: status_gunicorn(config))


@app.command("logs")
def logs_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: logs_gunicorn(config))
    _execute(lambda: run(["tail", "-n", "100", f"/var/log/apache2/{config.project}_error.log"], sudo=True))


@app.command("ssl")
def ssl_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: install_ssl(config))


@app.command("superuser")
def superuser_command(project: str = typer.Argument(..., help="Nom du projet ou fichier YAML.")) -> None:
    config = _get_config(project)
    _execute(lambda: createsuperuser(config))


if __name__ == "__main__":
    app()
