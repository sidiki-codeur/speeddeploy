from __future__ import annotations

import bootstrap_tests  # noqa: F401

import tempfile
import unittest
from pathlib import Path, PurePosixPath

import yaml

from speeddeploy.config import ConfigError, ConfigTemplate, DeploymentTarget, load_config, render_config_template


class ConfigV1Tests(unittest.TestCase):
    def test_render_and_load_round_trip(self) -> None:
        template = ConfigTemplate(
            project="demo",
            domain="demo.example.com",
            repo="https://example.com/demo.git",
            path=PurePosixPath("/srv/demo"),
            user="django",
            group="www-data",
            wsgi="config.wsgi:application",
            python="python3.12",
            workers=4,
            target=DeploymentTarget(web_server="apache"),
        )

        content = render_config_template(template)
        data = yaml.safe_load(content)
        self.assertEqual(data["path"], "/srv/demo")
        self.assertEqual(data["venv"], "/srv/demo/venv")
        self.assertEqual(data["static_dir"], "/srv/demo/staticfiles")
        self.assertEqual(data["media_dir"], "/srv/demo/media")

        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects"
            projects_dir.mkdir()
            (projects_dir / "demo.yml").write_text(content, encoding="utf-8")

            config = load_config("demo", projects_dir=projects_dir)
            self.assertEqual(config.project, "demo")
            self.assertEqual(str(config.path), "/srv/demo")
            self.assertEqual(str(config.venv), "/srv/demo/venv")
            self.assertEqual(str(config.static_dir), "/srv/demo/staticfiles")
            self.assertEqual(str(config.media_dir), "/srv/demo/media")
            self.assertEqual(config.target.web_server, "apache")

    def test_legacy_nested_project_mapping_is_supported(self) -> None:
        legacy_yaml = """
project:
  name: legacy
  domain: legacy.example.com
  repo: https://example.com/legacy.git
  path: /srv/legacy
  user: django
  group: www-data
  wsgi: config.wsgi:application
  python: python3
  venv: /srv/legacy/venv
  static_dir: /srv/legacy/staticfiles
  media_dir: /srv/legacy/media
  workers: 2
"""

        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects"
            projects_dir.mkdir()
            (projects_dir / "legacy.yml").write_text(legacy_yaml, encoding="utf-8")

            config = load_config("legacy", projects_dir=projects_dir)
            self.assertEqual(config.project, "legacy")
            self.assertEqual(str(config.path), "/srv/legacy")
            self.assertEqual(config.workers, 2)

    def test_missing_required_field_raises(self) -> None:
        broken_yaml = """
project: demo
domain: demo.example.com
repo: https://example.com/demo.git
path: /srv/demo
user: django
group: www-data
wsgi: config.wsgi:application
python: python3
venv: /srv/demo/venv
static_dir: /srv/demo/staticfiles
media_dir: /srv/demo/media
"""

        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects"
            projects_dir.mkdir()
            (projects_dir / "demo.yml").write_text(broken_yaml, encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_config("demo", projects_dir=projects_dir)
