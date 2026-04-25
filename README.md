# Klaxon: An agent arena for DeFi exploit detection

Bonded analyzer iNFTs compete to spot exploits in real time. Each finding is cross-verified inside a TEE, gossiped peer-to-peer, and once three independent agents agree, the protocol pauses automatically. Winners earn bounty splits. False positives get slashed.

[![Solidity](https://img.shields.io/badge/Solidity-0.8-363636?logo=solidity)](https://soliditylang.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*"When one finds it, a thousand answer."*

Built for [ETHGlobal Open Agents](https://ethglobal.com/events/openagents) (April 24 to May 3, 2026).

---

## Status

Build in progress. See [`PLAN.md`](./PLAN.md) for the day-by-day build plan and current status.

---

## What Is Klaxon?

Every DeFi protocol has a pauser multisig. It is the most dangerous key in the system and also the slowest. Klaxon replaces it with an open arena of bonded AI analyzer agents, each minted as an iNFT with its own reputation and stake. Agents compete to detect exploits, verify each finding inside a Trusted Execution Environment, and trigger a protocol pause only when three independent agents reach quorum.

Your funds stop moving the second the swarm knows. Not when your ops team wakes up.

Every quorum-passing finding emits an on-chain `FindingAttested` event with the TEE attestation hash, so any auditor can verify the claim on the 0G explorer. The pause is autonomous, but the proof is public.

---

## Prize Tracks

Klaxon targets three ETHGlobal Open Agents partner prizes with load-bearing integrations:

| Sponsor | Track | Prize |
|---|---|---|
| [0G](https://ethglobal.com/events/openagents/prizes/0g) | Track B: Autonomous Agents, Swarms, iNFT | $7,500 |
| [Gensyn AXL](https://ethglobal.com/events/openagents/prizes/gensyn) | Best Application of Agent eXchange Layer | $5,000 |
| [KeeperHub](https://ethglobal.com/events/openagents/prizes/keeperhub) | Best Use of KeeperHub + Builder Feedback Bounty | $4,500 + $500 |

---

## Features

- **Agents as bonded iNFTs**: every analyzer is minted as an ERC-7857 iNFT on 0G Chain. Reputation and analyzer code hash live in 0G Storage. Bonded agents earn; misbehaving ones get slashed
- **Decentralized pause authority**: replaces a single pauser multisig with an N-of-M signature quorum from independently-operated agents
- **TEE-attested findings on-chain**: every signed finding is summarized inside 0G Sealed Inference (Intel TDX + NVIDIA H100). Quorum-passing findings emit a `FindingAttested` event so any auditor can verify the attestation hash on the 0G explorer
- **Peer-to-peer gossip over AXL**: signed findings propagate across the Gensyn mesh with no central broker
- **Economic quorum**: agents stake bonds, earn bounties on verified rescues, and lose bonds on false positives
- **Bounded action surface**: agents can only sign findings, never hold keys or move funds. Every move is executed by a Guardian contract that only sweeps to the protocol's own preset recovery vault
- **Reliable execution**: KeeperHub submits pause and sweep transactions with private routing, retries, and gas optimization
- **Bounty splits via x402**: post-rescue payments to participating agents settle in a single x402 V2 session

---

## Tech Stack

| Layer | Technology |
|---|---|
| Contracts | Solidity 0.8, Foundry, 0G Chain (EVM-compatible) |
| Agent runtime | Python 3.10, Pydantic, `requests` |
| P2P mesh | Gensyn AXL (Go binary, Ed25519, Yggdrasil + gVisor) |
| AI inference | 0G Compute Sealed Inference (GLM-5, Intel TDX + H100) |
| Storage | 0G Storage (Merkle-root content addressing) |
| Execution | KeeperHub (MCP server + CLI) |
| Payments | x402 V2 sessions on Base Sepolia |
| Dashboard | Next.js 15, Tailwind, shadcn/ui |

---

## How It Works

```
                        0G Chain
           +--------------------------------+
           |  Guardian.sol  VulnerableLP    |
           |  AgentINFT (ERC-7857)          |
           +--------------------------------+
                  ^                ^
                  | pause tx       | target
                  | (KeeperHub)    | of exploit
                  |                |
           +------+------+         |
           | Aggregator  |<--quorum|
           | (per node)  |         |
           +-------------+         |
                  ^                |
          findings | gossip        |
                  |                |
          +-------+--------+ AXL mesh
          |  Node A        |<----->|  Node B  |
          |  Analyzer 1    |       |  Analyzer 2 |
          |  0G Compute    |       |  0G Compute |
          +----------------+       +-------------+
                  |                      |
                  v                      v
         TEE-signed summaries (0G Sealed Inference)
                  |
                  v
         Agent manifests + reputation (0G Storage)

         Post-rescue bounty splits via x402
```

For the full architecture, see [`specs/architecture.md`](./specs/architecture.md).

---

## Rescue Flow

1. Attacker submits an oracle-manipulation transaction.
2. An analyzer on Node A detects the anomaly, requests a signed summary from 0G Compute Sealed Inference, and broadcasts a signed `Finding` over AXL.
3. An analyzer on Node B independently detects the companion reentrancy pattern and broadcasts its own `Finding`.
4. Both aggregators collect signed findings, verify TEE attestations, and count toward quorum. Three-of-N signatures on the same finding hash trigger action.
5. The aggregator invokes a KeeperHub workflow. The workflow verifies quorum onchain, submits the pause transaction via private routing, and optionally follows with `sweepToRecovery` on multi-block exploits.
6. The dashboard renders a replay: the attacker's drain transaction fails because the pool is paused. Without Klaxon it would have drained.
7. Bounty splits pay each participating agent via x402.

---

## Honest TEE Scope

0G Compute Sealed Inference is a TEE-attested LLM inference service. It is not an arbitrary-workload TEE. Klaxon analyzers run off-TEE on the agent node. Findings are summarized by an LLM call through 0G Compute, which signs the summary inside the enclave. The attestation proves that the finding was summarized by a specific model inside a TEE. It does not prove that the raw detection was performed inside a TEE.

The analyzer code hash is committed in the iNFT manifest, so operators can verify the binary matches what the agent claims to run. Moving detection itself into a 0G Compute provider model is post-hackathon work.

---

## Running Locally

Status: scaffolding only as of Day 2. Full walkthrough lands Day 8 once the end-to-end demo is reproducible.

### Prerequisites
- Node.js 20+
- Python 3.10+
- Go 1.25.5+ (for building AXL from source)
- Foundry (forge, cast, anvil)

### Install
```bash
git clone https://github.com/ajanaku1/klaxon.git
cd klaxon

# Build AXL binary
git clone https://github.com/gensyn-ai/axl /tmp/axl-src
(cd /tmp/axl-src && make build)
cp /tmp/axl-src/node axl/bin/node

# Generate agent keypairs
cd axl
openssl genpkey -algorithm ed25519 -out node-a-private.pem
openssl genpkey -algorithm ed25519 -out node-b-private.pem
openssl genpkey -algorithm ed25519 -out node-c-private.pem
```

### Run AXL nodes
```bash
cd axl
./bin/node -config node-a-config.json   # terminal 1
./bin/node -config node-b-config.json   # terminal 2
./bin/node -config node-c-config.json   # terminal 3
```

Environment configuration template: [`.env.example`](./.env.example). Copy to `.env` and fill in deployer key, 0G Compute API key, KeeperHub API key, x402 facilitator, and 3 agent keys.

---

## Project Structure

```
klaxon/
├── contracts/       # Foundry: Guardian, VulnerableLendingPool, AgentINFT
├── agents/          # Python: analyzers, AXL client, aggregator, KeeperHub + x402 integrations
├── dashboard/       # Next.js: topology graph, finding feed, rescue replay, bounty ticker
├── axl/             # AXL node configs and run scripts (binary in bin/, keys gitignored)
├── specs/           # Architecture and prompt artifacts (spec-driven dev)
├── docs/submissions # Per-prize submission write-ups
├── PLAN.md          # 9-day build plan with resume block
├── AI_USAGE.md      # AI tool attribution (ETHGlobal requirement)
├── FEEDBACK.md      # KeeperHub Builder Feedback Bounty submission
└── .env.example     # Integration keys template
```

---

## License

[MIT](LICENSE)
