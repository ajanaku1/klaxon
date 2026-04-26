"""Build the three Klaxon agent manifests and compute their root hashes.

The on-chain AgentINFT.tokenURI returns `og://<hex root>` where the root is
the keccak256 of the canonicalized manifest JSON. In production the manifest
would be uploaded to 0G Storage and the root would be the storage Merkle
root; for the hackathon demo we hash locally because the @0g*/0g-ts-sdk
upload path has an axios/Node-25 incompat bug in open-jsonrpc-provider
(see PLAN.md Day-7 notes). Manifest JSON files are committed to the repo so
anyone can re-derive the root and verify the iNFT mint matches.

Output:
  manifests/agent-{a,b,c}.json   canonical manifest, one per agent
  manifests/manifests.json       index mapping agent id to root hash and
                                 ETH address; consumed by the iNFT mint
                                 script.

Run:  .venv/bin/python agents/build_manifests.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import keccak

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFESTS_DIR = REPO_ROOT / "manifests"
KEYS_PATH = REPO_ROOT / "axl" / "agent-eth-keys.json"
ROSTER_PATH = REPO_ROOT / "axl" / "agent-roster.json"

# Code hash covers the analyzer + finding modules so any change to detection
# or signing logic forces a manifest re-mint.
CODE_FILES = [
    REPO_ROOT / "agents" / "finding.py",
    REPO_ROOT / "agents" / "analyzer_oracle.py",
    REPO_ROOT / "agents" / "aggregator.py",
]


def analyzer_code_hash() -> str:
    h = hashlib.sha256()
    for p in CODE_FILES:
        h.update(p.read_bytes())
    return "0x" + h.hexdigest()


def canonical_json(obj: dict) -> str:
    """Stable serialization: sort keys at every nesting level, no spaces."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def compute_root(manifest_canonical: str) -> str:
    return "0x" + keccak(manifest_canonical.encode()).hex()


def build_manifest(agent: dict, axl_pubkey: str, code_hash: str) -> dict:
    return {
        "schema_version": "1",
        "agent_id": agent["id"],
        "eth_address": agent["address"].lower(),
        "axl_pubkey": axl_pubkey,
        "analyzer_code_hash": code_hash,
        "specialty": "oracle_manipulation",
        "reputation": {"rescues": 0, "false_positives": 0},
        "created_at": "2026-04-27",
    }


def main() -> int:
    MANIFESTS_DIR.mkdir(exist_ok=True)
    keys = json.loads(KEYS_PATH.read_text())["agents"]
    roster = json.loads(ROSTER_PATH.read_text())["agents"]
    code_hash = analyzer_code_hash()
    print(f"analyzer code hash: {code_hash}\n")

    index = {"agents": [], "code_hash": code_hash}
    for k in keys:
        roster_entry = next((r for r in roster if r["id"] == k["id"]), None)
        if roster_entry is None:
            raise RuntimeError(f"agent {k['id']} missing from roster")
        manifest = build_manifest(k, roster_entry["axlPubkey"], code_hash)

        # Sign the manifest with the agent's own ETH key. Anyone with the
        # manifest can recover the signer and confirm it's the agent's.
        canonical = canonical_json(manifest)
        signed = Account.sign_message(encode_defunct(text=canonical), private_key=k["privateKey"])
        manifest["signature"] = "0x" + signed.signature.hex()

        # Re-canonicalize WITH the signature so the on-chain root commits to
        # both the manifest and its self-signature.
        canonical_signed = canonical_json(manifest)
        root = compute_root(canonical_signed)

        out_path = MANIFESTS_DIR / f"agent-{k['id']}.json"
        out_path.write_text(canonical_signed + "\n")
        print(f"agent {k['id']}: {root}  -> {out_path.relative_to(REPO_ROOT)}")
        index["agents"].append({
            "id": k["id"],
            "eth_address": k["address"],
            "root_hash": root,
            "path": str(out_path.relative_to(REPO_ROOT)),
        })

    (MANIFESTS_DIR / "manifests.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"\nindex: {(MANIFESTS_DIR / 'manifests.json').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
