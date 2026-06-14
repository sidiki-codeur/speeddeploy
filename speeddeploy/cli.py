"""CLI entry point for SpeedDeploy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .apache import render_apache_config
from .config import ConfigError, ConfigTemplate, DeploymentTarget, ProjectConfig, render_config_template, load_config
from .deployer import (
    DeploymentError,
    build_deployment_plan,
    clone_or_update,
    full_deploy,
    init_project,
    update_project,
)
from .django import create_venv, createsuperuser, django_prepare
from .gunicorn import logs_gunicorn, render_gunicorn_service, restart_gunicorn, status_gunicorn
from .runner import CommandError, run, set_dry_run
from .ssl import install_ssl
from .system import RuntimeInfo, detect_runtime
from .v2.cli import app as v2_app

app = typer.Typer(add_completion=False, help="SpeedDeploy deployment CLI.")
config_app = typer.Typer(add_completion=False, help="Create and inspect project config files.")
console = Console()


@dataclass(slots=True)
class AppState:
    """CLI runtime state shared by commands."""

    dry_run: bool
    projects_dir: Path
    runtime: RuntimeInfo


def _make_state(dry_run: bool, projects_dir: Path | None = None) -> AppState:
    return AppState(
        dry_run=dry_run,
        projects_dir=projects_dir or (Path.cwd() / "projects"),
        runtime=detect_runtime(),
    )


@app.callback()
def main(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show commands without executing them."),
    projects_dir: Path = typer.Option(Path("projects"), "--projects-dir", help="Directory containing YAML project files."),
) -> None:
    """Configure global CLI behavior."""
    state = _make_state(dry_run=dry_run, projects_dir=projects_dir)
    set_dry_run(state.dry_run)
    ctx.obj = state


def _get_state(ctx: typer.Context) -> AppState:
    state = ctx.obj
    if not isinstance(state, AppState):
        state = _make_state(dry_run=False)
        ctx.obj = state
    return state


def _get_config(project: str, state: AppState) -> ProjectConfig:
    try:
        return load_config(project, projects_dir=state.projects_dir)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _execute(state: AppState, action: Callable[[], None]) -> None:
    if not state.runtime.supports_local_deployment and not state.dry_run:
        console.print(
            "[red]This version runs local Linux deployment commands only. "
            "Use --dry-run, run it on Linux/WSL, or add a remote backend later.[/red]"
        )
        raise typer.Exit(code=1)

    try:
        action()
    except (CommandError, DeploymentError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _print_runtime(state: AppState) -> None:
    table = Table(title="Runtime")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("System", state.runtime.system)
    table.add_row("Release", state.runtime.release)
    table.add_row("Machine", state.runtime.machine)
    table.add_row("Python", state.runtime.python)
    table.add_row("WSL", "yes" if state.runtime.is_wsl else "no")
    table.add_row("Supported", "yes" if state.runtime.supports_local_deployment else "no")
    console.print(table)


def _print_config(config: ProjectConfig) -> None:
    table = Table(title=f"Configuration for {config.project}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Project", config.project)
    table.add_row("Domain", config.domain)
    table.add_row("Path", str(config.path))
    table.add_row("Virtualenv", str(config.venv))
    table.add_row("Web server", config.target.web_server)
    table.add_row("App server", config.target.app_server)
    table.add_row("Init system", config.target.init_system)
    table.add_row("SSL provider", config.target.ssl_provider)
    table.add_row("Package manager", config.target.package_manager)
    console.print(table)


def _print_plan(config: ProjectConfig) -> None:
    table = Table(title=f"Deployment plan for {config.project}")
    table.add_column("#", justify="right")
    table.add_column("Step")
    for idx, step in enumerate(build_deployment_plan(config), start=1):
        table.add_row(str(idx), step)
    console.print(table)


def _print_helpers(config: ProjectConfig | None = None) -> None:
    table = Table(title="SpeedDeploy helpers")
    table.add_column("Command")
    table.add_column("Use")
    table.add_row("speeddeploy config new", "Generate a new project YAML file interactively.")
    table.add_row("speeddeploy v2 config new", "Generate a backend-aware V2 project YAML file.")
    table.add_row("speeddeploy v2 deploy", "Run the next-generation backend-aware deployment engine.")
    table.add_row("speeddeploy doctor <project>", "Inspect runtime, config, and planned steps.")
    table.add_row("speeddeploy plan <project>", "Preview the deployment plan without running it.")
    table.add_row("speeddeploy --dry-run deploy <project>", "Show the commands that would be executed.")
    table.add_row("speeddeploy status <project>", "Check the Gunicorn service status.")
    table.add_row("speeddeploy logs <project>", "Show recent Gunicorn and Apache logs.")
    table.add_row("speeddeploy restart <project>", "Restart Gunicorn and reload Apache.")
    console.print(table)

    if config is not None:
        console.print()
        _print_config(config)


def _scaffold_config(
    *,
    projects_dir: Path,
    project: str,
    domain: str,
    repo: str,
    path: Path,
    user: str,
    group: str,
    wsgi: str,
    python: str,
    workers: int,
    target: DeploymentTarget,
    force: bool,
) -> Path:
    projects_dir.mkdir(parents=True, exist_ok=True)
    destination = projects_dir / f"{project}.yml"
    if destination.exists() and not force:
        raise ConfigError(f"Config file already exists: {destination}")

    template = ConfigTemplate(
        project=project,
        domain=domain,
        repo=repo,
        path=path,
        user=user,
        group=group,
        wsgi=wsgi,
        python=python,
        workers=workers,
        target=target,
    )
    content = render_config_template(template)
    destination.write_text(content, encoding="utf-8")
    return destination


def _prompt_text(label: str, value: str | None, default: str | None = None) -> str:
    if value is not None:
        return value.strip()
    if default is None:
        return typer.prompt(label).strip()
    return typer.prompt(label, default=default).strip()


def _prompt_int(label: str, value: int | None, default: int) -> int:
    if value is not None:
        return value
    return typer.prompt(label, default=default, type=int)


def _prompt_path(label: str, value: Path | None, default: Path) -> Path:
    if value is not None:
        return value
    raw = typer.prompt(label, default=str(default))
    return Path(raw).expanduser()


def _prompt_target(
    *,
    os_name: str | None = None,
    init_system: str | None = None,
    web_server: str | None = None,
    app_server: str | None = None,
    ssl_provider: str | None = None,
    package_manager: str | None = None,
) -> DeploymentTarget:
    return DeploymentTarget(
        os=_prompt_text("Target OS", os_name, "linux"),
        init_system=_prompt_text("Init system", init_system, "systemd"),
        web_server=_prompt_text("Web server", web_server, "apache"),
        app_server=_prompt_text("App server", app_server, "gunicorn"),
        ssl_provider=_prompt_text("SSL provider", ssl_provider, "certbot"),
        package_manager=_prompt_text("Package manager", package_manager, "apt"),
    )


@app.command("init")
def init_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: init_project(config))


@app.command("clone")
def clone_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: clone_or_update(config))


@app.command("venv")
def venv_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: create_venv(config))


@app.command("django")
def django_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: django_prepare(config))


@app.command("gunicorn")
def gunicorn_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: render_gunicorn_service(config))


@app.command("apache")
def apache_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: render_apache_config(config))


@app.command("deploy")
def deploy_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: full_deploy(config))


@app.command("update")
def update_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: update_project(config))


@app.command("restart")
def restart_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: restart_gunicorn(config))
    _execute(state, lambda: run(["systemctl", "reload", "apache2"], sudo=True))


@app.command("status")
def status_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: status_gunicorn(config))


@app.command("logs")
def logs_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: logs_gunicorn(config))
    _execute(state, lambda: run(["tail", "-n", "100", f"/var/log/apache2/{config.project}_error.log"], sudo=True))


@app.command("ssl")
def ssl_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: install_ssl(config))


@app.command("superuser")
def superuser_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _execute(state, lambda: createsuperuser(config))


@app.command("doctor")
def doctor_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _print_runtime(state)
    _print_config(config)
    _print_plan(config)


@app.command("plan")
def plan_command(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state)
    _print_runtime(state)
    _print_config(config)
    _print_plan(config)


@app.command("helpers")
def helpers_command(
    ctx: typer.Context,
    project: str | None = typer.Argument(None, help="Optional project name or YAML file."),
) -> None:
    state = _get_state(ctx)
    config = _get_config(project, state) if project else None
    _print_helpers(config)


@config_app.command("new")
def config_new_command(
    ctx: typer.Context,
    project: str | None = typer.Argument(None, help="Project name used for the YAML filename."),
    domain: str | None = typer.Option(None, "--domain", "-d", help="Primary domain for the deployment."),
    repo: str | None = typer.Option(None, "--repo", "-r", help="Git repository URL."),
    path: Path | None = typer.Option(None, "--path", help="Target application path."),
    user: str | None = typer.Option(None, "--user", help="System user owning the deployment."),
    group: str | None = typer.Option(None, "--group", help="System group owning the deployment."),
    wsgi: str | None = typer.Option(None, "--wsgi", help="WSGI application path."),
    python: str | None = typer.Option(None, "--python", help="Python interpreter to use."),
    workers: int | None = typer.Option(None, "--workers", min=1, help="Gunicorn worker count."),
    os_name: str | None = typer.Option(None, "--os", help="Target operating system."),
    init_system: str | None = typer.Option(None, "--init-system", help="Target init system."),
    web_server: str | None = typer.Option(None, "--web-server", help="Target web server."),
    app_server: str | None = typer.Option(None, "--app-server", help="Target app server."),
    ssl_provider: str | None = typer.Option(None, "--ssl-provider", help="Target SSL provider."),
    package_manager: str | None = typer.Option(None, "--package-manager", help="Target package manager."),
    force: bool = typer.Option(False, "--force", help="Overwrite the config file if it exists."),
) -> None:
    state = _get_state(ctx)
    project_name = _prompt_text("Project name", project)
    target_path = _prompt_path("Target application path", path, Path(f"/srv/{project_name}"))
    domain_value = _prompt_text("Domain", domain)
    repo_value = _prompt_text("Git repository URL", repo)
    user_value = _prompt_text("System user", user, "django")
    group_value = _prompt_text("System group", group, "www-data")
    wsgi_value = _prompt_text("WSGI module", wsgi, "config.wsgi:application")
    python_value = _prompt_text("Python interpreter", python, "python3")
    workers_value = _prompt_int("Gunicorn workers", workers, 3)
    target = _prompt_target(
        os_name=os_name,
        init_system=init_system,
        web_server=web_server,
        app_server=app_server,
        ssl_provider=ssl_provider,
        package_manager=package_manager,
    )
    template_path = state.projects_dir / f"{project_name}.yml"

    if template_path.exists() and not force:
        console.print(f"[red]Config file already exists: {template_path}[/red]")
        raise typer.Exit(code=1)

    try:
        if state.dry_run:
            template = ConfigTemplate(
                project=project_name,
                domain=domain_value,
                repo=repo_value,
                path=target_path,
                user=user_value,
                group=group_value,
                wsgi=wsgi_value,
                python=python_value,
                workers=workers_value,
                target=target,
            )
            console.print(f"[yellow][dry-run] Would create config file: {template_path}[/yellow]")
            console.print(render_config_template(template).rstrip())
            return

        destination = _scaffold_config(
            projects_dir=state.projects_dir,
            project=project_name,
            domain=domain_value,
            repo=repo_value,
            path=target_path,
            user=user_value,
            group=group_value,
            wsgi=wsgi_value,
            python=python_value,
            workers=workers_value,
            target=target,
            force=force,
        )
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Config file created: {destination}[/green]")


app.add_typer(config_app, name="config")
app.add_typer(v2_app, name="v2")


if __name__ == "__main__":
    app()
