"""`klaxon findings` — pretty-print the live finding feed across all agents.

Tails the three agent log files in .klaxon/run/ and rewrites each line with
color and symbols so the rescue beats are visible from across the room.
The agent runtime emits structured INFO lines like:

  14:43:51 INFO  agent[a]     DETECTED oracle_manipulation ratio=10x tx=...
  14:44:05 INFO  agent[a]     TEE attested: signer=0x83df... verified=True
  14:44:07 INFO  agent[a]     QUORUM hash=0x... signers=[...]
  14:44:08 INFO  keeperhub    started execution h3sr... for workflow ...
  14:44:11 INFO  agent[a]     KeeperHub execution h3sr... -> success
"""

from __future__ import annotations

import os
import re
import select
import time
from pathlib import Path

from rich.console import Console
from rich.text import Text

from klaxon._paths import RUNTIME_DIR

console = Console()

AGENT_LOGS = ["agent-a.log", "agent-b.log", "agent-c.log"]


# Recognized beats. Order matters: more specific first.
BEAT_RULES = [
    (re.compile(r"DETECTED (\S+) ratio=(\d+x).*?tx=(\S+) block=(\d+)"),
     "yellow", "DETECT"),
    (re.compile(r"TEE attested: signer=(\S+) verified=True"),
     "magenta", "ATTEST"),
    (re.compile(r"TEE attestation failed"),
     "red", "ATTEST!"),
    (re.compile(r"QUORUM hash=(\S+) signers=\[([^\]]+)\]"),
     "bold cyan", "QUORUM"),
    (re.compile(r"started execution (\S+) for workflow (\S+)"),
     "blue", "KH-FIRE"),
    (re.compile(r"KeeperHub execution (\S+) -> success"),
     "bold green", "PAUSED"),
    (re.compile(r"KeeperHub execution (\S+) -> error.*?AlreadyProcessed"),
     "dim", "race-loss"),
    (re.compile(r"pause receipt status=1 block=(\d+)"),
     "bold green", "PAUSED"),
    (re.compile(r"pause receipt status=0"),
     "dim", "race-loss"),
    (re.compile(r"broadcast: (\{.*?\})"),
     "white", "GOSSIP"),
    (re.compile(r"scan starting at block (\d+)"),
     "dim cyan", "SCAN"),
    (re.compile(r"agent started"),
     "green", "BOOT"),
    (re.compile(r"listening on AXL inbox"),
     "dim", "AXL-UP"),
]


def _agent_id_from_log(path: Path) -> str:
    return path.stem.split("-")[-1]


def _classify(line: str) -> tuple[str, str, str | None]:
    """Return (beat_label, color_style, summary)."""
    for rx, color, label in BEAT_RULES:
        m = rx.search(line)
        if m:
            return label, color, m.group(0)
    return "log", "dim", None


def _format(agent: str, beat: str, color: str, line: str) -> Text:
    ts_match = re.match(r"(\d\d:\d\d:\d\d)", line)
    ts = ts_match.group(1) if ts_match else "        "
    text = Text()
    text.append(f"{ts}  ", style="dim")
    text.append(f"[{agent.upper()}] ", style="bold cyan" if agent in {"a", "b", "c"} else "dim")
    text.append(f"{beat:<8}", style=color)
    body = line.split("INFO", 1)[-1].strip() if "INFO" in line else line
    body = body.lstrip()
    body = re.sub(r"^(agent\[\w\]|keeperhub|og_compute|axl_client)\s+", "", body)
    text.append(body)
    return text


def _backfill(paths: list[Path], lines: int) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for p in paths:
        if not p.exists():
            continue
        try:
            tail = p.read_text(errors="ignore").splitlines()[-lines:]
        except Exception:
            tail = []
        for line in tail:
            out.append((p, line))
    out.sort(key=lambda pl: pl[1][:8] if len(pl[1]) >= 8 else "")
    return out


def run(*, follow: bool, lines: int) -> None:
    rt = RUNTIME_DIR
    if not rt.exists():
        console.print("[yellow]No runtime dir yet — boot the swarm with `klaxon agents up`[/yellow]")
        return
    paths = [rt / name for name in AGENT_LOGS]

    for p, line in _backfill(paths, lines):
        beat, color, _ = _classify(line)
        console.print(_format(_agent_id_from_log(p), beat, color, line))

    if not follow:
        return

    console.print("[dim]— following live; ctrl-C to stop —[/dim]")
    files = []
    for p in paths:
        if not p.exists():
            p.touch()
        f = open(p, "r", errors="ignore")
        f.seek(0, os.SEEK_END)
        files.append((p, f))

    try:
        while True:
            had_data = False
            for p, f in files:
                where = f.tell()
                line = f.readline()
                if not line:
                    f.seek(where)
                    continue
                had_data = True
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                beat, color, _ = _classify(line)
                console.print(_format(_agent_id_from_log(p), beat, color, line))
            if not had_data:
                time.sleep(0.2)
    except KeyboardInterrupt:
        console.print("\n[dim]stopped[/dim]")
    finally:
        for _p, f in files:
            f.close()
