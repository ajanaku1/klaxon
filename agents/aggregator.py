"""Per-node aggregator — collects signed Findings, fires when quorum forms.

State machine: keyed by findingHash, holding the set of distinct authorized
signer addresses observed and their signatures. The aggregator does NOT
care about ordering or who-arrived-first; quorum is just |distinct
authorized signers| >= K.

Validity checks for each ingested Finding:
  1. signature must recover to a signer (eth_account does this).
  2. recovered signer must equal `agent_address` claimed in the Finding.
     This catches the case where a malicious peer rewrites agent_id /
     agent_address on a forwarded Finding without invalidating the sig
     itself (since runtime fields aren't in the hash).
  3. recovered signer must be in the authorized set (the on-chain
     Guardian's authorizedAgents).

Quorum returns sigs in ASCENDING signer-address order — Guardian doesn't
require this, but it makes test reproducibility and gas accounting stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from finding import Finding


@dataclass(frozen=True)
class Quorum:
    finding_hash: bytes
    sigs: list[bytes]
    signers: list[str]  # lowercase 0x-hex, in same order as `sigs`
    representative: Finding  # any one of the contributing Findings — used for tee_attestation_hash


@dataclass
class Aggregator:
    authorized_signers: frozenset[str]  # lowercase 0x-hex
    quorum_size: int = 3
    _by_hash: dict[bytes, dict[str, tuple[bytes, Finding]]] = field(default_factory=dict)
    _fired: set[bytes] = field(default_factory=set)

    def add_finding(self, f: Finding) -> Quorum | None:
        """Ingest a Finding. Returns a Quorum the FIRST time this hash hits
        the threshold, then None on subsequent calls for the same hash."""
        if not f.signature:
            return None
        try:
            signer = f.recover_signer()
        except Exception:
            return None

        if signer != f.agent_address.lower():
            # Forged or mutated Finding — sig recovers to a different address
            return None
        if signer not in self.authorized_signers:
            return None

        h = f.finding_hash()
        if h in self._fired:
            return None

        bucket = self._by_hash.setdefault(h, {})
        if signer in bucket:
            return None  # already counted this signer's vote
        # signature is hex (0x-prefixed); store raw bytes for on-chain submission
        sig_bytes = bytes.fromhex(f.signature[2:] if f.signature.startswith("0x") else f.signature)
        bucket[signer] = (sig_bytes, f)

        if len(bucket) >= self.quorum_size:
            self._fired.add(h)
            ordered = sorted(bucket.items(), key=lambda kv: kv[0])
            return Quorum(
                finding_hash=h,
                sigs=[sig for _, (sig, _) in ordered],
                signers=[addr for addr, _ in ordered],
                representative=ordered[0][1][1],
            )
        return None

    def already_fired(self, finding_hash: bytes) -> bool:
        return finding_hash in self._fired
