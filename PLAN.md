# Klaxon — 9-Day Build Plan

**Event**: ETHGlobal Open Agents (Apr 24 – May 3, 2026)
**Submission deadline**: Sun May 3, 12:00 pm EDT
**Build start**: Sat Apr 25 (Day 2)
**Team**: solo
**Pitch (arena-framed, mechanically a pause oracle)**: agent arena for DeFi exploit detection — bonded analyzer iNFTs compete to spot exploits, TEE-verify, and trigger protocol pauses on 3-of-N quorum. Winners earn bounty splits; false positives get slashed.
**Prize targets (3-cap)**: 0G Track B ($7.5k) + Gensyn AXL ($5k) + KeeperHub ($4.5k + $500)

---

## Resume point

> **Current day**: Day 4 (Mon Apr 27) — AXL transport layer up, signer/analyzer next
> **Last completed**: Day 3 deploy on 0G Galileo (chainId 16602) — Guardian `0xeF93...6691`, Pool `0x51A3...A18c`, Oracle `0xD0F9...22A9`, AgentINFT `0x5312...9353`, kCOL `0x2A24...Faa8D`, kDBT `0x8620...300D`; multi-block exploit reproduced on chain (50_000 kDBT drained). Day 4: all three AXL nodes (A/B/C on 9002/9012/9022) running locally; `agents/axl_client.py` + `smoke_test_axl.py` verified A → {B, C} signed broadcast over the Yggdrasil mesh; `axl/agent-roster.json` maps ETH→AXL pubkeys for the swarm.
> **Day 2 config bugs found + fixed in Day 4**: (1) all three node configs used PascalCase `APIPort` which Go's JSON decoder silently ignored — switched to snake_case `api_port`; (2) `axl/README.md` broadcast pattern iterated `/topology["peers"]` which is *direct TCP links only* (Gensyn bootstrap nodes in our setup), not other swarm agents — replaced with roster-based broadcast; (3) `X-From-Peer-Id` from `/recv` is Yggdrasil-IPv6-derived form (~14-byte pubkey prefix + 0x7fff... padding), not the full Ed25519 key — added prefix matching in `AxlClient.pubkey_to_agent_id`. AXL `tcp_port` is a gVisor netstack port (per-node userspace), so all 3 nodes default to 7000 even on one host without colliding.
> **Decision (Day 3 noon)**: Agent finding signatures = **secp256k1 / ecrecover**. Reasons: 0G Chain is EVM, ecrecover is native; Ed25519 needs a non-standard precompile; agents already hold ETH keys for x402 payouts. AXL transport keys remain Ed25519 — separate concern.
> **Gas note**: 0G Galileo enforces a 2 gwei priority fee minimum. Deploy/attacker scripts that hit "transaction gas price below minimum" need `--priority-gas-price 2gwei`.
> **Next action**: Finish Day 4 — write `agents/finding.py` (Pydantic Finding + canonical hash + ETH-prefixed personal_sign matching Guardian.verifyQuorum), reentrancy analyzer 1 (ingests `debug_traceTransaction`), per-node aggregator (collects 3 sigs on same hash → submits `Guardian.pause(sigs, hash, 0x0)` via RPC). Hard gate: re-run attacker → analyzer detects → finding gossips → quorum → on-chain pause → drain reverts.
> **Blockers**: USER tasks status — KeeperHub registered ✓, Gensyn Discord joined ✓, 0G Chain funded ✓, Base Sepolia funded for 3 agents ✓. Still pending: fund deployer on Base Sepolia for x402 settlement, deposit 3 OG to a 0G Compute provider on Day 5, reserve domain + X handle.

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
