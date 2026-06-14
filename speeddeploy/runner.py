"""Command execution helpers."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Sequence

from rich.console import Console

console = Console()


class CommandError(RuntimeError):
    """Raised when an external command fails."""


def _normalize_command(command: Sequence[str]) -> list[str]:
    if not command:
        raise ValueError("La commande ne peut pas être vide.")
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
    console.print(f"[cyan]$ {command_str}[/cyan]")

    try:
        return subprocess.run(args, cwd=str(cwd) if cwd is not None else None, check=True)
    except FileNotFoundError as exc:
        message = f"Commande introuvable: {args[0]}"
        console.print(f"[red]{message}[/red]")
        raise CommandError(message) from exc
    except subprocess.CalledProcessError as exc:
        message = f"Échec de la commande ({exc.returncode}): {command_str}"
        console.print(f"[red]{message}[/red]")
        raise CommandError(message) from exc
