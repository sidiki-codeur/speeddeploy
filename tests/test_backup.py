from __future__ import annotations

import bootstrap_tests  # noqa: F401

import unittest
from pathlib import PurePosixPath

from speeddeploy.v2.backup import backup_database
from speeddeploy.v2.models import ConnectionSpec, DatabaseSpec, DeploymentTarget, HealthcheckSpec, ProjectSpec, ReleasesSpec

from tests.support import FakeExecutor


class BackupTests(unittest.TestCase):
    def test_postgres_backup_uses_temp_passfile_and_prunes_old_backups(self) -> None:
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
            database=DatabaseSpec(engine="postgres", name="demo_db", user="demo", password="secret", host="db.example.com", port=5432, keep=2),
        )
        executor = FakeExecutor()
        backup_dir = PurePosixPath("/srv/demo/backups")
        work_dir = PurePosixPath("/srv/demo")

        backup_database(executor, spec, backup_dir=backup_dir, work_dir=work_dir, timestamp="20260628-120000")

        self.assertEqual(executor.writes[0]["path"], "/srv/demo/backups/.pgpass-demo")
        self.assertIn("PGPASSFILE=", executor.commands[2]["command"][2])
        self.assertIn("pg_dump", executor.commands[2]["command"][2])
        self.assertEqual(executor.commands[3]["command"], ["rm", "-f", "/srv/demo/backups/.pgpass-demo"])
        self.assertIn("ls -1t", executor.commands[4]["command"][2])

    def test_sqlite_backup_skips_when_database_is_missing(self) -> None:
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
            database=DatabaseSpec(engine="sqlite", sqlite_path="db.sqlite3"),
        )
        executor = FakeExecutor()

        backup_database(executor, spec, backup_dir=PurePosixPath("/srv/demo/backups"), work_dir=PurePosixPath("/srv/demo"), timestamp="20260628-120000")

        self.assertEqual(executor.commands[0]["command"], ["mkdir", "-p", "/srv/demo/backups"])
        self.assertEqual(executor.commands[1]["command"], ["chown", "django:www-data", "/srv/demo/backups"])
        self.assertIn("ls -1t", executor.commands[2]["command"][2])
        self.assertEqual(executor.writes, [])
