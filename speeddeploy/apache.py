"""Apache configuration rendering."""

from __future__ import annotations

import tempfile
from pathlib import Path

from jinja2 import Environment, PackageLoader
from rich.console import Console

from .config import ProjectConfig
from .runner import run

console = Console()
_TEMPLATE_ENV = Environment(
    loader=PackageLoader("speeddeploy", "templates"),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render_template(template_name: str, config: ProjectConfig) -> str:
    template = _TEMPLATE_ENV.get_template(template_name)
    return template.render(
        project=config.project,
        domain=config.domain,
        repo=config.repo,
        path=str(config.path),
        user=config.user,
        group=config.group,
        wsgi=config.wsgi,
        python=config.python,
        venv=str(config.venv),
        static_dir=str(config.static_dir),
        media_dir=str(config.media_dir),
        workers=config.workers,
    )


def render_apache_config(config: ProjectConfig) -> Path:
    """Render and install the Apache vhost, then reload Apache."""
    content = _render_template("apache.conf.j2", config)
    temp_path = Path(tempfile.gettempdir()) / f"{config.project}.apache.conf"
    target_path = Path("/etc/apache2/sites-available") / f"{config.project}.conf"
    temp_path.write_text(content, encoding="utf-8")

    try:
        run(["install", "-m", "644", str(temp_path), str(target_path)], sudo=True)
        run(["a2enmod", "proxy", "proxy_http", "headers"], sudo=True)
        run(["a2ensite", f"{config.project}.conf"], sudo=True)
        run(["apache2ctl", "configtest"], sudo=True)
        run(["systemctl", "reload", "apache2"], sudo=True)
    finally:
        temp_path.unlink(missing_ok=True)

    console.print("[green]Configuration Apache activée.[/green]")
    return target_path
