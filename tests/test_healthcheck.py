from __future__ import annotations

import bootstrap_tests  # noqa: F401

import unittest
from pathlib import PurePosixPath

from speeddeploy.v2.health import HealthcheckError, run_healthcheck
from speeddeploy.v2.models import ConnectionSpec, DatabaseSpec, DeploymentTarget, HealthcheckSpec, ProjectSpec, ReleasesSpec

from tests.support import FakeExecutor


class HealthcheckTests(unittest.TestCase):
    def test_healthcheck_passes_after_retry(self) -> None:
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
            healthcheck=HealthcheckSpec(enabled=True, retries=2, delay=0),
            database=DatabaseSpec(),
        )
        executor = FakeExecutor(capture_responses=["500", "200"])

        run_healthcheck(executor, spec)

        self.assertEqual(len(executor.captures), 2)

    def test_healthcheck_raises_after_exhausting_retries(self) -> None:
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
            healthcheck=HealthcheckSpec(enabled=True, retries=2, delay=0),
            database=DatabaseSpec(),
        )
        executor = FakeExecutor(capture_responses=["500", "500"])

        with self.assertRaises(HealthcheckError):
            run_healthcheck(executor, spec)
