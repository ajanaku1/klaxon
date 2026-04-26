"""Tests for Finding canonical hash + signing.

Critical correctness check: `Account.sign_message(encode_defunct(h))` must
produce a sig that recovers to the signer when verified by the SAME ETH-
prefixed flow Guardian.sol uses. Verified here by recovering with
`Account.recover_message(encode_defunct(h), signature=sig)` and confirming
the recovered address matches.

A second test confirms determinism: two Finding instances built from the
same canonical fields produce the same findingHash regardless of dict
insertion order or 0x hex casing.

Run:  .venv/bin/python -m pytest agents/test_finding.py -v
   or .venv/bin/python agents/test_finding.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from finding import Finding


# Use one of the canonical agent keys from axl/agent-eth-keys.json (gitignored).
# Hardcoded here for the test only; matches AGENT_A.
AGENT_A_PK = "0xee49aa1a6edd8968bb8f85edbf2586e15c5892975846dcf1556e3e5af7c74142"
AGENT_A_ADDR = "0x4A0AF400AdF0CF99cF7Bab4F05E84a227bb15fFA"

POOL = "0x51A3f25C391C9CDf1421198e94E3aBB71b96A18c"


def make_finding(**overrides) -> Finding:
    base = dict(
        chain_id=16602,
        pool_address=POOL,
        finding_type="oracle_manipulation",
        severity="critical",
        tx_hash="0xabc" + "0" * 61,
        block_number=42,
        evidence={"old_price": 1, "new_price": 1000, "multiplier": 1000},
        agent_id="a",
        agent_address=AGENT_A_ADDR,
    )
    base.update(overrides)
    return Finding(**base)


def test_finding_hash_deterministic_across_dict_order():
    f1 = make_finding(evidence={"a": 1, "b": 2, "c": 3})
    f2 = make_finding(evidence={"c": 3, "b": 2, "a": 1})
    assert f1.finding_hash() == f2.finding_hash(), "dict order changed hash"


def test_finding_hash_lowercases_hex_strings():
    f1 = make_finding(tx_hash="0xABC" + "0" * 61, pool_address=POOL.upper())
    f2 = make_finding(tx_hash="0xabc" + "0" * 61, pool_address=POOL.lower())
    assert f1.finding_hash() == f2.finding_hash(), "hex casing changed hash"


def test_finding_hash_changes_with_content():
    f1 = make_finding(block_number=42)
    f2 = make_finding(block_number=43)
    assert f1.finding_hash() != f2.finding_hash()


def test_finding_hash_excludes_runtime_fields():
    """signature, tee_attestation_hash, agent_id, agent_address must NOT
    contribute to findingHash — otherwise two agents seeing the same
    incident would compute different hashes and quorum wouldn't form."""
    f1 = make_finding(agent_id="a")
    f2 = make_finding(agent_id="b", agent_address="0x000000000000000000000000000000000000dead")
    f3 = make_finding(tee_attestation_hash="0x" + "ff" * 32)
    assert f1.finding_hash() == f2.finding_hash()
    assert f1.finding_hash() == f3.finding_hash()


def test_sign_then_recover_roundtrip():
    f = make_finding()
    signed = f.sign(AGENT_A_PK)
    assert signed.signature is not None
    assert signed.recover_signer() == AGENT_A_ADDR.lower()
    assert signed.verify_self_signed()


def test_sign_returns_copy_does_not_mutate():
    f = make_finding()
    signed = f.sign(AGENT_A_PK)
    assert f.signature is None  # original untouched
    assert signed.signature is not None


def test_wire_roundtrip_preserves_signature_and_hash():
    signed = make_finding().sign(AGENT_A_PK)
    raw = signed.to_wire()
    decoded = Finding.from_wire(raw)
    assert decoded.signature == signed.signature
    assert decoded.finding_hash() == signed.finding_hash()
    assert decoded.recover_signer() == AGENT_A_ADDR.lower()


def test_signature_invariant_to_runtime_field_change():
    """If a malicious peer mutates agent_id but keeps the signature, the
    sig should still recover to the original signer (since agent_id is not
    in the hash). The aggregator's job is to discard such forgeries by
    cross-checking that signature recovers to agent_address."""
    signed = make_finding(agent_id="a", agent_address=AGENT_A_ADDR).sign(AGENT_A_PK)
    forged = signed.model_copy(update={"agent_id": "b", "agent_address": "0x" + "11" * 20})
    # Hash unchanged because agent_id/address are runtime-only
    assert forged.finding_hash() == signed.finding_hash()
    # Signature recovers to agent A — but agent_address now claims someone else
    assert forged.recover_signer() == AGENT_A_ADDR.lower()
    assert not forged.verify_self_signed()  # mismatch caught


def main() -> int:
    """Minimal test runner so we don't need pytest installed."""
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}  -> {e}")
            failures += 1
        except Exception as e:
            print(f"ERROR {t.__name__}  -> {type(e).__name__}: {e}")
            failures += 1
    print(f"\n{len(tests) - failures}/{len(tests)} passing")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
