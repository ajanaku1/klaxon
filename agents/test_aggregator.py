"""Tests for the per-node aggregator state machine."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggregator import Aggregator
from finding import Finding


# Three real keys from axl/agent-eth-keys.json (gitignored).
KEYS = [
    ("a", "0x4A0AF400AdF0CF99cF7Bab4F05E84a227bb15fFA",
     "0xee49aa1a6edd8968bb8f85edbf2586e15c5892975846dcf1556e3e5af7c74142"),
    ("b", "0xD87AD210297A2d7ECAc28AaFc224F9d1444221fa",
     "0x432b55eb03f3cab79f82b76464c60e651f22bc96f41d21385cdf44c6348588cb"),
    ("c", "0x92977216087Baec7Ff1Deb14e07258B06DB08804",
     "0x15f23eb6d9b892a326068a5e86ec60fa2284079cd83dfa92b200659d6edea184"),
]
AUTHORIZED = frozenset(addr.lower() for _, addr, _ in KEYS)

# A 4th key not in the authorized set
INTRUDER_PK = "0xd985e7d377419cdab9320c66cebf35a7bbfbec042056ec256f6aeda919b3462d"
INTRUDER_ADDR = "0x6d4B6bba630Ddd33dFD54769fd9158b0c31283df"


def make_finding(agent_id: str, agent_addr: str, **overrides) -> Finding:
    base = dict(
        chain_id=16602,
        pool_address="0x51A3f25C391C9CDf1421198e94E3aBB71b96A18c",
        finding_type="oracle_manipulation",
        severity="critical",
        tx_hash="0x" + "ab" * 32,
        block_number=42,
        evidence={"old_price": 1, "new_price": 1000},
        agent_id=agent_id,
        agent_address=agent_addr,
    )
    base.update(overrides)
    return Finding(**base)


def signed_findings_from_all_three():
    return [make_finding(aid, addr).sign(pk) for aid, addr, pk in KEYS]


def test_quorum_fires_after_third_distinct_signer():
    agg = Aggregator(authorized_signers=AUTHORIZED, quorum_size=3)
    fs = signed_findings_from_all_three()
    assert agg.add_finding(fs[0]) is None
    assert agg.add_finding(fs[1]) is None
    q = agg.add_finding(fs[2])
    assert q is not None
    assert len(q.sigs) == 3
    assert len(q.signers) == 3
    assert q.signers == sorted(q.signers)


def test_quorum_only_fires_once_per_hash():
    agg = Aggregator(authorized_signers=AUTHORIZED, quorum_size=3)
    fs = signed_findings_from_all_three()
    for f in fs:
        agg.add_finding(f)
    # Re-adding any finding does nothing
    assert agg.add_finding(fs[0]) is None


def test_duplicate_signer_does_not_double_count():
    agg = Aggregator(authorized_signers=AUTHORIZED, quorum_size=3)
    aid, addr, pk = KEYS[0]
    f1 = make_finding(aid, addr).sign(pk)
    aid2, addr2, pk2 = KEYS[1]
    f2 = make_finding(aid2, addr2).sign(pk2)
    assert agg.add_finding(f1) is None
    assert agg.add_finding(f1) is None  # duplicate
    assert agg.add_finding(f2) is None  # only 2 distinct signers
    # Now a third distinct signer fires quorum
    aid3, addr3, pk3 = KEYS[2]
    q = agg.add_finding(make_finding(aid3, addr3).sign(pk3))
    assert q is not None


def test_unauthorized_signer_rejected():
    agg = Aggregator(authorized_signers=AUTHORIZED, quorum_size=3)
    intruder = make_finding(agent_id="x", agent_addr=INTRUDER_ADDR).sign(INTRUDER_PK)
    assert agg.add_finding(intruder) is None
    aid, addr, pk = KEYS[0]
    aid2, addr2, pk2 = KEYS[1]
    agg.add_finding(make_finding(aid, addr).sign(pk))
    agg.add_finding(make_finding(aid2, addr2).sign(pk2))
    # Still no quorum — intruder didn't count
    assert not agg.already_fired(make_finding("a", KEYS[0][1]).finding_hash())


def test_forged_agent_address_rejected():
    """A peer that rewrites agent_address (so signature recovers to someone
    else) gets rejected — the aggregator cross-checks recover(sig) against
    the claimed agent_address."""
    agg = Aggregator(authorized_signers=AUTHORIZED, quorum_size=3)
    aid, addr, pk = KEYS[0]
    legit = make_finding(aid, addr).sign(pk)
    forged = legit.model_copy(update={"agent_id": "b", "agent_address": KEYS[1][1]})
    assert agg.add_finding(forged) is None


def test_unsigned_finding_rejected():
    agg = Aggregator(authorized_signers=AUTHORIZED, quorum_size=3)
    f = make_finding("a", KEYS[0][1])
    assert f.signature is None
    assert agg.add_finding(f) is None


def test_different_findings_get_separate_buckets():
    agg = Aggregator(authorized_signers=AUTHORIZED, quorum_size=3)
    f_block42 = [make_finding(aid, addr, block_number=42).sign(pk) for aid, addr, pk in KEYS]
    f_block43 = [make_finding(aid, addr, block_number=43).sign(pk) for aid, addr, pk in KEYS]
    # Mix two votes from each — neither should reach quorum
    agg.add_finding(f_block42[0])
    agg.add_finding(f_block42[1])
    agg.add_finding(f_block43[0])
    agg.add_finding(f_block43[1])
    assert agg.add_finding(f_block42[2]) is not None  # 42 fires
    assert agg.add_finding(f_block43[2]) is not None  # 43 fires independently


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
