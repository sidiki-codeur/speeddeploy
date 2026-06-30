from __future__ import annotations

import bootstrap_tests  # noqa: F401

import json
import unittest
from pathlib import PurePosixPath

from speeddeploy.v2.engine import DeploymentEngine
from speeddeploy.v2.models import ConnectionSpec, DatabaseSpec, DeploymentTarget, HealthcheckSpec, ProjectSpec, ReleasesSpec

from tests.support import FakeExecutor


class StateAndRollbackTests(unittest.TestCase):
    def test_deployment_state_round_trip(self) -> None:
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
        )
        state_dir = PurePosixPath("/srv/demo/.speeddeploy")
        executor = FakeExecutor(
            existing_paths=[state_dir / "state.json"],
            capture_responses=[
                json.dumps(
                    {
                        "project": "demo",
                        "branch": "main",
                        "strategy": "in-place",
                        "status": "success",
                        "last_deploy_at": "2026-06-28T16:30:00Z",
                        "current_release": None,
                        "previous_release": None,
                        "last_commit": "abc123",
                    }
                )
            ],
        )
        engine = DeploymentEngine(spec=spec, executor=executor)

        state = engine.deployment_state()

        self.assertIsNotNone(state)
        self.assertEqual(state.project, "demo")
        self.assertEqual(state.status, "success")
        self.assertEqual(state.last_commit, "abc123")

    def test_targeted_rollback_updates_state_file(self) -> None:
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
            database=DatabaseSpec(),
        )
        executor = FakeExecutor(
            existing_paths=[
                PurePosixPath("/srv/demo/current"),
                PurePosixPath("/srv/demo/releases/20260628-150000"),
                PurePosixPath("/srv/demo/releases/20260628-163000"),
            ],
            capture_responses=[
                "/srv/demo/releases/20260628-163000",
                "200",
                "abc123",
            ],
        )
        engine = DeploymentEngine(spec=spec, executor=executor)

        engine.rollback(target_release="20260628-150000")

        self.assertTrue(any("20260628-150000" in " ".join(item["command"]) for item in executor.commands))
        self.assertTrue(any(item["command"][:3] == ["systemctl", "restart", "demo.service"] for item in executor.commands))
        self.assertTrue(any(item["path"] == "/srv/demo/shared/.speeddeploy/state.json" for item in executor.writes))
        state_write = executor.writes[-1]["content"]
        self.assertIn('"current_release": "20260628-150000"', state_write)
        self.assertIn('"status": "success"', state_write)
