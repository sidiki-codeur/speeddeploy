from __future__ import annotations

import bootstrap_tests  # noqa: F401

import unittest
from pathlib import PurePosixPath

from speeddeploy.v2.engine import DeploymentEngine
from speeddeploy.v2.models import ConnectionSpec, DatabaseSpec, DeploymentTarget, HealthcheckSpec, ProjectSpec, ReleasesSpec, SSLSpec

from tests.support import FakeExecutor


class AuditTests(unittest.TestCase):
    def test_audit_reports_ok_warnings_and_no_errors(self) -> None:
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
            target=DeploymentTarget(web_server="apache", ssl_provider="certbot"),
            connection=ConnectionSpec(backend="ssh", host="203.0.113.10", user="root"),
            releases=ReleasesSpec(enabled=False),
            healthcheck=HealthcheckSpec(enabled=True),
            ssl=SSLSpec(enabled=True, email="admin@example.com"),
            database=DatabaseSpec(),
        )
        executor = FakeExecutor(
            capture_responses=[
                "",
                "uid=1000(django) gid=1000(www-data)",
                "www-data:x:33:",
                "Python 3.12.0",
                "pip 25.0 from /opt/lib/python3.12/site-packages/pip (python 3.12)",
                "venv help",
                "root = /srv/demo/staticfiles",
                "",
                "systemd 255",
                "Server version: Apache/2.4.58 (Ubuntu)",
                "Certbot 2.11.0",
                "192.0.2.10 demo.example.com",
                "LISTEN 0 128 0.0.0.0:80",
                "abc123\trefs/heads/main",
            ],
            existing_paths=[
                PurePosixPath("/srv/demo"),
                PurePosixPath("/srv/demo/manage.py"),
                PurePosixPath("/srv/demo/requirements.txt"),
            ],
        )
        engine = DeploymentEngine(spec=spec, executor=executor)

        findings = engine.audit()
        severities = [item.severity for item in findings]

        self.assertIn("ok", severities)
        self.assertIn("warn", severities)
        self.assertNotIn("error", severities)
        self.assertTrue(any(item.check == "STATIC_ROOT" for item in findings))
        self.assertTrue(any(item.check == "DEFAULT_AUTO_FIELD" and item.severity == "warn" for item in findings))
        self.assertTrue(any(item.check == "DNS" and item.severity == "ok" for item in findings))
