"""Klaxon Signal — signed Finding type.

A Finding is what an analyzer broadcasts when it spots an exploit pattern.
The on-chain Guardian.verifyQuorum verifies an array of secp256k1 sigs over
a single `findingHash`, so all agents observing the same incident MUST hash
the same canonical bytes — otherwise their sigs cover different hashes and
no quorum forms.

Canonical hash = keccak256(json.dumps(canonical_dict, sort_keys=True)) where
canonical_dict is the Finding minus the signature. Stable across Python
processes; deterministic across analyzers seeing the same incident.

Signature = ETH-prefixed personal_sign of findingHash, exactly matching the
Guardian's verification path:
    bytes32 ethSigned = keccak256("\\x19Ethereum Signed Message:\\n32" || findingHash)
    address signer = ecrecover(ethSigned, v, r, s)
"""

from __future__ import annotations

import json
from typing import Literal

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import keccak
from pydantic import BaseModel, Field

FindingType = Literal["reentrancy", "oracle_manipulation"]
Severity = Literal["low", "medium", "high", "critical"]


class Finding(BaseModel):
    """A single analyzer's observation of a suspicious tx.

    Fields with `_excluded` in their canonicalization are runtime-only and
    do NOT contribute to findingHash — otherwise two agents wouldn't agree.
    """

    # Canonical fields (contribute to findingHash):
    chain_id: int
    pool_address: str
    finding_type: FindingType
    severity: Severity
    tx_hash: str  # the offending or trigger tx
    block_number: int
    evidence: dict  # analyzer-specific structured payload

    # Runtime fields (NOT in findingHash):
    agent_id: str = Field(..., description="roster id of the signing agent (a/b/c)")
    agent_address: str = Field(..., description="signer's secp256k1 address (0x...)")
    signature: str | None = Field(default=None, description="65-byte hex sig over findingHash")
    tee_attestation_hash: str = Field(
        default="0x" + "00" * 32,
        description="bytes32 keccak256(tee_text) — committed to on-chain via Guardian.FindingAttested",
    )
    # The full TEE envelope. Receivers verify locally (no provider round-trip)
    # before counting this Finding toward quorum.
    tee_summary: str | None = Field(default=None, description="human-readable summary signed by the enclave")
    tee_text: str | None = Field(default=None, description="raw text the enclave signed (commitment string)")
    tee_signature: str | None = Field(default=None, description="65-byte hex secp256k1 sig over tee_text")
    tee_signing_address: str | None = Field(default=None, description="enclave's on-chain identity")

    def canonical_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "pool_address": self.pool_address.lower(),
            "finding_type": self.finding_type,
            "severity": self.severity,
            "tx_hash": self.tx_hash.lower(),
            "block_number": self.block_number,
            "evidence": _canonicalize(self.evidence),
        }

    def finding_hash(self) -> bytes:
        canonical = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))
        return keccak(canonical.encode())

    def finding_hash_hex(self) -> str:
        return "0x" + self.finding_hash().hex()

    def sign(self, private_key: str) -> "Finding":
        """Return a copy of self with `signature` set."""
        h = self.finding_hash()
        signed = Account.sign_message(encode_defunct(h), private_key=private_key)
        sig_bytes = signed.signature
        return self.model_copy(update={"signature": "0x" + sig_bytes.hex()})

    def recover_signer(self) -> str:
        """Recover the signer address from `signature`. Returns lowercase 0x-hex."""
        if self.signature is None:
            raise ValueError("Finding has no signature")
        h = self.finding_hash()
        signer = Account.recover_message(encode_defunct(h), signature=self.signature)
        return signer.lower()

    def verify_self_signed(self) -> bool:
        """True iff signature is present and recovers to agent_address."""
        if self.signature is None:
            return False
        try:
            return self.recover_signer() == self.agent_address.lower()
        except Exception:
            return False

    def verify_tee_attestation(self) -> bool:
        """True iff this Finding carries a TEE envelope, the signature
        recovers to the claimed signing_address, and the attestation hash
        commits to the signed text. Receivers call this before counting
        the Finding toward quorum — proves an authentic enclave attested
        the summary, no provider round-trip required."""
        if not (self.tee_text and self.tee_signature and self.tee_signing_address):
            return False
        try:
            signer = Account.recover_message(
                encode_defunct(text=self.tee_text),
                signature=self.tee_signature,
            )
            if signer.lower() != self.tee_signing_address.lower():
                return False
        except Exception:
            return False
        # Attestation hash must commit to the same text the enclave signed.
        expected = "0x" + keccak(self.tee_text.encode()).hex()
        return expected.lower() == self.tee_attestation_hash.lower()

    def to_wire(self) -> bytes:
        """Serialize for AXL gossip."""
        return self.model_dump_json().encode()

    @classmethod
    def from_wire(cls, raw: bytes) -> "Finding":
        return cls.model_validate_json(raw)


def _canonicalize(obj):
    """Recursive lowercase + sort to make findingHash invariant to hex casing
    and dict insertion order. Strings starting with 0x are lowercased."""
    if isinstance(obj, dict):
        return {k: _canonicalize(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_canonicalize(v) for v in obj]
    if isinstance(obj, str) and obj.startswith("0x"):
        return obj.lower()
    return obj
