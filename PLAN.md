# Klaxon — 9-Day Build Plan

**Event**: ETHGlobal Open Agents (Apr 24 – May 3, 2026)
**Submission deadline**: Sun May 3, 12:00 pm EDT
**Build start**: Sat Apr 25 (Day 2)
**Team**: solo
**Pitch (arena-framed, mechanically a pause oracle)**: agent arena for DeFi exploit detection — bonded analyzer iNFTs compete to spot exploits, TEE-verify, and trigger protocol pauses on 3-of-N quorum. Winners earn bounty splits; false positives get slashed.
**Prize targets (3-cap)**: 0G Track B ($7.5k) + Gensyn AXL ($5k) + KeeperHub ($4.5k + $500)

---

## Resume point

> **Current day**: End of Day 2 (Sat Apr 25)
> **Last completed**: Repo init, monorepo scaffold, specs/architecture.md, README/AI_USAGE/FEEDBACK stubs, Foundry installed (via foundryup + libusb), Go 1.26 installed via brew, AXL binary built (`axl/bin/node`, pinned to Go 1.25.5 via AXL Makefile), 3 Ed25519 keypairs generated, 3 node configs written, AXL smoke-test passed (boots + connects to Gensyn mesh).
> **Next action**: Day 3 — init Foundry project in `contracts/`, write Guardian.sol + VulnerableLendingPool.sol + AgentINFT.sol, deploy to 0G Chain testnet. Decide Ed25519-vs-secp256k1 signature scheme by Day 3 noon.
> **Blockers**: USER tasks outstanding — KeeperHub registered (✓), 0G needs no signup (wallet-based auth via build.0g.ai/compute). Still pending: join Gensyn Discord/Telegram, fund testnet wallets on 0G Chain + Base Sepolia, deposit 3 OG to a 0G Compute provider account, reserve domain + X handle.

Update this block every time you pause/resume so a fresh Claude session can pick up without re-deriving context.

---

## Day 2 — Sat Apr 25 — Scaffolding + accounts

**Objective**: everything that's not code, done. Unblock all external dependencies before they bite you mid-week.

- [ ] Init repo `/Users/mac/Vibecoding/klaxon`, commit empty scaffold (Next.js dashboard + Hardhat/Foundry contracts + Python agents in monorepo layout)
- [ ] Create `README.md` (stub), `AI_USAGE.md` (stub), `FEEDBACK.md` (empty, start logging as you go)
- [x] Sign up at KeeperHub (`app.keeperhub.com`)
- [ ] Join Gensyn Telegram/Discord for AXL support
- [ ] Fund testnet wallet on 0G Chain testnet (faucet) and deposit 3 OG to a 0G Compute provider — wallet-based auth, no separate signup needed
- [ ] Fund testnet wallet on Base Sepolia for x402 payments
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

- [ ] `Guardian.sol`: `pause()`, `sweepToRecovery(address)`, `verifyQuorum(bytes[] sigs, bytes32 findingHash)` (3-of-N signature verify), `revokeAuthorization()` owner kill switch, **`FindingAttested(bytes32 findingHash, bytes32 teeAttestationHash)` event emitted on every quorum-passing finding** (on-chain attestation trail — AInfluencer's 1st-place narrative hook applied to security)
- [ ] `VulnerableLendingPool.sol`: deposit/borrow/liquidate with intentionally exploitable oracle dependency + reentrant withdraw. Exploit must take ≥2 txs (oracle manipulation block N, drain block N+1) so the pause window is real
- [ ] `AgentINFT.sol` (ERC-7857): mint-only, `tokenURI` returns a 0G Storage root hash pointing to manifest JSON
- [ ] Deploy all three to 0G Chain testnet, record addresses in `README.md`
- [ ] Write `attacker.ts` — Foundry/Hardhat script that executes the multi-tx exploit. Confirm it drains funds on testnet.
- [ ] Commit with clear messages

**Done when**: attacker script drains VulnerableLendingPool on testnet in a reproducible sequence, Guardian deployed, iNFT mint works from cast/foundry.

**Risk**: Ed25519 signature recovery in Solidity needs a precompile or library. If 0G Chain doesn't support it, switch agent signatures to secp256k1 (`ecrecover`) — agents sign with ETH keys instead. **Decide by Day 3 noon.**

---

## Day 4 — Mon Apr 27 — AXL gossip + first analyzer

**Objective**: two agent processes talking across two AXL nodes, emitting signed findings.

- [ ] Stand up AXL node 2 (separate VM, separate Ed25519 key, peer with node 1)
- [ ] Python helper `axl_client.py`: `broadcast(payload)` iterates `/topology`, POSTs signed payload to each peer via `/send`; `listen()` polls `/recv`
- [ ] Test: `echo` bot from node A → received on node B. Commit as `smoke_test_axl.py`
- [ ] **Analyzer 1** — reentrancy detector (Python). Input: tx trace JSON from `debug_traceTransaction`. Output: `Finding { txHash, type, severity, evidence }`. Signed, broadcast via AXL.
- [ ] Aggregator stub on each node: collects findings, when 3-of-N same-hash findings seen → calls Guardian `pause()` (direct RPC for now)

**Done when**: attacker script runs → analyzer 1 on node A detects → finding gossips to node B → aggregator sees quorum and emits pause call.

**Risk**: AXL `/recv` may need long-poll rather than single poll — check `collaborative-autoresearch-demo` first.

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
