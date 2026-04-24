# KeeperHub Builder Feedback

Feedback for the [KeeperHub Builder Feedback Bounty](https://ethglobal.com/events/openagents/prizes/keeperhub) ($500, up to 2 teams at $250 each).

Built against KeeperHub during the ETHGlobal Open Agents hackathon (Apr 25 – May 3, 2026).

---

## UX / UI friction

_Specific, reproducible — filled in as encountered during Day 6 integration._

## Bugs

_Reproducible — include repro steps, expected vs actual behavior._

## Documentation gaps

_Where the docs left us stuck — specific URLs, missing sections, unclear examples._

## Feature requests

_What's missing that would have made the Klaxon build easier._

---

## Our use case (context for feedback)

Klaxon uses KeeperHub as the execution layer for protocol pause/sweep transactions triggered by a decentralized AI agent swarm. Specifically:

- An aggregator agent collects signed findings from peer agents over Gensyn AXL
- Once 3-of-N quorum is reached, the aggregator invokes a KeeperHub workflow via MCP/CLI to:
  1. Verify quorum signatures onchain against the Guardian contract
  2. Submit the `pause()` tx with private routing + retry
  3. For multi-block exploits, follow up with `sweepToRecovery()`
- Agent bounty splits are paid out via x402 after successful execution (hitting the suggested x402/MPP integration angle).
