"""Integration check: Python-signed Finding → live Guardian.verifyQuorum.

Sign the same findingHash with all three agent ETH keys (loaded from the
gitignored axl/agent-eth-keys.json), then call the on-chain
`verifyQuorum(bytes[] sigs, bytes32 findingHash)` against the deployed
Guardian. Return value MUST be true — that's the contract-level proof
that our Python signing path matches Guardian.sol's ecrecover path.

Also verifies the negative case: a 4th key (deployer, not authorized)
included in place of one agent should make verifyQuorum return false.

Run:  .venv/bin/python agents/test_guardian_integration.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

REPO_ROOT = Path(__file__).resolve().parent.parent
KEYS_PATH = REPO_ROOT / "axl" / "agent-eth-keys.json"
DEPLOYMENT_PATH = REPO_ROOT / "contracts" / "deployments" / "16602.json"

RPC_URL = "https://evmrpc-testnet.0g.ai"

VERIFY_QUORUM_ABI = {
    "inputs": [
        {"name": "sigs", "type": "bytes[]"},
        {"name": "findingHash", "type": "bytes32"},
    ],
    "name": "verifyQuorum",
    "outputs": [{"name": "", "type": "bool"}],
    "stateMutability": "view",
    "type": "function",
}


def sign_eth_prefixed(private_key: str, finding_hash: bytes) -> bytes:
    signed = Account.sign_message(encode_defunct(finding_hash), private_key=private_key)
    return signed.signature


def main() -> int:
    keys = json.loads(KEYS_PATH.read_text())["agents"]
    deployment = json.loads(DEPLOYMENT_PATH.read_text())
    guardian_addr = Web3.to_checksum_address(deployment["guardian"])

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print(f"FAIL: cannot reach {RPC_URL}", file=sys.stderr)
        return 2

    guardian = w3.eth.contract(address=guardian_addr, abi=[VERIFY_QUORUM_ABI])

    # Use a unique findingHash per run so we don't collide with anything.
    finding_hash = Web3.keccak(text=f"klaxon-integration-test-{w3.eth.block_number}")
    print(f"findingHash: 0x{finding_hash.hex()}")

    # Positive case: all three authorized agents sign.
    sigs_ok = [sign_eth_prefixed(a["privateKey"], finding_hash) for a in keys]
    ok = guardian.functions.verifyQuorum(sigs_ok, finding_hash).call()
    print(f"verifyQuorum(3 authorized sigs)   -> {ok}")

    # Negative case: agent A's sig replaced with deployer's (not authorized).
    deployer_pk = "0xd985e7d377419cdab9320c66cebf35a7bbfbec042056ec256f6aeda919b3462d"
    sigs_bad = [
        sign_eth_prefixed(deployer_pk, finding_hash),
        sign_eth_prefixed(keys[1]["privateKey"], finding_hash),
        sign_eth_prefixed(keys[2]["privateKey"], finding_hash),
    ]
    bad = guardian.functions.verifyQuorum(sigs_bad, finding_hash).call()
    print(f"verifyQuorum(2 authorized + deployer) -> {bad}")

    # Negative case 2: only 2 authorized sigs (sub-quorum).
    sub = guardian.functions.verifyQuorum(sigs_ok[:2], finding_hash).call()
    print(f"verifyQuorum(2 authorized sigs)   -> {sub}")

    failures = 0
    if not ok:
        print("FAIL: 3 authorized sigs did not pass quorum")
        failures += 1
    if bad:
        print("FAIL: deployer (unauthorized) sig was accepted")
        failures += 1
    if sub:
        print("FAIL: 2 sigs passed quorum (should need 3)")
        failures += 1

    if failures == 0:
        print("\nALL CHECKS PASSED — Python signing path matches Guardian.sol ecrecover.")
    return failures


if __name__ == "__main__":
    sys.exit(main())
