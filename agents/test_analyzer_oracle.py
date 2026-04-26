"""Tests for the oracle-manipulation analyzer.

Synthetic PriceBumpedEvents — no chain access. Verifies detection rule,
no-fire on benign moves, deterministic findingHash across the three
agents (so quorum forms), severity ladder.

Run:  .venv/bin/python agents/test_analyzer_oracle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyzer_oracle import OracleManipulationAnalyzer, PriceBumpedEvent


CHAIN_ID = 16602
POOL = "0x51A3f25C391C9CDf1421198e94E3aBB71b96A18c"
ORACLE = "0xD0F93DD3e498C456A95cc91d1FBcB8dB24b122A9"

AGENT_A = ("a", "0x4A0AF400AdF0CF99cF7Bab4F05E84a227bb15fFA")
AGENT_B = ("b", "0xD87AD210297A2d7ECAc28AaFc224F9d1444221fa")
AGENT_C = ("c", "0x92977216087Baec7Ff1Deb14e07258B06DB08804")


def _analyzer(agent):
    return OracleManipulationAnalyzer(
        chain_id=CHAIN_ID,
        pool_address=POOL,
        oracle_address=ORACLE,
        agent_id=agent[0],
        agent_address=agent[1],
    )


def _event(old: int, new: int, *, tx="0x" + "ab" * 32, block=42, by="0x" + "11" * 20):
    return PriceBumpedEvent(by=by, old_price=old, new_price=new, tx_hash=tx, block_number=block)


def test_demo_exploit_flagged_critical():
    """1000x bump (the actual attacker.s.sol bump) → critical."""
    a = _analyzer(AGENT_A)
    f = a.analyze_event(_event(old=10**18, new=10**21))
    assert f is not None
    assert f.finding_type == "oracle_manipulation"
    assert f.severity == "critical"
    assert f.evidence["ratio"] == 1000


def test_5x_bump_at_threshold_flagged_medium():
    a = _analyzer(AGENT_A)
    f = a.analyze_event(_event(old=100, new=500))
    assert f is not None
    assert f.severity == "medium"


def test_4x_bump_below_threshold_ignored():
    a = _analyzer(AGENT_A)
    assert a.analyze_event(_event(old=100, new=400)) is None


def test_2x_bump_organic_move_ignored():
    a = _analyzer(AGENT_A)
    assert a.analyze_event(_event(old=10**18, new=2 * 10**18)) is None


def test_zero_to_nonzero_flagged():
    a = _analyzer(AGENT_A)
    f = a.analyze_event(_event(old=0, new=1))
    assert f is not None


def test_zero_to_zero_ignored():
    a = _analyzer(AGENT_A)
    assert a.analyze_event(_event(old=0, new=0)) is None


def test_severity_ladder():
    a = _analyzer(AGENT_A)
    assert a.analyze_event(_event(old=1, new=5)).severity == "medium"     # 5x
    assert a.analyze_event(_event(old=1, new=10)).severity == "high"      # 10x
    assert a.analyze_event(_event(old=1, new=100)).severity == "critical" # 100x
    assert a.analyze_event(_event(old=1, new=1000)).severity == "critical"


def test_three_agents_compute_same_findingHash_on_same_event():
    """Quorum can only form if all agents hash to the same bytes32."""
    evt = _event(old=10**18, new=10**21, tx="0x" + "cd" * 32, block=99)
    h_a = _analyzer(AGENT_A).analyze_event(evt).finding_hash()
    h_b = _analyzer(AGENT_B).analyze_event(evt).finding_hash()
    h_c = _analyzer(AGENT_C).analyze_event(evt).finding_hash()
    assert h_a == h_b == h_c
    # And differs from a different incident
    other = _analyzer(AGENT_A).analyze_event(_event(old=10**18, new=10**21, block=100))
    assert other.finding_hash() != h_a


def test_agent_identity_recorded_but_excluded_from_hash():
    evt = _event(old=10**18, new=10**21)
    f_a = _analyzer(AGENT_A).analyze_event(evt)
    f_b = _analyzer(AGENT_B).analyze_event(evt)
    assert f_a.agent_id == "a" and f_b.agent_id == "b"
    assert f_a.agent_address != f_b.agent_address
    assert f_a.finding_hash() == f_b.finding_hash()


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
