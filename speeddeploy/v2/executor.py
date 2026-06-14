"""Execution backends for V2 deployment."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from rich.console import Console

console = Console()


class ExecutorError(RuntimeError):
    """Raised when command execution fails."""


class Executor(ABC):
    """Abstract command executor."""

    @abstractmethod
    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        sudo: bool = False,
        as_user: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def capture(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        sudo: bool = False,
        as_user: str | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def write_text(self, path: str | Path, content: str, *, sudo: bool = False, mode: str = "0644") -> None:
        raise NotImplementedError

    @abstractmethod
    def kind(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def path_exists(self, path: str | Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_empty_dir(self, path: str | Path) -> bool:
        raise NotImplementedError


def _stringify(command: Sequence[str]) -> list[str]:
    if not command:
        raise ValueError("Command cannot be empty.")
    return [str(part) for part in command]


@dataclass(slots=True)
class LocalExecutor(Executor):
    """Execute commands on the local machine."""

    dry_run: bool = False

    def kind(self) -> str:
        return "local"

    def path_exists(self, path: str | Path) -> bool:
        return Path(path).expanduser().exists()

    def is_empty_dir(self, path: str | Path) -> bool:
        candidate = Path(path).expanduser()
        if not candidate.exists():
            return True
        if not candidate.is_dir():
            return False
        return not any(candidate.iterdir())

    def _prefix(self, args: list[str], sudo: bool, as_user: str | None) -> list[str]:
        if as_user:
            return ["sudo", "-u", as_user, "-H", *args]
        if sudo:
            return ["sudo", *args]
        return args

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        sudo: bool = False,
        as_user: str | None = None,
    ) -> None:
        args = _stringify(command)
        args = self._prefix(args, sudo=sudo, as_user=as_user)
        command_str = shlex.join(args)
        if self.dry_run:
            console.print(f"[yellow][dry-run] $ {command_str}[/yellow]")
            return
        console.print(f"[cyan]$ {command_str}[/cyan]")
        try:
            subprocess.run(args, cwd=str(cwd) if cwd is not None else None, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise ExecutorError(str(exc)) from exc

    def capture(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        sudo: bool = False,
        as_user: str | None = None,
    ) -> str:
        args = _stringify(command)
        args = self._prefix(args, sudo=sudo, as_user=as_user)
        command_str = shlex.join(args)
        if self.dry_run:
            console.print(f"[yellow][dry-run] $ {command_str}[/yellow]")
            return ""
        console.print(f"[cyan]$ {command_str}[/cyan]")
        try:
            completed = subprocess.run(
                args,
                cwd=str(cwd) if cwd is not None else None,
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise ExecutorError(str(exc)) from exc
        return (completed.stdout or completed.stderr).strip()

    def write_text(self, path: str | Path, content: str, *, sudo: bool = False, mode: str = "0644") -> None:
        target = Path(path)
        if self.dry_run:
            console.print(f"[yellow][dry-run] write {target}[/yellow]")
            return
        if not sudo:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            os.chmod(target, int(mode, 8))
            return

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(content)
            temp_name = handle.name
        try:
            self.run(["install", "-m", mode, temp_name, str(target)], sudo=True)
        finally:
            try:
                os.remove(temp_name)
            except FileNotFoundError:
                pass


@dataclass(slots=True)
class SSHExecutor(Executor):
    """Execute commands on a remote Linux host over SSH."""

    host: str
    user: str | None = None
    port: int = 22
    identity_file: Path | None = None
    dry_run: bool = False

    def kind(self) -> str:
        return "ssh"

    def _ssh_prefix(self) -> list[str]:
        args = ["ssh", "-p", str(self.port)]
        if self.identity_file is not None:
            args.extend(["-i", str(self.identity_file)])
        destination = f"{self.user}@{self.host}" if self.user else self.host
        args.append(destination)
        return args

    def _probe(self, script: str) -> bool:
        ssh_args = [*self._ssh_prefix(), "bash", "-lc", script]
        if self.dry_run:
            console.print(f"[yellow][dry-run] $ {shlex.join(ssh_args)}[/yellow]")
            return False
        try:
            completed = subprocess.run(ssh_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except FileNotFoundError as exc:
            raise ExecutorError(str(exc)) from exc
        return completed.returncode == 0

    def _remote_prefix(self, args: list[str], sudo: bool, as_user: str | None) -> list[str]:
        if as_user:
            return ["sudo", "-u", as_user, "-H", *args]
        if sudo:
            return ["sudo", *args]
        return args

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        sudo: bool = False,
        as_user: str | None = None,
    ) -> None:
        args = _stringify(command)
        args = self._remote_prefix(args, sudo=sudo, as_user=as_user)
        remote = shlex.join(args)
        if cwd is not None:
            remote = f"cd {shlex.quote(str(cwd))} && {remote}"
        ssh_args = [*self._ssh_prefix(), "bash", "-lc", remote]
        command_str = shlex.join(ssh_args)
        if self.dry_run:
            console.print(f"[yellow][dry-run] $ {command_str}[/yellow]")
            return
        console.print(f"[cyan]$ {command_str}[/cyan]")
        try:
            subprocess.run(ssh_args, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise ExecutorError(str(exc)) from exc

    def capture(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        sudo: bool = False,
        as_user: str | None = None,
    ) -> str:
        args = _stringify(command)
        args = self._remote_prefix(args, sudo=sudo, as_user=as_user)
        remote = shlex.join(args)
        if cwd is not None:
            remote = f"cd {shlex.quote(str(cwd))} && {remote}"
        ssh_args = [*self._ssh_prefix(), "bash", "-lc", remote]
        command_str = shlex.join(ssh_args)
        if self.dry_run:
            console.print(f"[yellow][dry-run] $ {command_str}[/yellow]")
            return ""
        console.print(f"[cyan]$ {command_str}[/cyan]")
        try:
            completed = subprocess.run(
                ssh_args,
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise ExecutorError(str(exc)) from exc
        return (completed.stdout or completed.stderr).strip()

    def write_text(self, path: str | Path, content: str, *, sudo: bool = False, mode: str = "0644") -> None:
        destination = str(path)
        tee_args = ["tee", destination]
        if sudo:
            tee_args.insert(0, "sudo")
        ssh_args = [*self._ssh_prefix(), *tee_args]
        command_str = shlex.join(ssh_args)
        if self.dry_run:
            console.print(f"[yellow][dry-run] write {destination} via ssh[/yellow]")
            return
        console.print(f"[cyan]$ {command_str}[/cyan]")
        try:
            subprocess.run(ssh_args, input=content.encode("utf-8"), stdout=subprocess.DEVNULL, check=True)
            self.run(["chmod", mode, destination], sudo=sudo)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise ExecutorError(str(exc)) from exc

    def path_exists(self, path: str | Path) -> bool:
        quoted = shlex.quote(str(path))
        return self._probe(f"test -e {quoted}")

    def is_empty_dir(self, path: str | Path) -> bool:
        quoted = shlex.quote(str(path))
        return self._probe(f"test -d {quoted} && [ -z \"$(find {quoted} -mindepth 1 -maxdepth 1 -print -quit)\" ]")
