# Klaxon — 9-Day Build Plan

**Event**: ETHGlobal Open Agents (Apr 24 – May 3, 2026)
**Submission deadline**: Sun May 3, 12:00 pm EDT
**Build start**: Sat Apr 25 (Day 2)
**Team**: solo
**Pitch (arena-framed, mechanically a pause oracle)**: agent arena for DeFi exploit detection — bonded analyzer iNFTs compete to spot exploits, TEE-verify, and trigger protocol pauses on 3-of-N quorum. Winners earn bounty splits; false positives get slashed.
**Prize targets (3-cap)**: 0G Track B ($7.5k) + Gensyn AXL ($5k) + KeeperHub ($4.5k + $500)

---

## Resume point

> **Current day**: End of Day 4 (Mon Apr 27) — full detect→gossip→quorum→pause loop working on testnet
> **Last completed**: Day 4 hard gate cleared at 13:13 UTC. Three agent processes (A/B/C) tail the chain, detect oracle manipulation via `PriceBumped` events, sign Findings with secp256k1, gossip over the AXL Yggdrasil mesh, aggregate to 3-of-N quorum, and race to submit `Guardian.pause`. Verified live: bump 5e21→5e22 → all 3 detected ratio=10x → quorum on hash `0x742afdba...` → agent A won the on-chain race (tx `0x28b2370...`, block 29923397), B/C reverted with `AlreadyProcessed`. `Pool.paused()=true`, subsequent attacker `drain()` reverts with `IsPaused()`. Python signing path verified contract-correct against the live Guardian via `test_guardian_integration.py` (3 sigs → quorum=true; deployer-substituted → false).
> **New funding done in Day 4**: deployer sent 0.5 OG to each of the 3 agent addresses on 0G Galileo (txs `0xff9f...`, `0x3d4c...`, `0xacbc...`). Without this, `Guardian.pause` reverts with "insufficient funds" — agents need testnet gas on the chain they pause, not just on Base Sepolia.
> **Day 4 also wrote** (29 unit tests passing, all green): `agents/finding.py` (Pydantic Finding + ETH-prefixed personal_sign), `analyzer_oracle.py`, `aggregator.py`, `agent.py` runtime (3 threads: scan/listen/fire), `run_agent.py` CLI. Pivoted analyzer 1 from "reentrancy" to "oracle-manipulation" since that matches the demo exploit; reentrancy moves to Day 5 as analyzer 2.
> **Cumulative gotchas logged**: PascalCase `APIPort` ignored by AXL config (use `api_port`); `/topology["peers"]` is direct TCP links only, broadcast must iterate a swarm roster instead; `X-From-Peer-Id` is Yggdrasil-IPv6-derived (14-byte prefix), needs prefix matching; `tcp_port` 7000 is gVisor-internal so all nodes can share it on one host; 0G Galileo enforces 2 gwei priority-fee minimum (use `--priority-gas-price 2gwei` and `--with-gas-price 5gwei` when forge complains).
> **Decision (Day 3 noon)**: Agent finding signatures = **secp256k1 / ecrecover**. Reasons: 0G Chain is EVM, ecrecover is native; Ed25519 needs a non-standard precompile; agents already hold ETH keys for x402 payouts. AXL transport keys remain Ed25519 — separate concern.
> **Next action**: Day 5 — analyzer 2 (reentrancy detector via `debug_traceTransaction`), wire `og-compute/` helpers into the agent runtime (Python → Node subprocess) so each Finding carries a real `tee_attestation_hash`, fix `processResponse` "getting signature error" so receiver-side enclave verification can gate quorum.
> **Day 5 prep done**: 0G Compute is set up. `og-compute/` (Node helper) deposited 3 OG to the broker ledger (tx `0xebf942a4...`), listed 2 providers on Galileo, acknowledged the chatbot provider `0xa48f01287233509FD694a22Bf840225062E67836` (qwen/qwen-2.5-7b-instruct, dstack TEE verifier), and ran a smoke test that returned a coherent finding summary. Model swap: plan targeted GLM-5; only Qwen 2.5-7B was in the provider catalog — README needs to note this.
> **Blockers**: USER tasks status — KeeperHub registered ✓, Gensyn Discord joined ✓, 0G Chain funded ✓ (deployer + 3 agents), 3 OG deposited to 0G Compute provider ✓, Base Sepolia funded for 3 agents ✓. Still pending: fund deployer on Base Sepolia for x402 settlement (Day 6), reserve domain + X handle.

