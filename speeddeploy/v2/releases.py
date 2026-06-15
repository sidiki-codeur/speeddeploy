"""Release directory management for atomic, rollback-capable deployments.

Layout under ``spec.path`` (the deploy root)::

    releases/<timestamp>/      one git checkout per deploy (with its own venv)
    current -> releases/<ts>   symlink the running app and configs point at
    shared/                    state shared across releases
        staticfiles/           collected static files
        media/                 user uploads
        backups/               database dumps
        .env                   secrets (mode 0640)
        .speeddeploy/          deployment state

Switching the ``current`` symlink is an atomic rename, so a deploy never leaves
the site pointing at a half-built release, and a rollback is just a swap back.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from rich.console import Console

from .executor import Executor, ExecutorError
from .models import ProjectSpec

console = Console()

SHARED_SUBDIRS = ("staticfiles", "media", "backups", ".speeddeploy")


def ensure_release_layout(executor: Executor, spec: ProjectSpec) -> None:
    """Create the releases/shared directory skeleton owned by the deploy user."""
    executor.run(["mkdir", "-p", str(spec.path)], sudo=True)
    directories = [spec.releases_dir, spec.shared_dir]
    directories.extend(spec.shared_dir / name for name in SHARED_SUBDIRS)
    for directory in directories:
        executor.run(["mkdir", "-p", str(directory)], sudo=True)
    executor.run(["chown", "-R", f"{spec.user}:{spec.group}", str(spec.path)], sudo=True)


def create_release(executor: Executor, spec: ProjectSpec, release_dir: Path) -> None:
    """Clone the configured branch into a fresh release directory."""
    if executor.path_exists(release_dir):
        raise ExecutorError(f"Release directory already exists: {release_dir}")
    executor.run(
        ["git", "clone", "--branch", spec.branch, "--single-branch", "--depth", "1", spec.repo, str(release_dir)],
        cwd=spec.releases_dir,
        as_user=spec.user,
    )


def link_shared(executor: Executor, spec: ProjectSpec, release_dir: Path, *, link_env: bool) -> None:
    """Symlink shared static/media/.env into a release so the app sees them."""
    dir_links = {
        release_dir / spec.static_dir.name: spec.shared_dir / "staticfiles",
        release_dir / spec.media_dir.name: spec.shared_dir / "media",
    }
    for link, target in dir_links.items():
        executor.run(["mkdir", "-p", str(target)], as_user=spec.user)
        executor.run(["rm", "-rf", str(link)], as_user=spec.user)
        executor.run(["ln", "-sfn", str(target), str(link)], as_user=spec.user)
    if link_env:
        env_link = release_dir / ".env"
        executor.run(["rm", "-rf", str(env_link)], as_user=spec.user)
        executor.run(["ln", "-sfn", str(spec.shared_dir / ".env"), str(env_link)], as_user=spec.user)


def switch_current(executor: Executor, spec: ProjectSpec, release_dir: Path) -> None:
    """Atomically repoint the ``current`` symlink at ``release_dir``."""
    link = spec.current_link
    tmp = f"{link}.tmp"
    script = (
        f"ln -sfn {shlex.quote(str(release_dir))} {shlex.quote(tmp)} && "
        f"mv -Tf {shlex.quote(tmp)} {shlex.quote(str(link))}"
    )
    executor.run(["bash", "-lc", script], as_user=spec.user)
    console.print(f"[green]current -> {release_dir}[/green]")


def list_releases(executor: Executor, spec: ProjectSpec) -> list[str]:
    """Return release directory names sorted oldest-first."""
    if getattr(executor, "dry_run", False) or not executor.path_exists(spec.releases_dir):
        return []
    try:
        listing = executor.capture(
            ["bash", "-lc", f"ls -1 {shlex.quote(str(spec.releases_dir))} 2>/dev/null"],
            as_user=spec.user,
        )
    except ExecutorError:
        return []
    names = [line.strip() for line in listing.splitlines() if line.strip()]
    return sorted(names)


def current_release(executor: Executor, spec: ProjectSpec) -> Path | None:
    """Return the release directory the ``current`` symlink points at."""
    if getattr(executor, "dry_run", False) or not executor.path_exists(spec.current_link):
        return None
    try:
        target = executor.capture(
            ["readlink", "-f", str(spec.current_link)],
            as_user=spec.user,
        ).strip()
    except ExecutorError:
        return None
    return Path(target) if target else None


def previous_release(executor: Executor, spec: ProjectSpec, *, exclude: Path | None = None) -> Path | None:
    """Return the most recent release that is not the current/excluded one."""
    names = list_releases(executor, spec)
    excluded = {exclude.name} if exclude else set()
    current = current_release(executor, spec)
    if current:
        excluded.add(current.name)
    candidates = [name for name in names if name not in excluded]
    if not candidates:
        return None
    return spec.releases_dir / candidates[-1]


def prune_releases(executor: Executor, spec: ProjectSpec, *, protect: set[str] | None = None) -> None:
    """Delete old releases, keeping the newest ``spec.releases.keep`` and any protected names."""
    keep = spec.releases.keep
    names = list_releases(executor, spec)
    protected = set(protect or set())
    current = current_release(executor, spec)
    if current:
        protected.add(current.name)
    survivors = names[-keep:] if keep > 0 else names
    removable = [name for name in names if name not in survivors and name not in protected]
    for name in removable:
        executor.run(["rm", "-rf", str(spec.releases_dir / name)], sudo=True)
    if removable:
        console.print(f"[green]Pruned {len(removable)} old release(s).[/green]")
