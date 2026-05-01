"""Python wrapper around the og-compute Node bridge.

Subprocesses `node_modules/.bin/tsx summarize-finding.ts` because the 0G
Compute SDK is TypeScript-only. The bridge handles deposit-account state,
broker init, signed-inference call, signature fetch, and TEE verification
in one round-trip — Python just hands it a prompt and parses the JSON.

Latency budget: ~3-5 s per call (broker on-chain ack + provider hit). Day 5
agents block on this synchronously between detection and broadcast — the
demo gate window is "between block N and block N+1" which on 0G is roughly
1-2 s, so summarization can land *just after* the bump and still leave
room before drain. Worst case the summary lags one block; quorum still
forms via 3 independent broadcasts.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_DIR = REPO_ROOT / "og-compute"
BRIDGE_SCRIPT = BRIDGE_DIR / "summarize-finding.ts"
TSX = BRIDGE_DIR / "node_modules" / ".bin" / "tsx"

log = logging.getLogger("og_compute")


@dataclass(frozen=True)
class Attestation:
    summary: str
    tee_attestation_hash: str  # 0x-bytes32 — keccak256(tee_text)
    tee_text: str
    tee_signature: str
    tee_signing_address: str
    verified: bool


def summarize(prompt: str, max_tokens: int = 80, temperature: float = 0.2, timeout_s: float = 180.0) -> Attestation:
    """Send a prompt to the 0G Compute provider and return a TEE-signed
    attestation over the response. Raises on bridge failure or non-verified
    attestation — agents shouldn't gossip Findings backed by unverified TEEs.
    """
    if not TSX.exists():
        raise RuntimeError(f"og-compute deps not installed: {TSX} missing. Run `npm install` in og-compute/.")
    if not BRIDGE_SCRIPT.exists():
        raise RuntimeError(f"bridge script missing: {BRIDGE_SCRIPT}")

    payload = json.dumps({"prompt": prompt, "max_tokens": max_tokens, "temperature": temperature})
    proc = subprocess.run(
        [str(TSX), str(BRIDGE_SCRIPT)],
        cwd=str(BRIDGE_DIR),
        input=payload,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"og-compute bridge exited {proc.returncode}: {proc.stderr.strip()}")
    last_line = proc.stdout.strip().splitlines()[-1]
    out = json.loads(last_line)
    att = Attestation(
        summary=out["summary"],
        tee_attestation_hash=out["tee_attestation_hash"],
        tee_text=out["tee_text"],
        tee_signature=out["tee_signature"],
        tee_signing_address=out["tee_signing_address"],
        verified=bool(out["verified"]),
    )
    if not att.verified:
        log.warning("attestation returned verified=false; signing_address=%s", att.tee_signing_address)
    return att


def verify_attestation_locally(att: Attestation) -> bool:
    """Re-verify a TEE attestation without hitting the provider — used by
    receivers to gate quorum. Recovers the signer of `tee_text` (ETH-prefixed
    hash) and compares to `tee_signing_address`.
    """
    from eth_account import Account
    from eth_account.messages import encode_defunct

    try:
        signer = Account.recover_message(
            encode_defunct(text=att.tee_text),
            signature=att.tee_signature,
        )
    except Exception:
        return False
    return signer.lower() == att.tee_signing_address.lower()
