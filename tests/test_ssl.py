from __future__ import annotations

import bootstrap_tests  # noqa: F401

import unittest
from pathlib import PurePosixPath

from speeddeploy.certbot import build_certbot_command
from speeddeploy.v2.engine import DeploymentEngine
from speeddeploy.v2.models import ConnectionSpec, DatabaseSpec, DeploymentTarget, HealthcheckSpec, ProjectSpec, ReleasesSpec, SSLSpec

from tests.support import FakeExecutor


class SSLTests(unittest.TestCase):
    def test_certbot_command_is_non_interactive(self) -> None:
        command = build_certbot_command(
            web_server="apache",
            domain="demo.example.com",
            email="admin@example.com",
            redirect=True,
            staging=True,
            agree_tos=True,
        )

        self.assertEqual(
            command,
            [
                "certbot",
                "--apache",
                "-d",
                "demo.example.com",
                "--non-interactive",
                "--agree-tos",
                "--email",
                "admin@example.com",
                "--redirect",
                "--staging",
            ],
        )

    def test_engine_ssl_uses_hardened_certbot_command(self) -> None:
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
            target=DeploymentTarget(web_server="nginx", ssl_provider="certbot"),
            connection=ConnectionSpec(),
            releases=ReleasesSpec(),
            healthcheck=HealthcheckSpec(),
            ssl=SSLSpec(enabled=True, redirect=False, staging=False, agree_tos=False),
            database=DatabaseSpec(),
        )
        executor = FakeExecutor()
        engine = DeploymentEngine(spec=spec, executor=executor)

        engine.ssl()

        self.assertEqual(
            executor.commands[0]["command"],
            [
                "certbot",
                "--nginx",
                "-d",
                "demo.example.com",
                "--non-interactive",
                "--register-unsafely-without-email",
                "--no-redirect",
            ],
        )
