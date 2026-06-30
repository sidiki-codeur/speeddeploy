"""Certbot command helpers."""

from __future__ import annotations


def build_certbot_command(
    *,
    web_server: str,
    domain: str,
    email: str | None = None,
    redirect: bool = True,
    staging: bool = False,
    agree_tos: bool = True,
) -> list[str]:
    """Build a non-interactive certbot command for the selected web server."""
    server = web_server.lower()
    if server == "apache":
        command = ["certbot", "--apache", "-d", domain]
    elif server == "nginx":
        command = ["certbot", "--nginx", "-d", domain]
    else:
        command = ["certbot", "--standalone", "-d", domain]

    command.append("--non-interactive")
    if agree_tos:
        command.append("--agree-tos")
    if email:
        command.extend(["--email", email])
    else:
        command.append("--register-unsafely-without-email")
    if server in {"apache", "nginx"}:
        command.append("--redirect" if redirect else "--no-redirect")
    if staging:
        command.append("--staging")
    return command
