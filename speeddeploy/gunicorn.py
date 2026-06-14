"""Gunicorn service rendering and lifecycle helpers."""

from __future__ import annotations

import tempfile
from pathlib import Path

from jinja2 import Environment, PackageLoader
from rich.console import Console

from .config import ProjectConfig
from .runner import is_dry_run, run

console = Console()
_TEMPLATE_ENV = Environment(
    loader=PackageLoader("speeddeploy", "templates"),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render_template(template_name: str, config: ProjectConfig) -> str:
    template = _TEMPLATE_ENV.get_template(template_name)
    return template.render(
        project=config.project,
        domain=config.domain,
        repo=config.repo,
        path=str(config.path),
        user=config.user,
        group=config.group,
        wsgi=config.wsgi,
        python=config.python,
        venv=str(config.venv),
        static_dir=str(config.static_dir),
        media_dir=str(config.media_dir),
        workers=config.workers,
    )


def render_gunicorn_service(config: ProjectConfig) -> Path:
    """Render and install the systemd service, then start Gunicorn."""
    content = _render_template("gunicorn.service.j2", config)
    temp_path = Path(tempfile.gettempdir()) / f"{config.project}.service"
    target_path = Path("/etc/systemd/system") / f"{config.project}.service"

    if is_dry_run():
        console.print(f"[yellow][dry-run] Would render Gunicorn service to {target_path}[/yellow]")
        return target_path

    temp_path.write_text(content, encoding="utf-8")

    try:
        run(["install", "-m", "644", str(temp_path), str(target_path)], sudo=True)
        run(["systemctl", "daemon-reload"], sudo=True)
        run(["systemctl", "enable", f"{config.project}.service"], sudo=True)
        run(["systemctl", "restart", f"{config.project}.service"], sudo=True)
    finally:
        temp_path.unlink(missing_ok=True)

    if not is_dry_run():
        console.print("[green]Gunicorn service enabled.[/green]")
    return target_path


def restart_gunicorn(config: ProjectConfig) -> None:
    """Restart the Gunicorn service."""
    run(["systemctl", "restart", f"{config.project}.service"], sudo=True)
    if not is_dry_run():
        console.print("[green]Gunicorn restarted.[/green]")


def status_gunicorn(config: ProjectConfig) -> None:
    """Show the Gunicorn service status."""
    run(["systemctl", "status", f"{config.project}.service", "--no-pager"], sudo=True)


def logs_gunicorn(config: ProjectConfig) -> None:
    """Show recent Gunicorn logs."""
    run(["journalctl", "-u", f"{config.project}.service", "-n", "100", "--no-pager"], sudo=True)
