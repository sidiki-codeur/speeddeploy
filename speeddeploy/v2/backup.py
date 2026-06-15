"""Database backups taken before running migrations.

Credentials are written to a temporary file with ``0600`` permissions and
referenced through ``PGPASSFILE`` / ``--defaults-extra-file`` so the password is
never passed on the command line (which the executor echoes to the console).
"""

from __future__ import annotations

import shlex
from pathlib import Path

from rich.console import Console

from .executor import Executor, ExecutorError
from .models import DatabaseSpec, ProjectSpec

console = Console()

_EXTENSIONS = {"postgres": "dump", "mysql": "sql", "sqlite": "sqlite3"}


def _prune(executor: Executor, spec: ProjectSpec, backup_dir: Path, extension: str, keep: int) -> None:
    pattern = shlex.quote(f"{backup_dir}/{spec.project}-*.{extension}")
    script = f"ls -1t {pattern} 2>/dev/null | tail -n +{keep + 1} | xargs -r rm -f"
    try:
        executor.run(["bash", "-lc", script], as_user=spec.user)
    except ExecutorError:
        console.print("[yellow]Could not prune old database backups (continuing).[/yellow]")


def _backup_postgres(executor: Executor, spec: ProjectSpec, db: DatabaseSpec, outfile: Path, backup_dir: Path) -> None:
    port = db.port or 5432
    passfile = backup_dir / f".pgpass-{spec.project}"
    pg_line = f"{db.host}:{port}:{db.name}:{db.user or spec.user}:{db.password or ''}\n"
    executor.write_text(passfile, pg_line, sudo=False, mode="0600")
    dump = (
        f"PGPASSFILE={shlex.quote(str(passfile))} pg_dump "
        f"-h {shlex.quote(db.host)} -p {port} -U {shlex.quote(db.user or spec.user)} "
        f"-Fc -f {shlex.quote(str(outfile))} {shlex.quote(db.name)}"
    )
    try:
        executor.run(["bash", "-lc", dump], as_user=spec.user)
    finally:
        executor.run(["rm", "-f", str(passfile)], as_user=spec.user)


def _backup_mysql(executor: Executor, spec: ProjectSpec, db: DatabaseSpec, outfile: Path, backup_dir: Path) -> None:
    port = db.port or 3306
    conf = backup_dir / f".my-{spec.project}.cnf"
    conf_body = (
        "[client]\n"
        f"user={db.user or spec.user}\n"
        f"password={db.password or ''}\n"
        f"host={db.host}\n"
        f"port={port}\n"
    )
    executor.write_text(conf, conf_body, sudo=False, mode="0600")
    dump = (
        f"mysqldump --defaults-extra-file={shlex.quote(str(conf))} "
        f"{shlex.quote(db.name)} > {shlex.quote(str(outfile))}"
    )
    try:
        executor.run(["bash", "-lc", dump], as_user=spec.user)
    finally:
        executor.run(["rm", "-f", str(conf)], as_user=spec.user)


def _backup_sqlite(executor: Executor, spec: ProjectSpec, db: DatabaseSpec, outfile: Path, work_dir: Path) -> None:
    source = Path(db.sqlite_path)
    if not source.is_absolute():
        source = work_dir / source
    if not executor.path_exists(source):
        console.print(f"[yellow]SQLite database not found at {source}; skipping backup.[/yellow]")
        return
    executor.run(["cp", "-p", str(source), str(outfile)], as_user=spec.user)


def backup_database(
    executor: Executor,
    spec: ProjectSpec,
    *,
    backup_dir: Path,
    work_dir: Path,
    timestamp: str,
) -> None:
    """Back up the configured database before migrations run."""
    db = spec.database
    if not db.enabled:
        return

    engine = db.engine.lower()
    extension = _EXTENSIONS.get(engine, "dump")
    outfile = backup_dir / f"{spec.project}-{timestamp}.{extension}"

    if getattr(executor, "dry_run", False):
        console.print(f"[yellow][dry-run] Would back up {engine} database to {outfile}[/yellow]")
        return

    console.print(f"[cyan]Backing up {engine} database before migrations -> {outfile}[/cyan]")
    executor.run(["mkdir", "-p", str(backup_dir)], sudo=True)
    executor.run(["chown", f"{spec.user}:{spec.group}", str(backup_dir)], sudo=True)

    if engine == "postgres":
        _backup_postgres(executor, spec, db, outfile, backup_dir)
    elif engine == "mysql":
        _backup_mysql(executor, spec, db, outfile, backup_dir)
    elif engine == "sqlite":
        _backup_sqlite(executor, spec, db, outfile, work_dir)
    else:  # pragma: no cover - guarded by config validation
        console.print(f"[yellow]Unknown database engine '{engine}'; skipping backup.[/yellow]")
        return

    _prune(executor, spec, backup_dir, extension, db.keep)
    console.print("[green]Database backup complete.[/green]")
