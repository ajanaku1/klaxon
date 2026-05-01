# Klaxon: An agent arena for DeFi exploit detection

Bonded analyzer iNFTs compete to spot exploits in real time. Each finding is cross-verified inside a TEE, gossiped peer-to-peer, and once three independent agents agree, the protocol pauses automatically. Winners earn bounty splits. False positives get slashed.

[![Solidity](https://img.shields.io/badge/Solidity-0.8-363636?logo=solidity)](https://soliditylang.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*"When one finds it, a thousand answer."*

Built for [ETHGlobal Open Agents](https://ethglobal.com/events/openagents) (April 24 to May 3, 2026).

---

## Status

Submission build for ETHGlobal Open Agents (deadline 2026-05-03). End-to-end rescue verified live on Base Sepolia + 0G Galileo. See [`PLAN.md`](./PLAN.md) for the day-by-day build plan and per-prize submission write-ups in [`docs/submissions/`](./docs/submissions/).

### Deployed contracts (0G Chain Galileo testnet, chainId 16602)

### Active deploy: Base Sepolia (chainId 84532)

The Guardian, Pool, Oracle, and demo ERC-20s moved to Base Sepolia on Day 6 because KeeperHub does not list 0G Galileo in its chain catalog. AgentINFT remains on 0G Chain (Day 7).

| Contract | Address |
|---|---|
| `Guardian` | [`0xD9d5E92393A6E5D238d3e7f35F384BdbaCdC785b`](https://sepolia.basescan.org/address/0xD9d5E92393A6E5D238d3e7f35F384BdbaCdC785b) |
| `VulnerableLendingPool` | [`0x923dEF178E5C058af9cd795c6bf76A76ceb9Fb45`](https://sepolia.basescan.org/address/0x923dEF178E5C058af9cd795c6bf76A76ceb9Fb45) |
| `ManipulableOracle` | [`0xC8470BDDF0038eCde3A9FB4E79B41AEf71f4D1f0`](https://sepolia.basescan.org/address/0xC8470BDDF0038eCde3A9FB4E79B41AEf71f4D1f0) |
| Demo collateral (kCOL) | [`0x01282bdE26e1d338aEA37a47204848e7413B4182`](https://sepolia.basescan.org/address/0x01282bdE26e1d338aEA37a47204848e7413B4182) |
| Demo debt asset (kDBT) | [`0x02F7eBb00DcdEB6bbF3D8a749C9E168006C47834`](https://sepolia.basescan.org/address/0x02F7eBb00DcdEB6bbF3D8a749C9E168006C47834) |

### Historical deploys (0G Galileo, chainId 16602)

Day 3 through Day 5 ran on 0G Chain. The Day 5 deploy at Guardian `0xca9F97...491B` is preserved on chain for the AInfluencer-style on-chain attestation trail (`FindingAttested(0x968c9487..., 0xa2d17599...)` on tx [`0x5f6db174`](https://chainscan-galileo.0g.ai/tx/0x5f6db17485f3e32dfb4beac855effc25bc6d71e32977d8b3c53db9920b148030)). The AgentINFT contract at [`0xdfcE8Bc5...3B17`](https://chainscan-galileo.0g.ai/address/0xdfcE8Bc5F90b5784Bd0320574e644c5427153B17) on 0G Galileo is what Day 7 will mint into.

**Day 3 hard gate cleared (2026-04-26)**: attacker bumped the oracle 1000× in block N, then drained 50,000 kDBT from the pool in block N+1 — exactly the detection window the swarm has to close. (Day 3 set deployed at `0xeF93...6691` etc; redeployed Day 5 to clear paused state for the TEE-attested rerun.)

**Day 4 hard gate cleared (2026-04-26)**: three independent Python agents on three AXL nodes detected an oracle bump, signed `Finding`s with their secp256k1 keys, gossiped over the Yggdrasil mesh, formed 3-of-N quorum, and raced to submit `Guardian.pause`. One won, two reverted with `AlreadyProcessed`. Subsequent attacker `drain()` reverted with `IsPaused()`.

**Day 5 hard gate cleared (2026-04-26)**: same flow but every `Finding` carries a real TEE attestation envelope from 0G Compute Sealed Inference (qwen-2.5-7b-instruct on a dstack-attested provider). Receivers gate quorum on local enclave-signature verification, no provider round-trip. The on-chain `FindingAttested` event now commits to a real `keccak256(tee_text)` instead of the Day-4 placeholder zero. Winning tx: [`0x5f6db174...`](https://chainscan-galileo.0g.ai/tx/0x5f6db17485f3e32dfb4beac855effc25bc6d71e32977d8b3c53db9920b148030).

**Day 6 hard gate cleared (2026-04-26)**: pause now flows through KeeperHub. Each agent submits a workflow execution via the KeeperHub MCP `execute_workflow` tool; KeeperHub's relayer wallet (`0xc90e35...fa84`) signs and submits `Guardian.pause` on Base Sepolia. Agent C won the race; A and B reverted with `AlreadyProcessed`. Pool paused, drain blocked.

**Day 7 hard gate cleared (2026-04-30)**: shipped the `klaxon` Python CLI (Typer + Rich) — `doctor`, `agents up/down/status`, `findings`, `receipts`, `attack bump|drain|reset`. Minted three AgentINFTs on 0G Galileo at [`0xdfcE8Bc5...3B17`](https://chainscan-galileo.0g.ai/address/0xdfcE8Bc5F90b5784Bd0320574e644c5427153B17), each `tokenURI` updated with the keccak256 root of its canonical signed manifest (manifests committed to [`/manifests`](./manifests/)). Single-file [`demo.html`](./demo.html) rescue replay built for video capture.

**Day 8 integration test (2026-05-01)**: re-ran the full pipeline on freshly-deployed contracts. Cycles 1 and 2 passed clean (~64 s detect→quorum→pause). Cycle 3 surfaced real degradation in the dstack TEE provider, documented in [`FEEDBACK.md`](./FEEDBACK.md) Part 2 Issue 4 along with the surgical fixes shipped (bridge-level retry on socket hang-ups, per-agent stagger on TEE calls).

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
| Contracts | Solidity 0.8, Foundry, Base Sepolia (Guardian/Pool/Oracle) + 0G Galileo (AgentINFT) |
| Agent runtime | Python 3.10, Pydantic, `web3.py`, `eth-account` |
| P2P mesh | Gensyn AXL (Go binary, Ed25519, Yggdrasil + gVisor) |
| TEE inference | 0G Compute Sealed Inference (Qwen 2.5 7B on dstack-attested provider) |
| Agent identity | 0G Storage manifests committed by hash to ERC-7857 iNFT `tokenURI` |
| Execution | KeeperHub workflow (private routing, race-safe) |
| Operator UX | `klaxon` CLI (Typer + Rich), single-file `demo.html` rescue replay |
| Payments (planned) | x402 V2 sessions on Base Sepolia for bounty splits |

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

Klaxon is operated as a CLI. After install, the entire flow is six commands.

### Prerequisites
- Python 3.10+ (for the agent runtime + CLI)
- Node.js 20–22 (for the 0G Compute bridge — Node 25 is currently incompatible with the 0G TS SDK chain, see `FEEDBACK.md` Part 2 Issue 5)
- Go 1.25+ (only if building AXL from source; binary is committed to `axl/bin/`)
- Foundry (`forge`, `cast`)

### Install
```bash
git clone <repo-url> klaxon
cd klaxon

python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 0G Compute bridge (TypeScript, sub-processed by Python)
(cd og-compute && npm install)

cp .env.example .env  # fill in deployer key, 3 agent keys, RPC URLs, KeeperHub API key
```

### Run a rescue end-to-end
```bash
klaxon doctor                      # 28 preflight checks across env, balances, deploys, providers
klaxon attack reset                # fresh Guardian/Pool/Oracle deploy on the active chain
klaxon agents up                   # boot 3 AXL daemons + 3 agent processes in the background
klaxon attack bump --price 1e22    # trigger the oracle manipulation tx
klaxon findings                    # tail signed Findings as agents detect, attest, and gossip
klaxon receipts                    # show every Guardian.FindingAttested + Paused on-chain
klaxon agents down                 # stop everything
```

The historical Day-6 rescue is on chain at `klaxon receipts --chain base-sepolia` (block 40,727,373, finding `0x622e2a05…`).

For video-quality replays without on-chain dependence, open `demo.html` in any browser and click *Run rescue*.

---

## Project Structure

```
klaxon/
├── contracts/       # Foundry: Guardian, VulnerableLendingPool, ManipulableOracle, AgentINFT
├── agents/          # Python: analyzers, AXL client, aggregator, KeeperHub + 0G Compute clients
├── klaxon/          # `klaxon` CLI (Typer + Rich) — entry point for the whole flow
├── og-compute/      # TypeScript bridge to 0G Compute Sealed Inference (sub-processed by Python)
├── og-storage/      # 0G Storage upload helpers (manifests committed by hash)
├── manifests/       # Canonical signed agent manifests committed to iNFT tokenURIs
├── keeperhub/       # KeeperHub workflow definitions + helper scripts
├── axl/             # AXL node configs (binary in bin/, .pem keys gitignored)
├── demo.html        # Single-file rescue replay for video capture
├── docs/submissions # Per-prize submission write-ups (0G, Gensyn AXL, KeeperHub)
├── specs/           # Architecture artifacts
├── PLAN.md          # 9-day build plan with resume block
├── AI_USAGE.md      # AI tool attribution (ETHGlobal requirement)
├── FEEDBACK.md      # KeeperHub Builder Feedback + 0G Compute SDK feedback
└── .env.example     # Integration keys template
```

---

## License

[MIT](LICENSE)
