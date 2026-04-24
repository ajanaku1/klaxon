# Klaxon Architecture

**Status**: Day 2 spec. Living document — update as components land.

## One-sentence description

A decentralized pause oracle for DeFi: independently-operated AI analyzer agents watch a protocol's contracts, emit signed findings over a P2P mesh, summarize each finding inside a TEE, and — once economic quorum is reached — trigger a Guardian contract's `pause()` via a reliability-guaranteed execution layer.

## System diagram (ASCII)

```
          ┌────────────────────────── 0G Chain ──────────────────────────┐
          │                                                               │
          │   ┌──────────────┐   ┌──────────────────────┐   ┌──────────┐ │
          │   │ Guardian.sol │   │VulnerableLendingPool │   │AgentINFT │ │
          │   │  pause()     │   │  (demo target)        │   │ (ERC-7857)│ │
          │   │  sweep()     │   │                       │   │           │ │
          │   │  quorum      │   └──────────────────────┘   └──────────┘ │
          │   └──────┬───────┘              ▲                     ▲      │
          └──────────┼──────────────────────┼─────────────────────┼──────┘
                     │ tx via KeeperHub     │ target of exploit   │ metadata
                     │                      │                     │ → 0G Storage
       ┌─────────────▼────────────┐         │                     │
       │      KeeperHub           │         │                     │
       │  (private routing,       │         │                     │
       │   retry, gas mgmt)       │         │                     │
       └─────────────▲────────────┘         │                     │
                     │                      │                     │
                     │ execute pause/sweep  │                     │
                     │                      │                     │
       ┌─────────────┴───────────────┐      │                     │
       │      Aggregator (quorum)    │      │                     │
       │      — on every agent node  │      │                     │
       └─────────────▲───────────────┘      │                     │
                     │ 3-of-N signed findings                     │
                     │                                            │
            ┌────────┴────────────────── AXL mesh ────────────────┴──┐
            │ (Yggdrasil + gVisor, Ed25519 per-node, localhost:9002)  │
            │                                                          │
            │    ┌────── Node A ──────┐        ┌────── Node B ──────┐ │
            │    │ Analyzer 1 (reent) │◀──────▶│ Analyzer 2 (oracle)│ │
            │    │ 0G Compute client  │  gossip│ 0G Compute client  │ │
            │    │ Aggregator         │        │ Aggregator         │ │
            │    └────────┬───────────┘        └────────┬───────────┘ │
            │             │                             │             │
            └─────────────┼─────────────────────────────┼─────────────┘
                          │ TEE-signed summaries        │
                          ▼                             ▼
                 ┌──────────────────── 0G Compute ────────────────────┐
                 │ Sealed Inference (Intel TDX + H100, GLM-5)         │
                 │ signs finding summary inside enclave               │
                 └─────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────▼──────────────────┐
                    │        0G Storage                  │
                    │ agent manifests + reputation logs  │
                    │ (Merkle root hashes → iNFT URI)    │
                    └────────────────────────────────────┘

                    ┌────────────────────────────────────┐
                    │   x402 (Base Sepolia)              │
                    │ post-rescue bounty splits          │
                    │ V2 session: 1 session, N payments  │
                    └────────────────────────────────────┘
```

## Components

### Contracts (on 0G Chain)

1. **`Guardian.sol`** — per-protocol guardian deployed by each subscribing protocol.
   - `pause()` — protocol-specific pause; only callable when quorum signatures verify against trusted agent set.
   - `sweepToRecovery(address recoveryVault)` — move protocol-owned funds to a preset recovery vault (protocol's own, never Klaxon's).
   - `verifyQuorum(bytes32 findingHash, bytes[] sigs)` — N-of-M signature verification. **Ed25519 if 0G Chain has the precompile, else secp256k1 via `ecrecover` (decision Day 3 noon).**
   - `revokeAuthorization()` — owner-only kill switch; protocol can disavow Klaxon in one tx.

2. **`VulnerableLendingPool.sol`** — demo target. A plausible-looking mini lending pool with:
   - Deposit / borrow / repay / liquidate
   - An oracle-dependent liquidation threshold
   - A reentrant withdraw path
   - The exploit requires **≥2 txs**: manipulate the oracle in block N, drain in block N+1. This creates a real pause window.

