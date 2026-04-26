"""`klaxon agents up / down / status` — orchestrate the 3-agent swarm.

PIDs and logs land in `<repo>/.klaxon/run/`. Each AXL daemon and each
Klaxon agent process gets its own .pid and .log. Stop semantics are
graceful first (SIGTERM), then forceful (SIGKILL) after a 3-second
deadline.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from klaxon._paths import (
    AGENTS_DIR,
    AXL_DIR,
    REPO_ROOT,
    RUNTIME_DIR,
    ensure_runtime_dir,
    env_value,
)


console = Console()

AGENT_IDS = ("a", "b", "c")
AXL_PORTS = {"a": 9002, "b": 9012, "c": 9022}


@dataclass(frozen=True)
class ManagedProcess:
    name: str
    cmd: list[str]
    cwd: Path
    log_path: Path
    pid_path: Path


def _venv_python() -> str:
    candidate = REPO_ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def _axl_proc(agent_id: str) -> ManagedProcess:
    rt = ensure_runtime_dir()
    return ManagedProcess(
        name=f"axl-{agent_id}",
        cmd=[str(AXL_DIR / "bin" / "node"), "-config", f"node-{agent_id}-config.json"],
        cwd=AXL_DIR,
        log_path=rt / f"axl-{agent_id}.log",
        pid_path=rt / f"axl-{agent_id}.pid",
    )


def _agent_proc(agent_id: str, *, enable_tee: bool, enable_keeperhub: bool) -> ManagedProcess:
    rt = ensure_runtime_dir()
    rpc = env_value("BASE_SEPOLIA_RPC_URL") or "https://sepolia.base.org"
    cmd = [_venv_python(), str(AGENTS_DIR / "run_agent.py"), "--agent", agent_id, "--rpc", rpc]
    if not enable_tee:
        cmd.append("--no-tee")
    if not enable_keeperhub:
        cmd.append("--no-keeperhub")
    cmd += ["--expected-tee-signer", "0x83df4b8eba7c0b3b740019b8c9a77fff77d508cf"]
    return ManagedProcess(
        name=f"agent-{agent_id}",
        cmd=cmd,
        cwd=REPO_ROOT,
        log_path=rt / f"agent-{agent_id}.log",
        pid_path=rt / f"agent-{agent_id}.pid",
    )


def _spawn(p: ManagedProcess) -> int:
    if _is_running(p):
        existing = int(p.pid_path.read_text().strip())
        console.print(f"[dim]{p.name} already running pid={existing}[/dim]")
        return existing
    log = open(p.log_path, "ab")
    proc = subprocess.Popen(
        p.cmd,
        cwd=str(p.cwd),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    p.pid_path.write_text(str(proc.pid))
    return proc.pid


def _is_running(p: ManagedProcess) -> bool:
    if not p.pid_path.exists():
        return False
    try:
        pid = int(p.pid_path.read_text().strip())
    except Exception:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _stop(p: ManagedProcess) -> str:
    if not p.pid_path.exists():
        return "stopped"
    try:
        pid = int(p.pid_path.read_text().strip())
    except Exception:
        p.pid_path.unlink(missing_ok=True)
        return "stale"
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        p.pid_path.unlink(missing_ok=True)
        return "already-gone"
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            p.pid_path.unlink(missing_ok=True)
            return "stopped"
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    p.pid_path.unlink(missing_ok=True)
    return "killed"


def list_running() -> list[dict]:
    out: list[dict] = []
    if not RUNTIME_DIR.exists():
        return out
    for p in RUNTIME_DIR.glob("*.pid"):
        try:
            pid = int(p.read_text().strip())
            os.kill(pid, 0)
            out.append({"name": p.stem, "pid": pid, "log": str(RUNTIME_DIR / f"{p.stem}.log")})
        except OSError:
            p.unlink(missing_ok=True)
    return out


def up(*, enable_tee: bool, enable_keeperhub: bool) -> None:
    console.rule("[bold]klaxon agents up")
    if not (AXL_DIR / "bin" / "node").exists():
        console.print("[red]✗ AXL binary missing — run `klaxon doctor` first[/red]")
        raise SystemExit(2)

    table = Table(show_header=True, header_style="bold")
    table.add_column("process", min_width=14)
    table.add_column("pid", justify="right")
    table.add_column("status")
    table.add_column("log", style="dim", overflow="fold")

    for aid in AGENT_IDS:
        p = _axl_proc(aid)
        pid = _spawn(p)
        table.add_row(p.name, str(pid), "started", str(p.log_path.relative_to(REPO_ROOT)))
    time.sleep(4)  # let AXL bind ports before agents try to call /topology

    for aid in AGENT_IDS:
        p = _agent_proc(aid, enable_tee=enable_tee, enable_keeperhub=enable_keeperhub)
        pid = _spawn(p)
        table.add_row(p.name, str(pid), "started", str(p.log_path.relative_to(REPO_ROOT)))

    console.print(table)
    console.print("[green]✓[/green] swarm up. tail with [bold]klaxon findings[/bold]; stop with [bold]klaxon agents down[/bold].")


def down() -> None:
    console.rule("[bold]klaxon agents down")
    table = Table(show_header=True, header_style="bold")
    table.add_column("process")
    table.add_column("result")

    for aid in reversed(AGENT_IDS):
        result = _stop(_agent_proc(aid, enable_tee=True, enable_keeperhub=True))
        table.add_row(f"agent-{aid}", result)
    for aid in reversed(AGENT_IDS):
        result = _stop(_axl_proc(aid))
        table.add_row(f"axl-{aid}", result)

    console.print(table)


def status() -> None:
    console.rule("[bold]klaxon agents status")
    running = list_running()
    table = Table(show_header=True, header_style="bold")
    table.add_column("process", min_width=14)
    table.add_column("pid", justify="right")
    table.add_column("axl port", justify="right")
    table.add_column("log size", justify="right")
    table.add_column("last log line", overflow="fold", style="dim")

    expected = [_axl_proc(a) for a in AGENT_IDS] + [_agent_proc(a, enable_tee=True, enable_keeperhub=True) for a in AGENT_IDS]
    by_name = {p.name: p for p in expected}
    running_names = {r["name"] for r in running}

    for p in expected:
        is_up = p.name in running_names
        pid = next((r["pid"] for r in running if r["name"] == p.name), None)
        port = ""
        if p.name.startswith("axl-"):
            port = str(AXL_PORTS.get(p.name.split("-")[1], ""))
        elif p.name.startswith("agent-"):
            port = str(AXL_PORTS.get(p.name.split("-")[1], ""))
        if not is_up:
            table.add_row(p.name, "-", port, "-", "[red]not running[/red]")
            continue
        try:
            stat = p.log_path.stat()
            size = f"{stat.st_size:,}b"
            last_line = ""
            with open(p.log_path, "rb") as f:
                f.seek(max(0, stat.st_size - 2000))
                tail = f.read().decode(errors="ignore").splitlines()
                if tail:
                    last_line = tail[-1]
        except FileNotFoundError:
            size = "-"
            last_line = ""
        table.add_row(p.name, str(pid), port, size, last_line[-160:])

    console.print(table)