Update this block every time you pause/resume so a fresh Claude session can pick up without re-deriving context.

---

## Day 2 — Sat Apr 25 — Scaffolding + accounts

**Objective**: everything that's not code, done. Unblock all external dependencies before they bite you mid-week.

- [ ] Init repo `/Users/mac/Vibecoding/klaxon`, commit empty scaffold (Next.js dashboard + Hardhat/Foundry contracts + Python agents in monorepo layout)
- [ ] Create `README.md` (stub), `AI_USAGE.md` (stub), `FEEDBACK.md` (empty, start logging as you go)
- [x] Sign up at KeeperHub (`app.keeperhub.com`)
- [x] Join Gensyn Discord for AXL support
- [x] Fund deployer wallet on 0G Chain testnet via faucet
- [ ] Deposit 3 OG to a 0G Compute provider via broker SDK (Day 5 — not blocking until then)
- [ ] Fund deployer + 3 agent wallets on Base Sepolia for x402 payments
- [ ] Clone + build AXL Go binary locally (`github.com/gensyn-ai/axl`), run one node successfully, generate Ed25519 key
- [ ] Skim `collaborative-autoresearch-demo` repo — reference for how AXL nodes talk
- [ ] Write `specs/architecture.md` (1-pager with 3 contracts, 2 agents, 2 AXL nodes, data flow arrows) — commit as spec artifact
- [ ] Pick domain + X handle, reserve both
- [ ] First commit to GitHub, public repo

**Done when**: AXL node runs on localhost:9002, testnet wallets funded, accounts created, spec pushed.

**Risk**: 0G testnet faucet throttle or KeeperHub signup delay — hit these first so you know overnight if there's a blocker.

---

## Day 3 — Sun Apr 26 — Contracts

**Objective**: all Solidity done and deployed on 0G Chain testnet.

