from __future__ import annotations

import bootstrap_tests  # noqa: F401

import tempfile
import unittest
from pathlib import Path, PurePosixPath

import yaml

from speeddeploy.v2.models import (
    ConnectionSpec,
    DatabaseSpec,
    DeploymentTarget,
    HealthcheckSpec,
    SSLSpec,
    ProjectTemplate,
    ReleasesSpec,
    SystemPackagesSpec,
    SystemUserSpec,
    V2ConfigError,
    load_project_spec,
    render_project_spec,
)


class V2ModelTests(unittest.TestCase):
    def test_render_and_load_round_trip_preserves_paths_and_extras(self) -> None:
        template = ProjectTemplate(
            project="demo",
            domain="demo.example.com",
            repo="https://example.com/demo.git",
            branch="main",
            path=PurePosixPath("/srv/demo"),
            user="django",
            group="www-data",
            wsgi="config.wsgi:application",
            python="python3.12",
            venv=PurePosixPath("/srv/demo/venv"),
            static_dir=PurePosixPath("/srv/demo/staticfiles"),
            media_dir=PurePosixPath("/srv/demo/media"),
            workers=3,
            target=DeploymentTarget(web_server="nginx"),
            connection=ConnectionSpec(
                backend="ssh",
                host="203.0.113.10",
                port=2222,
                user="root",
                identity_file=PurePosixPath("C:/Users/Administrateur/.ssh/id_ed25519"),
            ),
            releases=ReleasesSpec(enabled=True, keep=7),
            healthcheck=HealthcheckSpec(enabled=True, path="/health", host="demo.example.com", port=8080, expect_status=(200, 204)),
            ssl=SSLSpec(enabled=True, email="admin@example.com", redirect=True, staging=True, agree_tos=True),
            system_packages=SystemPackagesSpec(install=False),
            system_user=SystemUserSpec(create=True, shell="/usr/sbin/nologin", home=PurePosixPath("/srv/demo")),
            database=DatabaseSpec(engine="postgres", name="demo_db", user="demo", password="secret"),
            env={"DJANGO_SETTINGS_MODULE": "config.settings.production"},
            extras={"notes": "keep me"},
        )

        content = render_project_spec(template)
        data = yaml.safe_load(content)
        self.assertEqual(data["path"], "/srv/demo")
        self.assertEqual(data["venv"], "/srv/demo/venv")
        self.assertEqual(data["ssl"]["email"], "admin@example.com")
        self.assertFalse(data["system_packages"]["install"])
        self.assertTrue(data["system_user"]["create"])
        self.assertEqual(data["system_user"]["home"], "/srv/demo")
        self.assertEqual(data["notes"], "keep me")

        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects"
            projects_dir.mkdir()
            (projects_dir / "demo.yml").write_text(content, encoding="utf-8")

            spec = load_project_spec("demo", projects_dir=projects_dir)
            self.assertEqual(spec.project, "demo")
            self.assertEqual(str(spec.path), "/srv/demo")
            self.assertEqual(str(spec.venv), "/srv/demo/venv")
            self.assertEqual(str(spec.static_dir), "/srv/demo/staticfiles")
            self.assertEqual(str(spec.media_dir), "/srv/demo/media")
            self.assertEqual(spec.connection.backend, "ssh")
            self.assertEqual(spec.connection.port, 2222)
            self.assertEqual(str(spec.connection.identity_file).replace("\\", "/"), "C:/Users/Administrateur/.ssh/id_ed25519")
            self.assertEqual(spec.releases.keep, 7)
            self.assertEqual(spec.healthcheck.port, 8080)
            self.assertTrue(spec.ssl.enabled)
            self.assertEqual(spec.ssl.email, "admin@example.com")
            self.assertTrue(spec.ssl.staging)
            self.assertFalse(spec.system_packages.install)
            self.assertTrue(spec.system_user.create)
            self.assertEqual(str(spec.system_user.home), "/srv/demo")
            self.assertEqual(spec.database.engine, "postgres")
            self.assertEqual(spec.extras["notes"], "keep me")

    def test_ssh_backend_requires_host(self) -> None:
        broken_yaml = """
project: demo
domain: demo.example.com
repo: https://example.com/demo.git
branch: main
path: /srv/demo
user: django
group: www-data
wsgi: config.wsgi:application
python: python3
venv: /srv/demo/venv
static_dir: /srv/demo/staticfiles
media_dir: /srv/demo/media
workers: 3
connection:
  backend: ssh
"""

        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects"
            projects_dir.mkdir()
            (projects_dir / "demo.yml").write_text(broken_yaml, encoding="utf-8")

            with self.assertRaises(V2ConfigError):
                load_project_spec("demo", projects_dir=projects_dir)
