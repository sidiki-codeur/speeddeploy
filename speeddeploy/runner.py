"""Command execution helpers."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Sequence

from rich.console import Console

console = Console()
_DRY_RUN = False


class CommandError(RuntimeError):
    """Raised when an external command fails."""


def set_dry_run(enabled: bool) -> None:
    """Enable or disable dry-run mode."""
    global _DRY_RUN
    _DRY_RUN = bool(enabled)


def is_dry_run() -> bool:
    """Return the current dry-run state."""
    return _DRY_RUN


def _normalize_command(command: Sequence[str]) -> list[str]:
    if not command:
        raise ValueError("The command cannot be empty.")
    return [str(part) for part in command]


def run(
    command: Sequence[str],
    *,
    sudo: bool = False,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[None]:
    """Run a command without shell interpolation."""
    args = _normalize_command(command)
    if sudo:
        args = ["sudo", *args]

    command_str = shlex.join(args)
    if _DRY_RUN:
        console.print(f"[yellow][dry-run] $ {command_str}[/yellow]")
        return subprocess.CompletedProcess(args=args, returncode=0)

    console.print(f"[cyan]$ {command_str}[/cyan]")

    try:
        return subprocess.run(args, cwd=str(cwd) if cwd is not None else None, check=True)
    except FileNotFoundError as exc:
        message = f"Command not found: {args[0]}"
        console.print(f"[red]{message}[/red]")
        raise CommandError(message) from exc
    except subprocess.CalledProcessError as exc:
        message = f"Command failed ({exc.returncode}): {command_str}"
        console.print(f"[red]{message}[/red]")
        raise CommandError(message) from exc
