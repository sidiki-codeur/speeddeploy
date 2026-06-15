"""Environment file rendering for deployments.

Secrets declared under the project's ``env:`` section are rendered into a
``.env`` file on the target host with restrictive permissions and referenced by
the systemd unit through ``EnvironmentFile=``. The file contents are never
echoed to the console.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .executor import Executor
from .models import ProjectSpec

console = Console()

_NEEDS_QUOTING = set(" \t\n\"'#$&|;<>(){}*?!`\\")


def render_env_content(values: dict[str, str]) -> str:
    """Render a mapping as ``KEY=value`` lines suitable for an env file."""
    lines: list[str] = []
    for key, raw in values.items():
        value = "" if raw is None else str(raw)
        if value == "" or any(char in _NEEDS_QUOTING for char in value):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key}="{escaped}"')
        else:
            lines.append(f"{key}={value}")
    return ("\n".join(lines) + "\n") if lines else ""


def write_env_file(executor: Executor, spec: ProjectSpec, env_file: Path) -> bool:
    """Write the project's ``.env`` file. Returns True when env vars exist."""
    if not spec.env:
        return False
    content = render_env_content(spec.env)
    if getattr(executor, "dry_run", False):
        console.print(f"[yellow][dry-run] Would write {len(spec.env)} env var(s) to {env_file} (mode 0640)[/yellow]")
        return True
    executor.run(["mkdir", "-p", str(env_file.parent)], sudo=True)
    # write_text never prints the file contents, so secrets stay out of logs.
    executor.write_text(env_file, content, sudo=True, mode="0640")
    executor.run(["chown", f"{spec.user}:{spec.group}", str(env_file)], sudo=True)
    console.print(f"[green]Environment file written: {env_file}[/green]")
    return True
