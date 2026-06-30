from __future__ import annotations

import bootstrap_tests  # noqa: F401

import json
import unittest
from pathlib import PurePosixPath

from speeddeploy.v2.engine import DeploymentEngine
from speeddeploy.v2.models import ConnectionSpec, DatabaseSpec, DeploymentTarget, HealthcheckSpec, ProjectSpec, ReleasesSpec, SSLSpec

from tests.support import FakeExecutor


class DiagnoseTests(unittest.TestCase):
    def test_diagnose_reports_state_service_healthcheck_and_logs(self) -> None:
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
            releases=ReleasesSpec(enabled=True, keep=5),
            healthcheck=HealthcheckSpec(enabled=True, retries=1, delay=0),
            ssl=SSLSpec(enabled=True, email="admin@example.com"),
            database=DatabaseSpec(),
        )
        state_dir = PurePosixPath("/srv/demo/shared/.speeddeploy")
        executor = FakeExecutor(
            existing_paths=[
                state_dir / "state.json",
                PurePosixPath("/srv/demo/releases"),
                PurePosixPath("/srv/demo/current"),
                PurePosixPath("/srv/demo/releases/20260628-163000"),
            ],
            capture_responses=[
                json.dumps(
                    {
                        "project": "demo",
                        "branch": "main",
                        "strategy": "releases",
                        "status": "success",
                        "last_deploy_at": "2026-06-28T16:30:00Z",
                        "current_release": "20260628-163000",
                        "previous_release": "20260628-150000",
                        "last_commit": "abc123",
                    }
                ),
                "20260628-150000\n20260628-163000",
                "/srv/demo/releases/20260628-163000",
                "active",
                "200",
                "demo.service started\napplication ready",
            ],
        )
        engine = DeploymentEngine(spec=spec, executor=executor)

        findings = engine.diagnose()

        self.assertTrue(any(item.check == "Deployment state" and item.severity == "ok" for item in findings))
        self.assertTrue(any(item.check == "Service active" and item.severity == "ok" for item in findings))
        self.assertTrue(any(item.check == "Healthcheck" and item.severity == "ok" for item in findings))
        self.assertTrue(any(item.check == "Recent logs" and item.severity == "ok" for item in findings))
        self.assertTrue(any(item.check == "Last commit" and item.detail == "abc123" for item in findings))
