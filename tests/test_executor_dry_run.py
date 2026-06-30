from __future__ import annotations

import bootstrap_tests  # noqa: F401

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from speeddeploy import runner
from speeddeploy.v2.executor import LocalExecutor


class ExecutorDryRunTests(unittest.TestCase):
    def tearDown(self) -> None:
        runner.set_dry_run(False)

    def test_runner_dry_run_skips_subprocess(self) -> None:
        runner.set_dry_run(True)
        with patch("speeddeploy.runner.subprocess.run") as mocked_run:
            result = runner.run(["echo", "hello"])

        self.assertEqual(result.returncode, 0)
        mocked_run.assert_not_called()

    def test_local_executor_dry_run_skips_subprocess_and_writes(self) -> None:
        executor = LocalExecutor(dry_run=True)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "demo.txt"
            with patch("speeddeploy.v2.executor.subprocess.run") as mocked_run:
                executor.run(["echo", "hello"])
                captured = executor.capture(["uname", "-a"])
                executor.write_text(target, "content")

            self.assertEqual(captured, "")
            mocked_run.assert_not_called()
            self.assertFalse(target.exists())
