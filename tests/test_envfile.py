from __future__ import annotations

import bootstrap_tests  # noqa: F401

import unittest
from pathlib import PurePosixPath

from speeddeploy.v2.envfile import render_env_content, write_env_file
from speeddeploy.v2.models import ConnectionSpec, DatabaseSpec, DeploymentTarget, HealthcheckSpec, ProjectSpec, ReleasesSpec

from tests.support import FakeExecutor


class EnvFileTests(unittest.TestCase):
    def test_render_env_content_quotes_special_values(self) -> None:
        rendered = render_env_content(
            {
                "PLAIN": "value",
                "SPACED": "hello world",
                "QUOTED": 'say "hi"',
                "EMPTY": "",
            }
        )

        self.assertIn("PLAIN=value", rendered)
        self.assertIn('SPACED="hello world"', rendered)
        self.assertIn('QUOTED="say \\"hi\\""', rendered)
        self.assertIn('EMPTY=""', rendered)

    def test_write_env_file_uses_secure_permissions(self) -> None:
        spec = ProjectSpec(
            project="demo",
            domain="demo.example.com",
            repo="https://example.com/demo.git",
            branch="main",
            path=PurePosixPath("/srv/demo"),
            user="django",
            group="www-data",
            wsgi="config.wsgi:application",
            python="python3",
            venv=PurePosixPath("/srv/demo/venv"),
            static_dir=PurePosixPath("/srv/demo/staticfiles"),
            media_dir=PurePosixPath("/srv/demo/media"),
            workers=3,
            target=DeploymentTarget(),
            connection=ConnectionSpec(),
            releases=ReleasesSpec(),
            healthcheck=HealthcheckSpec(),
            database=DatabaseSpec(),
            env={"SECRET_KEY": "abc 123"},
        )
        executor = FakeExecutor()
        env_file = PurePosixPath("/srv/demo/shared/.env")

        created = write_env_file(executor, spec, env_file)

        self.assertTrue(created)
        self.assertEqual(executor.commands[0]["command"], ["mkdir", "-p", "/srv/demo/shared"])
        self.assertEqual(executor.commands[0]["sudo"], True)
        self.assertEqual(executor.writes[0]["path"], "/srv/demo/shared/.env")
        self.assertEqual(executor.writes[0]["mode"], "0640")
        self.assertEqual(executor.commands[1]["command"], ["chown", "django:www-data", "/srv/demo/shared/.env"])
