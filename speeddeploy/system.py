"""Runtime environment detection for SpeedDeploy."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeInfo:
    """Information about the current host runtime."""

    system: str
    release: str
    machine: str
    python: str
    is_windows: bool
    is_linux: bool
    is_macos: bool
    is_wsl: bool

    @property
    def supports_local_deployment(self) -> bool:
        """Return True when the current host can run the local deployment engine."""
        return self.is_linux or self.is_wsl


def detect_runtime() -> RuntimeInfo:
    """Detect the current operating system and Python runtime."""
    system = platform.system() or "Unknown"
    release = platform.release() or "Unknown"
    machine = platform.machine() or "Unknown"
    python = platform.python_version()
    is_windows = system == "Windows"
    is_linux = system == "Linux"
    is_macos = system == "Darwin"
    is_wsl = is_linux and (
        "microsoft" in release.lower()
        or "WSL_INTEROP" in os.environ
        or "microsoft" in platform.version().lower()
    )

    return RuntimeInfo(
        system=system,
        release=release,
        machine=machine,
        python=python,
        is_windows=is_windows,
        is_linux=is_linux,
        is_macos=is_macos,
        is_wsl=is_wsl,
    )
