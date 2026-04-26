"""Live test of the Python ↔ Node bridge against 0G Compute.

Hits the actual provider on Galileo. Skips automatically if og-compute/
node_modules isn't installed.

Run:  .venv/bin/python agents/test_og_compute.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from og_compute import TSX, summarize, verify_attestation_locally


def test_round_trip_returns_attested_summary():
    if not TSX.exists():
        print("SKIP: og-compute/node_modules missing")
        return
    att = summarize(
        "Say 'klaxon-bridge-test' and nothing else.",
        max_tokens=12,
        temperature=0,
    )
    assert att.summary, f"empty summary: {att}"
    assert att.tee_attestation_hash.startswith("0x") and len(att.tee_attestation_hash) == 66
    assert att.tee_signature.startswith("0x") and len(att.tee_signature) == 132  # 65 bytes hex + 0x
    assert att.tee_signing_address.startswith("0x") and len(att.tee_signing_address) == 42
    assert att.verified is True


def test_local_signature_verification_passes_for_valid_attestation():
    if not TSX.exists():
        print("SKIP: og-compute/node_modules missing")
        return
    att = summarize("Say 'klaxon-verify-local' and nothing else.", max_tokens=12, temperature=0)
    assert verify_attestation_locally(att), (
        f"local verify failed for live attestation: signer={att.tee_signing_address}"
    )


def test_local_verification_rejects_tampered_text():
    if not TSX.exists():
        print("SKIP: og-compute/node_modules missing")
        return
    att = summarize("Say 'klaxon-tamper' and nothing else.", max_tokens=12, temperature=0)
    from dataclasses import replace
    bad = replace(att, tee_text=att.tee_text + "TAMPERED")
    assert not verify_attestation_locally(bad), "tampered text incorrectly verified"


def main() -> int:
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
