"""V2 CLI surface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from .engine import DeploymentEngine, build_engine, build_plan
from .executor import ExecutorError
from .models import ConnectionSpec, DeploymentTarget, ProjectSpec, ProjectTemplate, V2ConfigError, load_project_spec, render_project_spec
from ..system import RuntimeInfo, detect_runtime

app = typer.Typer(add_completion=False, help="SpeedDeploy V2 primary deployment CLI.")
config_app = typer.Typer(add_completion=False, help="Create and inspect V2 project config files.")
projects_app = typer.Typer(add_completion=False, help="Manage V2 project configuration files.")
console = Console()


@dataclass(slots=True)
class V2State:
    dry_run: bool
    projects_dir: Path
    runtime: RuntimeInfo


@app.callback()
def main(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show commands without executing them."),
    projects_dir: Path = typer.Option(Path("projects"), "--projects-dir", help="Directory containing YAML project files."),
) -> None:
    ctx.obj = V2State(dry_run=dry_run, projects_dir=projects_dir, runtime=detect_runtime())


def _state(ctx: typer.Context) -> V2State:
    state = ctx.obj
    if not isinstance(state, V2State):
        state = V2State(dry_run=False, projects_dir=Path.cwd() / "projects", runtime=detect_runtime())
        ctx.obj = state
    return state


def _load_spec(project: str, state: V2State):
    try:
        return load_project_spec(project, projects_dir=state.projects_dir)
    except V2ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _project_config_path(project: str, state: V2State) -> Path:
    candidate = Path(project)
    if candidate.suffix.lower() in {".yml", ".yaml"} or candidate.exists():
        return candidate
    return state.projects_dir / f"{candidate.name}.yml"


def _print_plan(spec: ProjectSpec) -> None:
    table = Table(title=f"V2 plan for {spec.project}")
    table.add_column("#", justify="right")
    table.add_column("Step")
    for idx, step in enumerate(build_plan(spec), start=1):
        table.add_row(str(idx), step)
    console.print(table)


def _print_runtime(state: V2State) -> None:
    table = Table(title="Runtime")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("System", state.runtime.system)
    table.add_row("Release", state.runtime.release)
    table.add_row("Machine", state.runtime.machine)
    table.add_row("Python", state.runtime.python)
    table.add_row("WSL", "yes" if state.runtime.is_wsl else "no")
    table.add_row("Local deployment", "yes" if state.runtime.supports_local_deployment else "no")
    console.print(table)


def _print_project_summary(spec: ProjectSpec, config_path: Path) -> None:
    table = Table(title=f"Project file: {spec.project}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Project", spec.project)
    table.add_row("Branch", spec.branch)
    table.add_row("Domain", spec.domain)
    table.add_row("Repo", spec.repo)
    table.add_row("Path", str(spec.path))
    table.add_row("Venv", str(spec.venv))
    table.add_row("Static", str(spec.static_dir))
    table.add_row("Media", str(spec.media_dir))
    table.add_row("Backend", spec.connection.backend)
    table.add_row("Web server", spec.target.web_server)
    table.add_row("App server", spec.target.app_server)
    table.add_row("SSL", spec.target.ssl_provider)
    table.add_row("Config file", str(config_path))
    console.print(table)


def _template_from_spec(spec: ProjectSpec, *, project: str | None = None, path: Path | None = None) -> ProjectTemplate:
    return ProjectTemplate(
        project=project or spec.project,
        domain=spec.domain,
        repo=spec.repo,
        path=path or spec.path,
        branch=spec.branch,
        user=spec.user,
        group=spec.group,
        wsgi=spec.wsgi,
        python=spec.python,
        venv=spec.venv,
        static_dir=spec.static_dir,
        media_dir=spec.media_dir,
        workers=spec.workers,
        target=spec.target,
        connection=spec.connection,
        releases=spec.releases,
        healthcheck=spec.healthcheck,
        database=spec.database,
        env=dict(spec.env),
    )


def _run_engine(action):
    try:
        action()
    except ExecutorError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _resolve_local_changes_policy(
    *,
    keep_local_changes: bool,
    discard_local_changes: bool,
) -> str:
    if keep_local_changes and discard_local_changes:
        raise typer.BadParameter("Choose either --keep-local-changes or --discard-local-changes, not both.")
    if discard_local_changes:
        return "discard"
    return "keep"


def _prompt_text(label: str, value: str | None, default: str | None = None) -> str:
    if value is not None:
        return value.strip()
    return typer.prompt(label, default=default).strip() if default is not None else typer.prompt(label).strip()


def _prompt_optional_path(label: str, value: Path | None, default: Path) -> Path:
    if value is not None:
        return value
    return Path(typer.prompt(label, default=str(default))).expanduser()


def _build_template(
    project: str | None,
    domain: str | None,
    repo: str | None,
    branch: str | None,
    path: Path | None,
    user: str | None,
    group: str | None,
    wsgi: str | None,
    python: str | None,
    workers: int | None,
    web_server: str | None,
    app_server: str | None,
    os_name: str | None,
    init_system: str | None,
    ssl_provider: str | None,
    package_manager: str | None,
    backend: str | None,
    host: str | None,
    port: int | None,
    connection_user: str | None,
    identity_file: Path | None,
) -> ProjectTemplate:
    project_name = _prompt_text("Project name", project)
    target_path = _prompt_optional_path("Target path", path, Path(f"/srv/{project_name}"))
    branch_value = _prompt_text("Git branch", branch, "main")
    backend_value = _prompt_text("Backend", backend, "local").lower()
    if backend_value not in {"local", "ssh"}:
        raise typer.BadParameter("Backend must be `local` or `ssh`.")

    host_value: str | None = None
    connection_user_value: str | None = None
    port_value = 22
    identity_value = identity_file
    if backend_value == "ssh":
        host_value = _prompt_text("Remote host", host)
        raw_user = _prompt_text("Remote user", connection_user, "")
        connection_user_value = raw_user or None
        port_value = port or typer.prompt("SSH port", default=22, type=int)
        identity_value = identity_file
        if identity_value is None:
            identity_prompt = typer.prompt("SSH identity file", default="")
            identity_value = Path(identity_prompt).expanduser() if identity_prompt else None

    connection = ConnectionSpec(
        backend=backend_value,
        host=host_value,
        port=port_value,
        user=connection_user_value,
        identity_file=identity_value,
    )
    target = DeploymentTarget(
        os=_prompt_text("Target OS", os_name, "linux"),
        init_system=_prompt_text("Init system", init_system, "systemd"),
        web_server=_prompt_text("Web server", web_server, "apache"),
        app_server=_prompt_text("App server", app_server, "gunicorn"),
        ssl_provider=_prompt_text("SSL provider", ssl_provider, "certbot"),
        package_manager=_prompt_text("Package manager", package_manager, "apt"),
    )
    return ProjectTemplate(
        project=project_name,
        domain=_prompt_text("Domain", domain),
        repo=_prompt_text("Git repository URL", repo),
        branch=branch_value,
        path=target_path,
        user=_prompt_text("System user", user, "django"),
        group=_prompt_text("System group", group, "www-data"),
        wsgi=_prompt_text("WSGI module", wsgi, "config.wsgi:application"),
        python=_prompt_text("Python interpreter", python, "python3"),
        workers=workers or 3,
        target=target,
        connection=connection,
    )


@config_app.command("new")
def config_new(
    ctx: typer.Context,
    project: str | None = typer.Argument(None),
    domain: str | None = typer.Option(None, "--domain", "-d"),
    repo: str | None = typer.Option(None, "--repo", "-r"),
    branch: str | None = typer.Option(None, "--branch", "-b"),
    path: Path | None = typer.Option(None, "--path"),
    user: str | None = typer.Option(None, "--user"),
    group: str | None = typer.Option(None, "--group"),
    wsgi: str | None = typer.Option(None, "--wsgi"),
    python: str | None = typer.Option(None, "--python"),
    workers: int | None = typer.Option(None, "--workers", min=1),
    web_server: str | None = typer.Option(None, "--web-server"),
    app_server: str | None = typer.Option(None, "--app-server"),
    os_name: str | None = typer.Option(None, "--os"),
    init_system: str | None = typer.Option(None, "--init-system"),
    ssl_provider: str | None = typer.Option(None, "--ssl-provider"),
    package_manager: str | None = typer.Option(None, "--package-manager"),
    backend: str | None = typer.Option(None, "--backend"),
    host: str | None = typer.Option(None, "--host"),
    port: int | None = typer.Option(None, "--port"),
    connection_user: str | None = typer.Option(None, "--connection-user"),
    identity_file: Path | None = typer.Option(None, "--identity-file"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    state = _state(ctx)
    template = _build_template(
        project=project,
        domain=domain,
        repo=repo,
        branch=branch,
        path=path,
        user=user,
        group=group,
        wsgi=wsgi,
        python=python,
        workers=workers,
        web_server=web_server,
        app_server=app_server,
        os_name=os_name,
        init_system=init_system,
        ssl_provider=ssl_provider,
        package_manager=package_manager,
        backend=backend,
        host=host,
        port=port,
        connection_user=connection_user,
        identity_file=identity_file,
    )
    destination = state.projects_dir / f"{template.project}.yml"
    if destination.exists() and not force:
        console.print(f"[red]Config file already exists: {destination}[/red]")
        raise typer.Exit(code=1)
    state.projects_dir.mkdir(parents=True, exist_ok=True)
    content = render_project_spec(template)
    if state.dry_run:
        console.print(f"[yellow][dry-run] Would create config file: {destination}[/yellow]")
        console.print(content.rstrip())
        return
    destination.write_text(content, encoding="utf-8")
    console.print(f"[green]Config file created: {destination}[/green]")


@projects_app.command("list")
def projects_list(ctx: typer.Context) -> None:
    state = _state(ctx)
    state.projects_dir.mkdir(parents=True, exist_ok=True)
    project_files = sorted(
        [*state.projects_dir.glob("*.yml"), *state.projects_dir.glob("*.yaml")],
        key=lambda item: item.stem.lower(),
    )
    if not project_files:
        console.print("[yellow]No project configuration files found.[/yellow]")
        return

    table = Table(title="V2 projects")
    table.add_column("Project")
    table.add_column("Branch")
    table.add_column("Backend")
    table.add_column("Web")
    table.add_column("Path")
    table.add_column("Config")
    for config_path in project_files:
        try:
            spec = load_project_spec(config_path, projects_dir=state.projects_dir)
        except V2ConfigError as exc:
            table.add_row(config_path.stem, "[red]invalid[/red]", "-", "-", "-", f"[red]{exc}[/red]")
            continue
        table.add_row(spec.project, spec.branch, spec.connection.backend, spec.target.web_server, str(spec.path), str(config_path))
    console.print(table)


@projects_app.command("show")
def projects_show(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    config_path = _project_config_path(project, state)
    spec = _load_spec(project, state)
    _print_project_summary(spec, config_path)
    console.print()
    console.print(Syntax(config_path.read_text(encoding="utf-8"), "yaml", word_wrap=True, line_numbers=False))


@projects_app.command("duplicate")
def projects_duplicate(
    ctx: typer.Context,
    project: str,
    new_name: str,
    path: Path | None = typer.Option(None, "--path", help="Optional target path for the duplicated project."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
    force: bool = typer.Option(False, "--force", help="Overwrite the destination file if it exists."),
) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    destination = state.projects_dir / f"{new_name}.yml"
    if destination.exists() and not force:
        console.print(f"[red]Config file already exists: {destination}[/red]")
        raise typer.Exit(code=1)
    if not yes and not typer.confirm(f"Duplicate {spec.project} to {new_name}?", default=False):
        raise typer.Exit(code=1)

    template = _template_from_spec(spec, project=new_name, path=path or Path(f"/srv/{new_name}"))
    content = render_project_spec(template)
    state.projects_dir.mkdir(parents=True, exist_ok=True)
    if state.dry_run:
        console.print(f"[yellow][dry-run] Would create config file: {destination}[/yellow]")
        console.print(content.rstrip())
        return
    destination.write_text(content, encoding="utf-8")
    console.print(f"[green]Project duplicated: {destination}[/green]")


@projects_app.command("rename")
def projects_rename(
    ctx: typer.Context,
    project: str,
    new_name: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
    force: bool = typer.Option(False, "--force", help="Overwrite the destination file if it exists."),
) -> None:
    state = _state(ctx)
    source = _project_config_path(project, state)
    spec = _load_spec(project, state)
    destination = state.projects_dir / f"{new_name}.yml"
    if destination.exists() and not force:
        console.print(f"[red]Config file already exists: {destination}[/red]")
        raise typer.Exit(code=1)
    if not yes and not typer.confirm(f"Rename {spec.project} to {new_name}?", default=False):
        raise typer.Exit(code=1)

    template = _template_from_spec(spec, project=new_name)
    content = render_project_spec(template)
    if state.dry_run:
        console.print(f"[yellow][dry-run] Would rename {source} to {destination}[/yellow]")
        console.print(content.rstrip())
        return

    state.projects_dir.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    if source.resolve() != destination.resolve() and source.exists():
        source.unlink()
    console.print(f"[green]Project renamed: {source.name} -> {destination.name}[/green]")


@projects_app.command("remove")
def projects_remove(
    ctx: typer.Context,
    project: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    state = _state(ctx)
    config_path = _project_config_path(project, state)
    spec = _load_spec(project, state)
    if not yes and not typer.confirm(f"Delete project config {spec.project}?", default=False):
        raise typer.Exit(code=1)
    if state.dry_run:
        console.print(f"[yellow][dry-run] Would delete config file: {config_path}[/yellow]")
        return
    if not config_path.exists():
        console.print(f"[red]Config file not found: {config_path}[/red]")
        raise typer.Exit(code=1)
    config_path.unlink()
    console.print(f"[green]Project removed: {config_path}[/green]")


@app.command("helpers")
def helpers() -> None:
    table = Table(title="SpeedDeploy V2 helpers")
    table.add_column("Command")
    table.add_column("Use")
    table.add_row("speeddeploy v2 config new", "Generate a backend-aware project YAML file interactively.")
    table.add_row("speeddeploy v2 projects list", "List every known V2 project configuration.")
    table.add_row("speeddeploy v2 projects show <project>", "Display one V2 project configuration.")
    table.add_row("speeddeploy v2 projects duplicate <project> <new>", "Copy a project configuration under a new name.")
    table.add_row("speeddeploy v2 projects rename <project> <new>", "Rename a project configuration file and project id.")
    table.add_row("speeddeploy v2 projects remove <project>", "Delete a project configuration file.")
    table.add_row("speeddeploy v2 doctor <project>", "Inspect runtime, config, executor, and plan.")
    table.add_row("speeddeploy v2 doctor <project> --fix", "Repair Git ownership and safe.directory issues.")
    table.add_row("speeddeploy v2 plan <project>", "Preview the V2 deployment plan.")
    table.add_row("speeddeploy v2 deploy <project>", "Run a full deployment with the selected backend.")
    table.add_row("speeddeploy v2 deploy <project> --keep-local-changes", "Keep local Git changes if the repo already exists.")
    table.add_row("speeddeploy v2 deploy <project> --discard-local-changes", "Discard local Git changes if the repo already exists.")
    table.add_row("speeddeploy v2 update <project>", "Run the full update cycle: code, config, SSL, and restart.")
    table.add_row("speeddeploy v2 update <project> --keep-local-changes", "Stash and restore local changes after pull.")
    table.add_row("speeddeploy v2 update <project> --discard-local-changes", "Discard local changes before pull.")
    table.add_row("speeddeploy v2 update-code <project>", "Update only the application code and Python environment.")
    table.add_row("speeddeploy v2 update-code <project> --keep-local-changes", "Keep local Git changes while updating code.")
    table.add_row("speeddeploy v2 update-code <project> --discard-local-changes", "Discard local Git changes before updating code.")
    table.add_row("speeddeploy v2 update-conf <project>", "Re-render Gunicorn and web server configuration.")
    table.add_row("speeddeploy v2 update-cert <project>", "Renew or reissue SSL certificates and reload the web server.")
    table.add_row("speeddeploy v2 releases <project>", "List releases and show the active one (releases mode).")
    table.add_row("speeddeploy v2 rollback <project>", "Reactivate the previous release (releases mode).")
    table.add_row("speeddeploy v2 backup <project>", "Back up the configured database on demand.")
    console.print(table)


@app.command("doctor")
def doctor(
    ctx: typer.Context,
    project: str,
    fix: bool = typer.Option(False, "--fix", help="Attempt to repair Git ownership and safe.directory issues."),
) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _print_runtime(state)
    engine.doctor(fix=fix)


@app.command("plan")
def plan(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    _print_runtime(state)
    _print_plan(spec)


@app.command("deploy")
def deploy(
    ctx: typer.Context,
    project: str,
    keep_local_changes: bool = typer.Option(False, "--keep-local-changes", help="Keep local Git changes by stashing and restoring them after update."),
    discard_local_changes: bool = typer.Option(False, "--discard-local-changes", help="Discard local Git changes before updating."),
) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    policy = _resolve_local_changes_policy(
        keep_local_changes=keep_local_changes,
        discard_local_changes=discard_local_changes,
    )
    _run_engine(lambda: engine.deploy(local_changes=policy))


@app.command("update")
def update(
    ctx: typer.Context,
    project: str,
    keep_local_changes: bool = typer.Option(False, "--keep-local-changes", help="Keep local Git changes by stashing and restoring them after update."),
    discard_local_changes: bool = typer.Option(False, "--discard-local-changes", help="Discard local Git changes before updating."),
) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    policy = _resolve_local_changes_policy(
        keep_local_changes=keep_local_changes,
        discard_local_changes=discard_local_changes,
    )
    _run_engine(lambda: engine.update(local_changes=policy))


@app.command("update-code")
def update_code(
    ctx: typer.Context,
    project: str,
    keep_local_changes: bool = typer.Option(False, "--keep-local-changes", help="Keep local Git changes by stashing and restoring them after update."),
    discard_local_changes: bool = typer.Option(False, "--discard-local-changes", help="Discard local Git changes before updating."),
) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    policy = _resolve_local_changes_policy(
        keep_local_changes=keep_local_changes,
        discard_local_changes=discard_local_changes,
    )
    _run_engine(lambda: engine.update_code(local_changes=policy))


@app.command("update-conf")
def update_conf(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _run_engine(engine.update_conf)


@app.command("update-cert")
def update_cert(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _run_engine(engine.update_cert)


@app.command("restart")
def restart(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _run_engine(engine.restart)


@app.command("status")
def status(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _run_engine(engine.status)


@app.command("logs")
def logs(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _run_engine(engine.logs)


@app.command("ssl")
def ssl(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _run_engine(engine.ssl)


@app.command("superuser")
def superuser(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _run_engine(engine.superuser)


@app.command("rollback")
def rollback(ctx: typer.Context, project: str) -> None:
    """Reactivate the previous release (requires releases.enabled)."""
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _run_engine(engine.rollback)


@app.command("releases")
def releases(ctx: typer.Context, project: str) -> None:
    """List the available releases and highlight the active one."""
    state = _state(ctx)
    spec = _load_spec(project, state)
    if not spec.releases.enabled:
        console.print("[yellow]Releases are disabled for this project (set releases.enabled: true).[/yellow]")
        raise typer.Exit(code=0)
    engine = build_engine(spec, dry_run=state.dry_run)
    names, current = engine.release_overview()
    if not names:
        console.print("[yellow]No releases found yet.[/yellow]")
        return
    table = Table(title=f"Releases for {spec.project} (keep {spec.releases.keep})")
    table.add_column("Release")
    table.add_column("Active")
    for name in names:
        table.add_row(name, "[green]<- current[/green]" if name == current else "")
    console.print(table)


@app.command("backup")
def backup(ctx: typer.Context, project: str) -> None:
    """Back up the configured database on demand."""
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _run_engine(engine.backup_now)


app.add_typer(config_app, name="config")
app.add_typer(projects_app, name="projects")
