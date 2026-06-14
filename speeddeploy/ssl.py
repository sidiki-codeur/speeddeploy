"""SSL provisioning helpers."""

from __future__ import annotations

from rich.console import Console

from .config import ProjectConfig
from .runner import run

console = Console()


def install_ssl(config: ProjectConfig) -> None:
    """Install certbot and provision a certificate for the configured domain."""
    run(["apt-get", "update"], sudo=True)
    run(["apt-get", "install", "-y", "certbot", "python3-certbot-apache"], sudo=True)
    run(["certbot", "--apache", "-d", config.domain], sudo=True)
    console.print(f"[green]SSL activé pour {config.domain}[/green]")
