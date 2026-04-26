"""`klaxon attack <bump|drain|reset>` — drive the demo for video recording.

Wraps the foundry attacker script so the operator/recording session is
one ergonomic command per beat. Every call shells out to forge with the
right gas overrides for whichever chain the active deployment targets
(0G Galileo enforces a 2 gwei priority fee minimum; Base Sepolia is fine
without).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console

from klaxon._paths import CONTRACTS_DIR, DEPLOYMENTS_DIR, env_value


console = Console()


def _active_chain() -> tuple[str, dict]:
    """Pick the most recently-modified deployment file as the active chain."""
    candidates = list(DEPLOYMENTS_DIR.glob("*.json"))
    if not candidates:
        console.print("[red]no deployments found in contracts/deployments/[/red]")
        raise SystemExit(2)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    deploy = json.loads(candidates[0].read_text())
    chain_id = deploy["chainId"]
    if chain_id == 84532:
        return "base_sepolia", deploy
    if chain_id == 16602:
        return "zerog_testnet", deploy
    console.print(f"[red]unknown chainId {chain_id} in {candidates[0].name}[/red]")
    raise SystemExit(2)


def _gas_flags(chain: str) -> list[str]:
    if chain == "zerog_testnet":
        return ["--priority-gas-price", "2gwei", "--with-gas-price", "5gwei"]
    return []


def _run_forge(sig: str, *, env_extra: dict[str, str] | None = None) -> int:
    chain, deploy = _active_chain()
    env = os.environ.copy()
    for k, v in env_value("__nothing__") and {} or {}.items():
        env.setdefault(k, v)
    # Always source .env so PRIVATE_KEY etc. resolve
    for line in (CONTRACTS_DIR / ".env").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip())
    if env_extra:
        env.update(env_extra)

    cmd = [
        "forge", "script", "script/Attacker.s.sol",
        "--sig", sig, "--broadcast",
        "--rpc-url", chain,
    ] + _gas_flags(chain)
    console.print(f"[dim]chain: {chain}  ·  pool: {deploy['pool']}[/dim]")
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")

    proc = subprocess.run(cmd, cwd=str(CONTRACTS_DIR), env=env)
    return proc.returncode


def bump(*, price: str) -> None:
    console.rule("[bold yellow]klaxon attack bump")
    console.print(f"oracle target price: [bold]{price}[/bold] wei")
    rc = _run_forge("bump()", env_extra={"ATTACK_PRICE": price})
    raise SystemExit(rc)


def drain() -> None:
    console.rule("[bold red]klaxon attack drain")
    rc = _run_forge("drain()")
    if rc == 0:
        console.print("[red]drain succeeded — protocol was NOT protected (Klaxon would have caught this)[/red]")
    else:
        console.print("[green]drain reverted — pool is paused, attack neutralized[/green]")
    raise SystemExit(0 if rc != 0 else 1)


def reset() -> None:
    """Redeploy the protected pool so the rescue can be demoed again."""
    console.rule("[bold]klaxon attack reset")
    chain, _ = _active_chain()
    cmd = [
        "forge", "script", "script/Deploy.s.sol",
        "--broadcast",
        "--rpc-url", chain,
    ] + _gas_flags(chain)
    env = os.environ.copy()
    for line in (CONTRACTS_DIR / ".env").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip())
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    rc = subprocess.run(cmd, cwd=str(CONTRACTS_DIR), env=env).returncode
    if rc == 0:
        console.print("[green]✓ fresh pool deployed; deployments/<chainId>.json updated[/green]")
    raise SystemExit(rc)
