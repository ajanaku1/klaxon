"""Analyzer 1 — oracle-manipulation detector.

Pure detection logic. Watches the protected protocol's price oracle for
single-tx jumps that are too large to be organic, and emits an unsigned
Finding for each suspicious event. The agent runtime is responsible for
driving block iteration, signing, and gossip.

Detection rule (hackathon-grade):
    newPrice / oldPrice >= JUMP_RATIO_THRESHOLD  (default 5x)

5x in one tx is well outside any realistic price move on a real oracle —
even on illiquid assets, organic moves come in over many blocks. A 1000x
move (the demo exploit) blows past this trivially. False-positive risk is
acceptable for a hackathon; production would TWAP-compare and look for
back-and-forth pump+drain shapes.
"""

from __future__ import annotations

from dataclasses import dataclass

from finding import Finding


JUMP_RATIO_THRESHOLD = 5  # newPrice >= oldPrice * 5  ⇒ flag


@dataclass(frozen=True)
class PriceBumpedEvent:
    """Decoded ManipulableOracle.PriceBumped log entry."""

    by: str
    old_price: int
    new_price: int
    tx_hash: str
    block_number: int


@dataclass(frozen=True)
class OracleManipulationAnalyzer:
    """Stateless analyzer. Bound to one (chain_id, oracle, pool) tuple."""

    chain_id: int
    pool_address: str
    oracle_address: str
    agent_id: str
    agent_address: str
    threshold: int = JUMP_RATIO_THRESHOLD

    def is_suspicious(self, evt: PriceBumpedEvent) -> bool:
        if evt.old_price == 0:
            # Zero → nonzero is itself anomalous; flag.
            return evt.new_price > 0
        return evt.new_price >= evt.old_price * self.threshold

    def analyze_event(self, evt: PriceBumpedEvent) -> Finding | None:
        """Return an UNSIGNED Finding if the event looks like manipulation,
        else None. Caller (agent runtime) signs and broadcasts."""
        if not self.is_suspicious(evt):
            return None
        ratio = (evt.new_price // evt.old_price) if evt.old_price else evt.new_price
        return Finding(
            chain_id=self.chain_id,
            pool_address=self.pool_address,
            finding_type="oracle_manipulation",
            severity=_severity_for_ratio(ratio),
            tx_hash=evt.tx_hash,
            block_number=evt.block_number,
            evidence={
                "oracle": self.oracle_address.lower(),
                "old_price": evt.old_price,
                "new_price": evt.new_price,
                "ratio": ratio,
                "by": evt.by.lower(),
            },
            agent_id=self.agent_id,
            agent_address=self.agent_address,
        )


def _severity_for_ratio(ratio: int) -> str:
    if ratio >= 100:
        return "critical"
    if ratio >= 10:
        return "high"
    return "medium"
