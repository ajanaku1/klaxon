"""`klaxon doctor` — verify the local environment can run a rescue.

The output is a single Rich table. Each row is one check, color-coded:
  green check : ok
  yellow !   : optional / informational
  red X      : blocking, the demo will fail without this fixed

Failing rows include a one-line "fix me" hint so the user can act on the
output without leaving the terminal.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests
from rich.console import Console
from rich.table import Table
from rich.text import Text
from web3 import Web3

from klaxon._paths import (
    AGENTS_DIR,
    AXL_DIR,
    DEPLOYMENTS_DIR,
    KEEPERHUB_DIR,
    OG_COMPUTE_DIR,
    REPO_ROOT,
    env_value,
)


console = Console()


@dataclass
class Check:
    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str
    fix: str = ""


def _check_env_keys() -> list[Check]:
    out: list[Check] = []
    required = [
        "DEPLOYER_PRIVATE_KEY",
        "AGENT_A_PRIVATE_KEY",
        "AGENT_B_PRIVATE_KEY",
        "AGENT_C_PRIVATE_KEY",
        "OG_CHAIN_RPC_URL",
        "BASE_SEPOLIA_RPC_URL",
        "KEEPERHUB_API_KEY",
        "OG_COMPUTE_PROVIDER_ADDRESS",
    ]
    for key in required:
        val = env_value(key)
        if val and val.strip():
            preview = val if not key.endswith("KEY") else f"{val[:8]}…{val[-4:]}"
            out.append(Check(f".env: {key}", "ok", preview))
        else:
            out.append(Check(f".env: {key}", "fail", "missing", f"Set {key} in /.env"))
    return out


def _check_binaries() -> list[Check]:
    out: list[Check] = []
    if (AXL_DIR / "bin" / "node").exists():
        out.append(Check("axl binary", "ok", str((AXL_DIR / 'bin' / 'node').relative_to(REPO_ROOT))))
    else:
        out.append(Check("axl binary", "fail", "missing", f"build via `cd ../axl-src && make build && cp node {AXL_DIR}/bin/node`"))
    for binary in ("forge", "cast"):
        path = shutil.which(binary)
        out.append(Check(f"foundry: {binary}", "ok" if path else "fail", path or "not on PATH",
                         "" if path else "install via `curl -L https://foundry.paradigm.xyz | bash && foundryup`"))
    if (OG_COMPUTE_DIR / "node_modules" / ".bin" / "tsx").exists():
        out.append(Check("og-compute deps", "ok", "node_modules present"))
    else:
        out.append(Check("og-compute deps", "fail", "node_modules missing", f"cd {OG_COMPUTE_DIR.relative_to(REPO_ROOT)} && npm install"))
    return out


def _check_deployment(chain_id: int, label: str, rpc: str | None) -> list[Check]:
    out: list[Check] = []
    f = DEPLOYMENTS_DIR / f"{chain_id}.json"
    if not f.exists():
        return [Check(f"deployment {label}", "fail", f"missing {f.name}", "run `cd contracts && forge script script/Deploy.s.sol --broadcast --rpc-url <rpc>`")]
    deploy = json.loads(f.read_text())
    out.append(Check(f"deployment {label}", "ok", f"{f.name} present"))
    if rpc:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 5}))
            if w3.is_connected():
                pool = deploy["pool"]
                paused = w3.eth.contract(address=Web3.to_checksum_address(pool),
                                         abi=[{"name": "paused", "type": "function", "inputs": [], "outputs": [{"type": "bool"}], "stateMutability": "view"}]
                                         ).functions.paused().call()
                out.append(Check(f"  pool.paused() {label}", "warn" if paused else "ok",
                                 f"{paused} (cannot re-demo while paused)" if paused else "false (ready for fresh rescue)",
                                 "redeploy with `klaxon attack reset`" if paused else ""))
        except Exception as e:
            out.append(Check(f"  pool reachable {label}", "fail", f"rpc error: {e}", f"check {rpc}"))
    return out


def _check_balances(addresses: dict[str, str], rpc: str, chain_label: str) -> list[Check]:
    out: list[Check] = []
    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 5}))
    except Exception as e:
        return [Check(f"balances {chain_label}", "fail", f"rpc error: {e}")]
    for label, addr in addresses.items():
        try:
            bal = w3.eth.get_balance(Web3.to_checksum_address(addr))
        except Exception as e:
            out.append(Check(f"balance {label} {chain_label}", "fail", f"{e}"))
            continue
        eth = bal / 1e18
        if bal == 0:
            out.append(Check(f"balance {label} {chain_label}", "fail", f"{eth:.6f} (empty)",
                             f"fund {addr} with testnet ETH"))
        elif eth < 0.0001:
            out.append(Check(f"balance {label} {chain_label}", "warn", f"{eth:.6f} (low)",
                             f"top up {addr}"))
        else:
            out.append(Check(f"balance {label} {chain_label}", "ok", f"{eth:.6f}"))
    return out


def _check_keeperhub() -> list[Check]:
    out: list[Check] = []
    api_key = env_value("KEEPERHUB_API_KEY")
    if not api_key:
        return [Check("keeperhub api", "fail", "no api key")]
    workflow_path = KEEPERHUB_DIR / "workflow.json"
    if not workflow_path.exists():
        return [Check("keeperhub workflow", "fail", "workflow.json missing",
                      "run `python keeperhub/create-workflow.py`")]
    wf = json.loads(workflow_path.read_text())
    workflow_id = wf["workflow_id"]
    try:
        r = requests.get(f"https://app.keeperhub.com/api/workflows/{workflow_id}",
                         headers={"Authorization": f"Bearer {api_key}"}, timeout=8)
    except Exception as e:
        return [Check("keeperhub workflow", "fail", f"unreachable: {e}")]
    if not r.ok:
        return [Check("keeperhub workflow", "fail", f"HTTP {r.status_code}")]
    body = r.json()
    out.append(Check("keeperhub workflow", "ok", f"{workflow_id} (enabled={body.get('enabled')})"))
    return out


def _check_compute_provider() -> list[Check]:
    pa = env_value("OG_COMPUTE_PROVIDER_ADDRESS")
    if not pa:
        return [Check("0G Compute provider", "fail", "OG_COMPUTE_PROVIDER_ADDRESS not set")]
    return [Check("0G Compute provider", "ok", f"{pa[:8]}…{pa[-4:]} (acknowledge tx already submitted Day 5)")]


def _check_agents_running() -> list[Check]:
    from klaxon.commands.agents import list_running
    running = list_running()
    if not running:
        return [Check("swarm running", "warn", "no agents booted",
                      "run `klaxon agents up` to start the swarm")]
    return [Check("swarm running", "ok",
                  f"{len(running)} processes ({', '.join(r['name'] for r in running)})")]


def run() -> None:
    base_rpc = env_value("BASE_SEPOLIA_RPC_URL") or "https://sepolia.base.org"
    og_rpc = env_value("OG_CHAIN_RPC_URL") or "https://evmrpc-testnet.0g.ai"
    deployer = env_value("DEPLOYER_ADDRESS") or "0x6d4B6bba630Ddd33dFD54769fd9158b0c31283df"
    agent_a = env_value("AGENT_A_ADDRESS") or "0x4A0AF400AdF0CF99cF7Bab4F05E84a227bb15fFA"
    agent_b = env_value("AGENT_B_ADDRESS") or "0xD87AD210297A2d7ECAc28AaFc224F9d1444221fa"
    agent_c = env_value("AGENT_C_ADDRESS") or "0x92977216087Baec7Ff1Deb14e07258B06DB08804"
    relayer = "0xc90e350d8D8048d855C96CD8CD536855D1D4fa84"

    base_addresses = {"deployer": deployer, "agent A": agent_a, "agent B": agent_b,
                      "agent C": agent_c, "kh-relayer": relayer}
    og_addresses = {"deployer": deployer, "agent A": agent_a, "agent B": agent_b, "agent C": agent_c}

    checks: list[Check] = []
    checks += _check_env_keys()
    checks += _check_binaries()
    checks += _check_deployment(84532, "(Base Sepolia)", base_rpc)
    checks += _check_deployment(16602, "(0G Galileo)", og_rpc)
    checks += _check_balances(base_addresses, base_rpc, "(Base)")
    checks += _check_balances(og_addresses, og_rpc, "(0G)")
    checks += _check_keeperhub()
    checks += _check_compute_provider()
    checks += _check_agents_running()

    table = Table(title="klaxon doctor", show_lines=False, header_style="bold")
    table.add_column("", width=3)
    table.add_column("check", min_width=28)
    table.add_column("detail", overflow="fold")
    table.add_column("fix", overflow="fold", style="dim")

    counts = {"ok": 0, "warn": 0, "fail": 0}
    for c in checks:
        counts[c.status] += 1
        if c.status == "ok":
            mark = Text("✓", style="bold green")
        elif c.status == "warn":
            mark = Text("!", style="bold yellow")
        else:
            mark = Text("✗", style="bold red")
        table.add_row(mark, c.name, c.detail, c.fix)

    console.print(table)
    summary = Text()
    summary.append(f"{counts['ok']} ok ", style="green")
    summary.append(f"· {counts['warn']} warn ", style="yellow")
    summary.append(f"· {counts['fail']} fail", style="red" if counts["fail"] else "dim")
    console.print(summary)
