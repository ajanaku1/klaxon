"""Live test of the KeeperHub MCP client.

Builds a real 3-of-N quorum payload (sigs + finding hash) over a fresh
random hash and submits it through the workflow. We expect the workflow
to either:
  (a) succeed (Guardian.pause is called by KeeperHub's relayer wallet),
  (b) revert with QuorumNotMet (if our sigs are wrong),
  (c) revert with AlreadyProcessed (if the hash collides with a prior run).

Run:  .venv/bin/python agents/test_keeperhub_live.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

from keeperhub import KeeperHubClient

REPO_ROOT = Path(__file__).resolve().parent.parent
KEYS_PATH = REPO_ROOT / "axl" / "agent-eth-keys.json"


def main() -> int:
    keys = json.loads(KEYS_PATH.read_text())["agents"]
    finding_hash = Web3.keccak(text=f"klaxon-keeperhub-test-{int(time.time())}").hex()
    if not finding_hash.startswith("0x"):
        finding_hash = "0x" + finding_hash
    print(f"findingHash : {finding_hash}")

    sigs_hex = []
    for a in keys:
        h = bytes.fromhex(finding_hash[2:])
        signed = Account.sign_message(encode_defunct(h), private_key=a["privateKey"])
        sig_hex = "0x" + signed.signature.hex() if not signed.signature.hex().startswith("0x") else signed.signature.hex()
        sigs_hex.append(sig_hex)
        print(f"  agent {a['id']} sig: {sig_hex[:24]}...")

    tee_hash = "0x" + "00" * 32

    client = KeeperHubClient()
    print(f"\nworkflow_id : {client.workflow_id}")
    execution_id = client.execute(sigs_hex, finding_hash, tee_hash)
    print(f"executionId : {execution_id}")

    print("\npolling...")
    result = client.wait_for_execution(execution_id, timeout_s=90)
    print(f"final       : status={result.status}")
    if result.error:
        print(f"  error     : {result.error}")
    if result.last_node:
        print(f"  lastNode  : {result.last_node}")

    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
