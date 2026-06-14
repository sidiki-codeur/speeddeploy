"""SSL provisioning helpers."""

from __future__ import annotations

from rich.console import Console

from .config import ProjectConfig
from .runner import is_dry_run, run

console = Console()


def _package_command(manager: str) -> tuple[list[str], list[str] | None]:
    manager = manager.lower()
    if manager == "apt":
        return ["apt-get", "install", "-y"], ["apt-get", "update"]
    if manager == "dnf":
        return ["dnf", "install", "-y"], None
    if manager == "yum":
        return ["yum", "install", "-y"], None
    if manager == "apk":
        return ["apk", "add"], None
    if manager == "pacman":
        return ["pacman", "-Sy", "--noconfirm"], None
    raise ValueError(f"Unsupported package manager: {manager}")


def install_ssl(config: ProjectConfig) -> None:
    """Install certbot and provision a certificate for the configured domain."""
    if config.target.ssl_provider in {"", "none", "disabled"}:
        if not is_dry_run():
            console.print("[green]SSL provisioning skipped.[/green]")
        return

    installer, update_cmd = _package_command(config.target.package_manager)
    web_server = config.target.web_server.lower()
    packages = ["certbot"]
    if web_server == "apache":
        packages.append("python3-certbot-apache")
    elif web_server == "nginx":
        packages.append("python3-certbot-nginx")

    if update_cmd is not None:
        run(update_cmd, sudo=True)
    run([*installer, *packages], sudo=True)

    if config.target.web_server == "nginx":
        run(["certbot", "--nginx", "-d", config.domain], sudo=True)
    else:
        run(["certbot", "--apache", "-d", config.domain], sudo=True)

    if not is_dry_run():
        console.print(f"[green]SSL enabled for {config.domain}[/green]")
