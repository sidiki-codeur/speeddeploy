"""V2 CLI surface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .engine import DeploymentEngine, build_engine, build_plan
from .executor import ExecutorError
from .models import ConnectionSpec, DeploymentTarget, ProjectSpec, ProjectTemplate, V2ConfigError, load_project_spec, render_project_spec
from ..system import RuntimeInfo, detect_runtime

app = typer.Typer(add_completion=False, help="SpeedDeploy V2 deployment CLI.")
config_app = typer.Typer(add_completion=False, help="Create and inspect V2 project config files.")
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


def _run_engine(action):
    try:
        action()
    except ExecutorError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


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


@app.command("helpers")
def helpers() -> None:
    table = Table(title="SpeedDeploy V2 helpers")
    table.add_column("Command")
    table.add_column("Use")
    table.add_row("speeddeploy v2 config new", "Generate a backend-aware project YAML file interactively.")
    table.add_row("speeddeploy v2 doctor <project>", "Inspect runtime, config, executor, and plan.")
    table.add_row("speeddeploy v2 plan <project>", "Preview the V2 deployment plan.")
    table.add_row("speeddeploy v2 deploy <project>", "Run a full deployment with the selected backend.")
    table.add_row("speeddeploy v2 update <project>", "Update code, services, and web server config.")
    console.print(table)


@app.command("doctor")
def doctor(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _print_runtime(state)
    engine.doctor()


@app.command("plan")
def plan(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    _print_runtime(state)
    _print_plan(spec)


@app.command("deploy")
def deploy(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _run_engine(engine.deploy)


@app.command("update")
def update(ctx: typer.Context, project: str) -> None:
    state = _state(ctx)
    spec = _load_spec(project, state)
    engine = build_engine(spec, dry_run=state.dry_run)
    _run_engine(engine.update)


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


app.add_typer(config_app, name="config")
