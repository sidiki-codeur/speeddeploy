"""Post-deployment HTTP healthchecks.

The check is performed with ``curl`` against ``127.0.0.1`` using the project's
domain as the ``Host`` header, so it exercises the real web server vhost and
the Gunicorn socket without depending on public DNS or TLS being ready yet.
"""

from __future__ import annotations

import time

from rich.console import Console

from .executor import Executor, ExecutorError
from .models import ProjectSpec

console = Console()


class HealthcheckError(RuntimeError):
    """Raised when the post-deployment healthcheck never succeeds."""


def _curl_status(executor: Executor, url: str, host: str, timeout: int) -> str:
    command = [
        "curl",
        "-sS",
        "-o",
        "/dev/null",
        "-H",
        f"Host: {host}",
        "-w",
        "%{http_code}",
        "--max-time",
        str(timeout),
        url,
    ]
    return executor.capture(command).strip()


def run_healthcheck(executor: Executor, spec: ProjectSpec) -> None:
    """Probe the deployed site and raise HealthcheckError on persistent failure."""
    hc = spec.healthcheck
    if not hc.enabled:
        return
    if getattr(executor, "dry_run", False):
        console.print("[yellow][dry-run] Would run post-deployment healthcheck[/yellow]")
        return

    host = hc.host or spec.domain
    authority = f"127.0.0.1:{hc.port}" if hc.port else "127.0.0.1"
    path = hc.path if hc.path.startswith("/") else f"/{hc.path}"
    url = f"http://{authority}{path}"
    expected = set(hc.expect_status)
    last_detail = "no response"

    for attempt in range(1, hc.retries + 1):
        code = ""
        try:
            code = _curl_status(executor, url, host, hc.timeout)
        except ExecutorError as exc:
            last_detail = str(exc)
        if code.isdigit() and int(code) in expected:
            console.print(f"[green]Healthcheck passed (HTTP {code}) on attempt {attempt}/{hc.retries}.[/green]")
            return
        if code:
            last_detail = f"HTTP {code}"
        console.print(
            f"[yellow]Healthcheck attempt {attempt}/{hc.retries} failed ({last_detail}). "
            f"Retrying in {hc.delay}s...[/yellow]"
        )
        if attempt < hc.retries and hc.delay > 0:
            time.sleep(hc.delay)

    raise HealthcheckError(
        f"Healthcheck failed for {url} (Host: {host}). "
        f"Last result: {last_detail}; expected one of {sorted(expected)}."
    )
