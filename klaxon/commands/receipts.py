"""`klaxon receipts` — show recent rescues by reading Guardian events.

Reads `FindingAttested(bytes32 findingHash, bytes32 teeAttestationHash)` and
`Paused(bytes32 findingHash)` from the deployed Guardian on the chosen
chain. Prints them as a single rescue history table.
"""

from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table
from web3 import Web3

from klaxon._paths import DEPLOYMENTS_DIR, env_value


console = Console()

CHAIN_TO_ID = {"base-sepolia": 84532, "0g-galileo": 16602}
EXPLORERS = {
    84532: "https://sepolia.basescan.org/tx/",
    16602: "https://chainscan-galileo.0g.ai/tx/",
}

GUARDIAN_EVENTS_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "type": "bytes32", "name": "findingHash"},
            {"indexed": False, "type": "bytes32", "name": "teeAttestationHash"},
        ],
        "name": "FindingAttested",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [{"indexed": True, "type": "bytes32", "name": "findingHash"}],
        "name": "Paused",
        "type": "event",
    },
]


def _rpc_for(chain: str) -> str:
    if chain == "base-sepolia":
        return env_value("BASE_SEPOLIA_RPC_URL") or "https://sepolia.base.org"
    if chain == "0g-galileo":
        return env_value("OG_CHAIN_RPC_URL") or "https://evmrpc-testnet.0g.ai"
    raise ValueError(f"unknown chain: {chain}")


def run(*, chain: str, blocks: int) -> None:
    chain_id = CHAIN_TO_ID.get(chain)
    if chain_id is None:
        console.print(f"[red]unknown chain {chain}; use base-sepolia or 0g-galileo[/red]")
        raise SystemExit(2)
    deploy_path = DEPLOYMENTS_DIR / f"{chain_id}.json"
    if not deploy_path.exists():
        console.print(f"[red]no deployment for {chain} at {deploy_path}[/red]")
        raise SystemExit(2)
    deploy = json.loads(deploy_path.read_text())
    guardian_addr = Web3.to_checksum_address(deploy["guardian"])

    w3 = Web3(Web3.HTTPProvider(_rpc_for(chain)))
    if not w3.is_connected():
        console.print(f"[red]rpc unreachable: {_rpc_for(chain)}[/red]")
        raise SystemExit(2)

    head = w3.eth.block_number
    from_block = max(head - blocks, 0)

    guardian = w3.eth.contract(address=guardian_addr, abi=GUARDIAN_EVENTS_ABI)

    chunk = 9000  # Base Sepolia public RPC caps getLogs at ~10k blocks

    def _safe_logs(event):
        results = []
        cursor = from_block
        while cursor <= head:
            stop = min(cursor + chunk - 1, head)
            try:
                results.extend(event.get_logs(from_block=cursor, to_block=stop))
            except Exception as e:
                console.print(f"[yellow]warning: {event.event_name} chunk {cursor}-{stop} unavailable ({e})[/yellow]")
            cursor = stop + 1
        return results

    attested = _safe_logs(guardian.events.FindingAttested)
    paused = _safe_logs(guardian.events.Paused)

    by_hash: dict[str, dict] = {}
    for ev in attested:
        h = ev["args"]["findingHash"].hex()
        by_hash.setdefault(h, {})["attested_block"] = ev["blockNumber"]
        by_hash[h]["tx"] = ev["transactionHash"].hex()
        by_hash[h]["tee_hash"] = ev["args"]["teeAttestationHash"].hex()
    for ev in paused:
        h = ev["args"]["findingHash"].hex()
        by_hash.setdefault(h, {})["paused_block"] = ev["blockNumber"]

    console.rule(f"[bold]klaxon receipts · {chain}")
    console.print(f"[dim]Guardian {guardian_addr}  ·  scanned blocks {from_block}-{head}[/dim]\n")

    if not by_hash:
        console.print("[dim]no rescues in scan window[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("block", justify="right")
    table.add_column("findingHash", overflow="ellipsis", max_width=20)
    table.add_column("tee", overflow="ellipsis", max_width=18)
    table.add_column("tx")

    rows = sorted(by_hash.items(), key=lambda kv: kv[1].get("attested_block", 0), reverse=True)
    for h, data in rows:
        block = str(data.get("paused_block") or data.get("attested_block", ""))
        tx = data.get("tx", "")
        explorer = EXPLORERS.get(chain_id, "")
        link = f"[link={explorer}{tx}]{tx[:18]}…[/link]" if tx and explorer else tx[:18]
        table.add_row(block, f"0x{h[:16]}…", f"0x{data.get('tee_hash','')[:14]}…", link)

    console.print(table)
    console.print(f"\n[green]{len(by_hash)} rescue(s) recorded[/green]")
