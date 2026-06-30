"""SSL provisioning helpers."""

from __future__ import annotations

from collections.abc import Mapping

from rich.console import Console

from .certbot import build_certbot_command
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


def _as_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _ssl_options(config: ProjectConfig) -> Mapping[str, object]:
    options = config.extras.get("ssl")
    return options if isinstance(options, Mapping) else {}


def install_ssl(config: ProjectConfig) -> None:
    """Install certbot and provision a certificate for the configured domain."""
    if config.target.ssl_provider in {"", "none", "disabled"}:
        if not is_dry_run():
            console.print("[green]SSL provisioning skipped.[/green]")
        return

    ssl = _ssl_options(config)
    if not _as_bool(ssl.get("enabled", True), default=True):
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
    run(
        build_certbot_command(
            web_server=web_server,
            domain=config.domain,
            email=str(ssl.get("email")) if ssl.get("email") else None,
            redirect=_as_bool(ssl.get("redirect", True), default=True),
            staging=_as_bool(ssl.get("staging", False)),
            agree_tos=_as_bool(ssl.get("agree_tos", True), default=True),
        ),
        sudo=True,
    )

    if not is_dry_run():
        console.print(f"[green]SSL enabled for {config.domain}[/green]")
