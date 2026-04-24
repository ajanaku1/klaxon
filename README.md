# Klaxon

**Decentralized pause oracle for DeFi.** A swarm of independently-operated AI agents watches your contracts, cross-verifies findings inside TEEs, and autonomously triggers protocol pauses when economic quorum backs the call. No one agent can pause. No one agent can lie without getting slashed.

*"When one finds it, a thousand answer."*

Built for [ETHGlobal Open Agents](https://ethglobal.com/events/openagents) (Apr 24 – May 3, 2026).

---

## Status

🚧 **Build in progress.** See [`PLAN.md`](./PLAN.md) for the day-by-day build plan and current status.

## Prize tracks

- [0G](https://ethglobal.com/events/openagents/prizes/0g) — Track B: Autonomous Agents/Swarms/iNFT Innovations ($7.5k)
- [Gensyn AXL](https://ethglobal.com/events/openagents/prizes/gensyn) — Best Application of Agent eXchange Layer ($5k)
- [KeeperHub](https://ethglobal.com/events/openagents/prizes/keeperhub) — Best Use of KeeperHub + Builder Feedback Bounty ($4.5k + $500)

## Stack

- **0G Chain** — Guardian + iNFT contracts deployed here
- **0G Storage** — agent manifests + reputation logs (Merkle root hashes)
- **0G Compute Sealed Inference** — TEE-signed finding summaries (Intel TDX + H100)
- **Gensyn AXL** — signed finding gossip across independent agent nodes
- **KeeperHub** — pause/sweep tx execution with retry, private routing, gas optimization
- **x402** — agent bounty splits post-rescue (Base Sepolia, V2 sessions)

## Architecture

See [`specs/architecture.md`](./specs/architecture.md) for the full architecture.

High-level: analyzer agents watch a protocol's contracts → detect suspected exploit → each finding is summarized by an LLM call through 0G Sealed Inference (TEE signs the summary) → signed findings gossip across AXL → quorum of 3-of-N independent operators triggers a Guardian contract's `pause()` via KeeperHub.

## Honest TEE scope

0G Compute Sealed Inference is a TEE-attested LLM inference service, not an arbitrary-workload TEE. Klaxon analyzers run **off-TEE** on the agent node; findings are summarized via 0G Compute, which signs the summary inside the enclave. The attestation proves *"this finding was summarized by this model in a TEE,"* not *"the raw detection was done in a TEE."* Future work: move analyzer weights into a 0G Compute provider model so detection itself is enclave-attested.

## Repo layout

```
contracts/    # Foundry — Guardian, VulnerableLendingPool, AgentINFT (ERC-7857)
agents/       # Python — analyzer agents, AXL client, aggregator
dashboard/    # Next.js — swarm topology, finding feed, rescue replay
axl/          # AXL node configs + run scripts
specs/        # Architecture + prompt artifacts (spec-driven dev)
docs/         # Per-prize submission write-ups
```

## Setup

_Coming once Day 3–6 land. Target: `npm run demo` spins up 2 AXL nodes + attacker + dashboard end-to-end._

## Submission artifacts

- [`AI_USAGE.md`](./AI_USAGE.md) — per-file AI attribution (ETHGlobal requirement)
- [`FEEDBACK.md`](./FEEDBACK.md) — KeeperHub Builder Feedback Bounty submission
- [`specs/`](./specs/) — spec-driven dev artifacts (prompts + plans)

## License

MIT (TBD — finalize before submission)
