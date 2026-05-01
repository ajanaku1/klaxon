# Klaxon · Gensyn AXL Submission

**Track:** [Gensyn — Most innovative use of AXL]

**Project:** Klaxon — an agent arena for DeFi exploit detection. Three bonded
analyzer iNFTs compete to spot exploits, cross-verify each other inside a TEE,
and trigger a protocol pause on 3-of-N quorum.

---

## Why AXL is load-bearing here

Klaxon's whole product claim — "when one finds it, a thousand answer" —
requires that *independent* agents on *different machines* hear about a
finding fast enough to vote on it before the next block. We need cross-node
signed gossip. AXL is exactly that primitive.

Three Klaxon agents run as three separate processes, each paired with its
own AXL daemon (ports `9002`, `9012`, `9022`). All three nodes form a
Yggdrasil mesh through the public Gensyn bootstrap servers. Any agent's
detection emits a signed Klaxon Signal that reaches the other two via
AXL routing — no central coordinator, no message bus we own.

## What we built on top of AXL

- `agents/axl_client.py` — thin Python client over an AXL node's HTTP
  API. `broadcast(payload)` iterates the swarm roster and `/send`s to
  each peer; `listen()` polls `/recv` (200/204).
- `axl/agent-roster.json` — the swarm map. Each agent has an Ed25519
  AXL pubkey (transport identity) and a separate secp256k1 ETH address
  (finding-signing identity, also their x402 payout address).
- `agents/finding.py` — canonical Finding object with deterministic
  serialization for signing. The `signature` is over `keccak256(canonical
  JSON)` so receivers can `ecrecover` to the claimed agent address.
- `agents/aggregator.py` — per-node aggregator that collects signed
  Findings keyed by `findingHash`, validates each signature recovers to
  an authorized signer, also re-verifies the TEE attestation, and fires
  the rescue once 3-of-N independent signers agree.

## The cross-node specialists requirement, satisfied

Gensyn AXL's framing is *cross-node specialists*: separate processes
running on separate hardware, talking to each other. Klaxon's
3-agent quorum is meaningless if all three signatures come from one
process. AXL is what makes the independence verifiable end-to-end:

- Each agent has a distinct Ed25519 transport key (`axl/node-{a,b,c}-private.pem`)
- Each agent has a distinct secp256k1 finding-signing key (in `.env` /
  `axl/agent-eth-keys.json`)
- The on-chain Guardian's `verifyQuorum` function rejects duplicate
  signers — three signatures from the same key cannot pass
- The detection event's gossip path is observable: each agent logs the
  finding hash it broadcast, the per-peer ack/error, and which agent it
  received findings from before forming quorum

## Design decisions worth noting

### Roster-based broadcast (not topology-based)

AXL exposes `/topology["peers"]` but that returns only **direct TCP
links** — for our setup that's the Gensyn bootstrap servers, not other
Klaxon agents. There is no native broadcast primitive. We solved it by
keeping a swarm roster file (`agent-roster.json`) committed to the repo
and iterating it on broadcast — Yggdrasil routes the actual delivery.

This is a small piece of glue but not obvious from docs. It's the kind
of thing a future "swarm SDK" on top of AXL could absorb.

### `/recv` is a single poll, not a long-poll

We initially expected long-polling. AXL's `/recv` returns immediately:
200 + body if a message is queued, 204 if empty. Our `listen()` loop
polls every 100ms — plenty fast for sub-second propagation.

### Two-key model for agent identity

Agents have *two* keys, deliberately, and we wrote a memory entry to
keep them straight:

- **Ed25519 (AXL transport)** — for AXL daemon TLS + signed gossip
  envelopes. Lives in `*.pem`.
- **secp256k1 (Finding signing + x402 payout)** — for the on-chain
  Guardian's `ecrecover`-based quorum check, AND the destination address
  for x402 bounty splits. Same key, unified agent identity.

We chose secp256k1 for findings because Guardian runs on EVM and
`ecrecover` is a 3000-gas precompile; verifying Ed25519 on EVM needs a
non-standard precompile that 0G Galileo doesn't support.

## Live verification

The full path was first verified live on 2026-04-26:

- Three agents on three AXL nodes (single host, single AXL `tcp_port`
  inside gVisor)
- Attacker bumps oracle price 10× via `klaxon attack bump`
- All three agents detect via independent RPC scans
- Each TEE-attests its summary via 0G Compute (`0xa48f0128...`)
- Each gossips a signed Finding via AXL — the per-agent log shows
  `broadcast: {peer_a: 'ok', peer_b: 'ok'}` confirming AXL delivery
- All three reach 3-of-N quorum and race to submit `Guardian.pause`
  via KeeperHub. First wins, others revert with `AlreadyProcessed`
  (selector `0x57eee766`). This race is *exactly* what cross-node
  agreement looks like in practice.

## Stretch / what AXL helped us avoid

We considered building a small WebSocket bus or piggy-backing on a
public Redis. Both would have required hosting and a Klaxon-controlled
trust root, undermining the "decentralized swarm" claim. AXL is the
primitive that makes the trust story honest: the swarm doesn't need
Klaxon-the-team to be online for findings to propagate.