- [x] `Guardian.sol`: `pause()`, `sweepToRecovery(address)`, `verifyQuorum(bytes[] sigs, bytes32 findingHash)` (3-of-N signature verify), `revokeAuthorization()` owner kill switch, **`FindingAttested(bytes32 findingHash, bytes32 teeAttestationHash)` event emitted on every quorum-passing finding** (on-chain attestation trail — AInfluencer's 1st-place narrative hook applied to security)
- [x] `VulnerableLendingPool.sol`: deposit/borrow/liquidate with intentionally exploitable oracle dependency + reentrant withdraw. Exploit must take ≥2 txs (oracle manipulation block N, drain block N+1) so the pause window is real
- [x] `AgentINFT.sol` (ERC-7857): mint-only, `tokenURI` returns a 0G Storage root hash pointing to manifest JSON
- [x] Deploy all six contracts to 0G Chain testnet, record addresses in `README.md` (Galileo chainId 16602; see deployments/16602.json)
- [x] Write attacker script (`script/Attacker.s.sol`, `deposit/bump/drain` sigs) — broadcast on testnet, drained 50_000 kDBT confirmed onchain
- [x] Forge test suite: quorum, replay, dedupe, unauthorized signer, exploit reproducibility (11/11 passing)
- [ ] Commit with clear messages

**Done when**: attacker script drains VulnerableLendingPool on testnet in a reproducible sequence, Guardian deployed, iNFT mint works from cast/foundry.

**Risk**: Ed25519 signature recovery in Solidity needs a precompile or library. If 0G Chain doesn't support it, switch agent signatures to secp256k1 (`ecrecover`) — agents sign with ETH keys instead. **Decide by Day 3 noon.** → ✓ Decided: secp256k1. Same key reused for x402.

---

## Day 4 — Mon Apr 27 — AXL gossip + first analyzer

**Objective**: two agent processes talking across two AXL nodes, emitting signed findings.

- [x] Stand up AXL node 2 (3 nodes A/B/C running locally on 9002/9012/9022 — single-host since AXL `tcp_port` is gVisor-internal)
- [x] Python helper `axl_client.py`: `broadcast(payload)` iterates the swarm roster (`agent-roster.json`), POSTs signed payload to each peer via `/send`; `listen()` polls `/recv` (single-poll: 200/204)
- [x] Test: `smoke_test_axl.py` — A broadcasts, B and C both receive with correct sender attribution. Verified on the live Yggdrasil mesh.
- [x] **Analyzer 1 — oracle-manipulation detector** (Python). Subscribes to ManipulableOracle.PriceBumped events, fires on `newPrice >= oldPrice * 5`. Output: signed `Finding{ chainId, pool, type, severity, txHash, blockNumber, evidence }`. Pivoted from "reentrancy" since it matches the demo exploit; reentrancy moves to Day 5 as analyzer 2.
- [x] Per-node aggregator: collects 3-of-N findings keyed by findingHash, validates each signature recovers to the claimed `agent_address` AND that signer is in the authorized set. On quorum → calls Guardian.pause directly via web3.py (KeeperHub swap-in is Day 6).
- [ ] **Analyzer 1** — reentrancy detector (Python). Input: tx trace JSON from `debug_traceTransaction`. Output: `Finding { txHash, type, severity, evidence }`. Signed, broadcast via AXL.
- [ ] Aggregator stub on each node: collects findings, when 3-of-N same-hash findings seen → calls Guardian `pause()` (direct RPC for now)

**Done when**: attacker script runs → analyzer 1 on node A detects → finding gossips to node B → aggregator sees quorum and emits pause call. ✓ (2026-04-26 13:13 UTC) — three agents detected oracle bump 5e21→5e22 (10x), reached quorum on hash `0x742afdba...`, agent A's `Guardian.pause` won the race onchain (tx `0x28b2370...`, status=1, block 29923397), B and C reverted with `AlreadyProcessed` as designed. `Pool.paused()` flipped true. Subsequent attacker `drain()` reverts with `IsPaused()`.

**Risk**: AXL `/recv` may need long-poll rather than single poll — check `collaborative-autoresearch-demo` first. Resolved: `/recv` is a single-poll (200 + body / 204 empty). 0.1s poll loop in `AxlClient.listen()` is plenty.

---

## Day 5 — Tue Apr 28 — Analyzer 2 + 0G Compute attestation

**Objective**: second analyzer + TEE-signed summaries through 0G Compute.

- [ ] **Analyzer 2** — oracle-manipulation detector. Watches pending txs that move oracle-dependent prices by >X% in one block.
- [ ] 0G Compute integration: for each Finding, send to 0G Sealed Inference (GLM-5) with prompt *"Summarize this exploit finding in one sentence for a human operator."* Capture signed response.
- [ ] Attach `{ summary, tee_signature, enclave_quote }` to Finding before gossip
- [ ] Verify enclave signature on receiving node before counting toward quorum
- [ ] Update README with honest TEE scope note: *"TEE signs the LLM summary, not the raw detection."*
- [ ] **Stretch goal (only if Day 5 ends with slack)**: dynamic reputation rolls on iNFT manifest — after a successful aggregated finding, update Storage root + push new `tokenURI` to the AgentINFT contract. Visible "persistent memory + dynamic upgrades" per the 0G iNFT track text. Skip if behind.

**Done when**: end-to-end flow: attack tx → analyzer detects → 0G Compute summarizes → signed finding gossips across AXL → quorum verified → pause call emitted.

**Risk**: 0G Compute latency/rate limits. If Sealed Inference is slow (>5s), note it in README but doesn't break the design.

---

## Day 6 — Wed Apr 29 — KeeperHub + x402

**Objective**: real execution layer + real payments.

- [ ] KeeperHub integration: replace direct RPC `pause()` with a KeeperHub workflow call. Use MCP server from one of the agents.
- [ ] Workflow: (1) verify quorum onchain, (2) submit pause tx via private routing, (3) if multi-block exploit, follow up with `sweepToRecovery` to preset vault.
- [ ] x402 bounty split: after successful pause, each participating agent gets x402 payment from Guardian (or small escrow) for their cut. Use x402 V2 session so 3 splits = 1 session.
- [ ] Log every KeeperHub friction point in `FEEDBACK.md` — literal money ($250–$500 bonus).

**Done when**: full live chain: attacker tx → detection → 0G-attested summary → AXL gossip → quorum → KeeperHub executes pause → x402 pays 3 agents. All onchain, all visible on block explorer.

**Risk**: KeeperHub workflow complexity. If CLI/MCP is rough, bias toward CLI path (simpler) and log DX friction.

---

## Day 7 — Thu Apr 30 — iNFT + 0G Storage + dashboard shell

**Objective**: agents are iNFTs, manifests on 0G Storage, dashboard shows the flow.

- [ ] Agent manifest JSON: `{ agentId, pubkey, analyzerCodeHash, reputation: { rescues, falsePositives } }`. Upload to 0G Storage, get root hash.
- [ ] Mint 3 iNFTs on 0G Chain, one per agent, `tokenURI` = 0G Storage root hash
- [ ] Dashboard (Next.js + Tailwind + shadcn): four panels
  - Swarm topology graph (3 nodes, animated pulse on finding propagation)
  - Live finding feed (signed findings streaming in)
  - Rescue replay split-screen (what *would have* happened vs what did)
  - x402 earnings ticker
- [ ] Dashboard polls a local API that reads agent logs + onchain events

**Done when**: open dashboard in browser, trigger attacker script, watch the full flow happen live on screen.

**Risk**: dashboard eats time. Timebox 8h — if panels look rough, ship it and fix via video edit.

---

## Day 8 — Fri May 1 — Integration test + polish

**Objective**: everything works end-to-end, repeatedly, no manual intervention.

- [ ] One-command demo: `npm run demo` — spins up 2 AXL nodes, runs attacker, shows dashboard, executes pause + sweep + bounty splits
- [ ] Run it 5× in a row. Fix every flake.
- [ ] Write real `README.md`: pitch paragraph, architecture diagram (Excalidraw → SVG), setup, deployment addresses, honest TEE scope note, prize-track alignment section
- [ ] Finalize `AI_USAGE.md` with per-file attribution
- [ ] Write per-prize submission blurbs in `/docs/submissions/` — one each for 0G Track B, AXL, KeeperHub. Explain load-bearing integration.
- [ ] Finalize `FEEDBACK.md` — ≥5 specific, actionable KeeperHub items
- [ ] Dry-run the demo video recording (not final) to shake out pacing

**Done when**: repo submission-ready minus polished video. Fresh clone reproduces demo in <10 min.

---

## Day 9 — Sat May 2 — Demo video

**Objective**: 3-minute video that wins.

- [ ] Script (≤450 words): 15s problem → 30s architecture → 90s live demo → 30s differentiators → 15s CTA
- [ ] Record screen-capture of live demo, 720p min
- [ ] Voiceover with real mic, quiet room. No TTS. No music-over-text.
- [ ] Edit tight, skip waits. Max 1.2× speed.
- [ ] 4 slides max: title, architecture, key numbers, team/links
- [ ] Export 1080p, ≤4 min, ≥720p. Verify with `ffprobe` before upload.
- [ ] Fill submission form: project title, description, repo link, demo link, video. Select 3 prizes: **0G, Gensyn, KeeperHub**

**Done when**: video uploaded, submission form filled, 3 prize write-ups in, live demo link works from fresh browser.

**Risk**: upload hits 720p/length check. Export exactly 1080p, exactly ≤4:00, verify locally first.

---

## Day 10 — Sun May 3 — Final submit (noon EDT cutoff)

- [ ] Sanity check: repo public, addresses in README, AI_USAGE.md, FEEDBACK.md, spec files all committed
- [ ] Submit by 10:00 am EDT — **2-hour buffer** for upload failures
- [ ] Post to X with demo link
- [ ] Done.

---

## Dependency graph

```
Day 2 (accounts, AXL build) ──► Day 3 (contracts)
                                     │
Day 3 ──► Day 4 (AXL + analyzer 1) ──┼─► Day 5 (analyzer 2 + 0G)
                                     │            │
                            Day 6 (KeeperHub + x402) ◄─┘
                                     │
                            Day 7 (iNFT + dashboard)
                                     │
                            Day 8 (integration + docs)
                                     │
                            Day 9 (video + submit form)
                                     │
                            Day 10 (final submit)
```

## Hard gates (do not proceed if not green)

- **End of Day 2**: AXL binary runs, wallets funded
- **End of Day 3**: attacker.ts drains VulnerableLendingPool on testnet
- **End of Day 4**: 2 AXL nodes gossip a signed finding
- **End of Day 6**: full end-to-end onchain flow works at least once
- **End of Day 8**: demo runs 5× without manual intervention

**If any gate slips, cut scope immediately.** Priority to cut (in order): iNFT → second analyzer → x402 bounty splits → dashboard polish.

**Never cut**: Guardian + AXL gossip + KeeperHub execution + 0G Compute signed summaries. These are load-bearing for the 3 prize tracks.
