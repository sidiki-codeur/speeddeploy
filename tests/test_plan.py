from __future__ import annotations

import bootstrap_tests  # noqa: F401

import unittest
from pathlib import PurePosixPath

from speeddeploy.config import DeploymentTarget as V1DeploymentTarget, ProjectConfig
from speeddeploy.deployer import build_deployment_plan
from speeddeploy.v2.engine import build_plan
from speeddeploy.v2.models import ConnectionSpec, DatabaseSpec, DeploymentTarget, HealthcheckSpec, ProjectSpec, ReleasesSpec, SystemPackagesSpec, SystemUserSpec


class PlanTests(unittest.TestCase):
    def test_v1_plan_lists_expected_steps(self) -> None:
        config = ProjectConfig(
            project="demo",
            domain="demo.example.com",
            repo="https://example.com/demo.git",
            path=PurePosixPath("/srv/demo"),
            user="django",
            group="www-data",
            wsgi="config.wsgi:application",
            python="python3",
            venv=PurePosixPath("/srv/demo/venv"),
            static_dir=PurePosixPath("/srv/demo/staticfiles"),
            media_dir=PurePosixPath("/srv/demo/media"),
            workers=3,
            target=V1DeploymentTarget(),
        )

        plan = build_deployment_plan(config)
        self.assertEqual(plan[0], "Prepare target directory: /srv/demo")
        self.assertIn("Render Gunicorn service: demo.service", plan)
        self.assertEqual(plan[-1], "Optional SSL provisioning: certbot")

    def test_v2_plan_includes_releases_and_healthcheck(self) -> None:
        spec = ProjectSpec(
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
            target=DeploymentTarget(web_server="nginx", ssl_provider="certbot"),
            connection=ConnectionSpec(backend="ssh", host="203.0.113.10", user="root"),
            releases=ReleasesSpec(enabled=True, keep=5),
            healthcheck=HealthcheckSpec(enabled=True),
            database=DatabaseSpec(engine="postgres", name="demo_db"),
        )

        plan = build_plan(spec)
        self.assertIn("Select backend: ssh", plan[0])
        self.assertIn("Prepare release layout under /srv/demo", plan)
        self.assertIn("Back up postgres database before migrations", plan)
        self.assertIn("Activate release via atomic 'current' symlink swap", plan)
        self.assertIn("Run healthcheck (auto-rollback on failure)", plan)
        self.assertIn("Provision SSL via certbot", plan)

    def test_v2_plan_reflects_system_controls(self) -> None:
        spec = ProjectSpec(
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
            target=DeploymentTarget(web_server="apache", ssl_provider="certbot"),
            connection=ConnectionSpec(backend="local"),
            releases=ReleasesSpec(enabled=False),
            healthcheck=HealthcheckSpec(enabled=True),
            system_packages=SystemPackagesSpec(install=False),
            system_user=SystemUserSpec(create=True),
            database=DatabaseSpec(engine="none"),
        )

        plan = build_plan(spec)
        self.assertIn("Skip system package installation", plan)
        self.assertIn("Ensure system user django exists", plan)