3. **`AgentINFT.sol`** (ERC-7857) — mints each agent as an iNFT.
   - `tokenURI` returns a 0G Storage root hash
   - Storage manifest JSON: `{ agentId, pubkey, analyzerCodeHash, reputation: { rescues, falsePositives } }`
   - Mint-only for MVP. No breeding / merging / upgrading (kept for post-hackathon).

### Agent nodes (Python)

Two independent AXL nodes, each running:

- **Analyzer 1** — reentrancy detector. Subscribes to pending + mined tx stream, pattern-matches reentrancy sigs in tx traces (`debug_traceTransaction`), emits `Finding { txHash, type, severity, evidence }`.
- **Analyzer 2** — oracle manipulation detector. Watches pending txs that move oracle-dependent prices by >X% per block.
- **0G Compute client** — for each Finding, calls Sealed Inference with a summarization prompt. Receives `{ summary, tee_signature, enclave_quote }`.
- **AXL client** (`axl_client.py`) — signs Finding+summary with agent key, `broadcast()` via `/topology` + `/send` fan-out.
- **Aggregator** — listens on `/recv`, deduplicates findings by hash, verifies enclave signatures on inbound, counts toward quorum. On 3-of-N quorum: invokes KeeperHub workflow.

### AXL nodes

Two separate AXL Go binaries (different VMs or at minimum different ports). Each has:
- Ed25519 keypair in `axl/node-{a,b}.pem`
- Node config in `axl/node-{a,b}-config.json`
- Peered to each other via AXL's Yggdrasil overlay

### KeeperHub workflow

Single workflow invoked by the aggregator on quorum:
1. Verify quorum signatures onchain against Guardian.
2. Submit `pause()` tx with private routing + retry.
3. Optional: follow with `sweepToRecovery()` if the exploit is multi-block and protocol config allows.
4. On success: trigger x402 bounty split.

### x402 bounty splits

After successful pause, the aggregator (or Guardian-linked escrow) sends x402 payments to each participating agent's wallet. Using **x402 V2 session** so 3 splits reuse one session setup, not three.

## Data flow (rescue scenario)

1. Attacker submits oracle-manipulation tx (block N).
2. Analyzer 2 on Node A detects, calls 0G Compute for signed summary, broadcasts `Finding_1` over AXL.
3. Analyzer 1 on Node B sees the related reentrancy pattern in the follow-up tx, broadcasts `Finding_2`.
4. Both aggregators see both findings. Quorum: need 3-of-N sigs on the same `findingHash`. For demo, we'll have 3 agent keys signing the aggregated finding.
5. Aggregator invokes KeeperHub workflow → pause tx lands on 0G Chain → VulnerableLendingPool is paused **before block N+1 exploit lands**.
6. Dashboard renders the replay: attacker's drain tx fails (pool paused); without Klaxon, it would have drained.
7. x402 bounty splits paid to 3 agent wallets.

## Non-goals (for hackathon MVP)

- Agent bond / slashing mechanics in code (pitch deck only)
- Honeypot traps
- 48h challenge window enforcement
- Live global swarm map with real heartbeats (we fake a 3-node topology graph)
- ENS integration (no capacity — 3-prize cap)
- Uniswap API integration (doesn't fit the model)

## Honest scope notes

- **TEE attestation**: signs the LLM summary of a finding, not the raw analyzer detection. Mitigation: the analyzer code hash is committed in the iNFT manifest, so operators can verify the analyzer binary matches what the agent claims to run. True "detection-inside-TEE" is post-hackathon.
- **Quorum**: demo shows 3 keys signing. Real deployments need ~20+ independent operators for meaningful decentralization — this is a mechanism demo, not a production deployment.
- **Rescue window**: only exists for multi-block exploits. Atomic flash-loan drains finish in one block; Klaxon's pause won't land in time. This is why we lead with "pause oracle" (prevents the next exploit) rather than "rescue race" (physics-limited).

## Open decisions

- **Signature scheme** (Ed25519 vs secp256k1 for agent keys) — Day 3 noon based on 0G Chain precompile availability.
- **Domain + X handle** — reserve by end of Day 3.
- **Logomark** — commission or generate for video slide 1 (Day 9).
