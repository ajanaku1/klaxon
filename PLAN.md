# Klaxon — 9-Day Build Plan

**Event**: ETHGlobal Open Agents (Apr 24 – May 3, 2026)
**Submission deadline**: Sun May 3, 12:00 pm EDT
**Build start**: Sat Apr 25 (Day 2)
**Team**: solo
**Pitch (arena-framed, mechanically a pause oracle)**: agent arena for DeFi exploit detection — bonded analyzer iNFTs compete to spot exploits, TEE-verify, and trigger protocol pauses on 3-of-N quorum. Winners earn bounty splits; false positives get slashed.
**Prize targets (3-cap)**: 0G Track B ($7.5k) + Gensyn AXL ($5k) + KeeperHub ($4.5k + $500)

---

## Resume point

> **Current day**: End of Day 5 (Mon Apr 27) — TEE-attested findings gating quorum on testnet
> **Last completed**: Day 5 hard gate cleared at 14:44 UTC. Every gossiped Finding now carries a 0G Compute Sealed Inference envelope (`tee_text`, `tee_signature`, `tee_signing_address`, `tee_attestation_hash`); the aggregator gates quorum on local enclave-signature verification — receivers re-derive `recover(tee_text, tee_signature) == tee_signing_address` without hitting the provider. Verified live with bump 1e21→1e22 (10x): all 3 agents attested with signer `0x83df4b8e...` verified=true, formed quorum on hash `0x968c9487...`, raced to submit. Agent C won the race this time (tx `0x5f6db174...`, status=1, block 29935848); A and B reverted with `AlreadyProcessed`. **`FindingAttested` event now carries `0xa2d17599...`** — a real keccak256(tee_text) commitment, not the Day-4 placeholder zero. Subsequent attacker `drain()` reverts with `IsPaused()`.
> **Day 5 architecture**: Python agent ↔ Node bridge via subprocess (`agents/og_compute.py` shells out to `og-compute/summarize-finding.ts`). Bridge handles broker init, /chat/completions call, /v1/proxy/signature/<chatID>?model=... fetch, and `processResponse` verification in one round-trip; returns the full envelope JSON for Python to attach to the Finding before signing. Every recv-side check happens locally via `Finding.verify_tee_attestation()` — no inference round-trip on gossip path.
> **Day 5 SDK gotchas logged**: (1) the v0.7.5 ESM build's `lib.esm/index.mjs` re-exports under aliased names that don't exist in the chunk file — kept the og-compute package CJS as workaround. (2) `processResponse(provider, chatID, content)` arg order, NOT `(provider, content, chatID)` as I first guessed — and the chatID is the `ZG-Res-Key` response header, not the OpenAI body `id`. (3) The dstack provider rate-limits to 2 concurrent requests per user; with 3 agents attesting in parallel one always 429s — added 1.5–7s exponential backoff with jitter in the bridge; all three now eventually succeed.
> **Day 5 SCOPE CUT**: 0G Galileo does not expose `debug_traceTransaction` (-32601 "method does not exist"). Trace-based reentrancy detector for analyzer 2 is impossible without traces. Cut from Day 5; reentrancy stretch goal can be re-attempted via emitted-event heuristics on Day 8 if there's slack. Day 5's load-bearing work was TEE attestation, not analyzer count — Gensyn's "cross-node specialists" requirement is satisfied by 3 agents on 3 AXL nodes regardless of analyzer plurality.
> **Cumulative gotchas**: PascalCase `APIPort` ignored by AXL config (use `api_port`); `/topology["peers"]` is direct TCP links only — broadcast must iterate a swarm roster; `X-From-Peer-Id` is Yggdrasil-IPv6-derived (14-byte prefix), needs prefix matching; `tcp_port` 7000 is gVisor-internal so all nodes share it on one host; 0G Galileo enforces 2 gwei priority-fee minimum (use `--priority-gas-price 2gwei` and `--with-gas-price 5gwei`); 0G Galileo has NO `debug_traceTransaction`; 0G Compute provider has 2-concurrent-request cap per user (retry with backoff).
> **Decision (Day 3 noon)**: Agent finding signatures = **secp256k1 / ecrecover** (0G Chain is EVM, native ecrecover, agents already hold ETH keys for x402). AXL transport keys remain Ed25519 — separate concern.
> **Current day**: End of Day 6 (KeeperHub gate cleared) — pause now flows through KeeperHub, agent runtime no longer signs the on-chain pause directly
> **Day 6 hard gate cleared (18:04 UTC)**: agent C reached 3-of-N quorum, called `KeeperHubClient.execute(sigs, findingHash, teeHash)`, KeeperHub's relayer wallet (`0xc90e35...fa84`) submitted Guardian.pause on Base Sepolia, execution status returned `success`. Agents A and B then submitted as well; both reverted with `AlreadyProcessed` (selector `0x57eee766`) which is the expected race outcome. Pool.paused() = true, subsequent attacker drain reverts with IsPaused().
> **Day 6 KeeperHub findings (all in FEEDBACK.md, dual-audience write-up)**: 0G Galileo not in their chain catalog (forced the chain pivot), 404 page returned with HTTP 200, workflow create endpoint is `/api/workflows/create` not REST-conventional `/api/workflows`, Mustache templates `{{...}}` in `functionArgs` are not rendered before JSON.parse so we ship a per-execution PATCH workaround (`agents/keeperhub.py::_patch_static_args`), relayer wallet ships with zero gas and the dashboard does not surface the address (we found it from the failed-tx error message), node-config schemas are undocumented (we reverse-engineered via `POST /api/ai/generate`), API auth header convention not in any docs.
> **New funding done in Day 6**: deployer sent 0.0005 ETH to KeeperHub relayer `0xc90e35...fa84` on Base Sepolia (tx `0x92ed24b7...`). Without this, every workflow execution would have reverted with insufficient gas.
> **Next action**: Day 7 — iNFT mints + 0G Storage manifests, dashboard shell. Then x402 V2 bounty splits as a stretch (deferred from Day 6: would need testnet USDC funding for the deployer or escrow wallet; Klaxon escrow contract on Base Sepolia + KeeperHub second-action `web3/transfer-token` to each agent is the cleanest path, hits the x402 USDC settlement story without needing a literal HTTP-402 dance).
> **Day 6 chain pivot (architectural)**: KeeperHub does not support 0G Galileo (chainId 16602 missing from their EVM catalog; cannot be self-registered). Moved Guardian, VulnerableLendingPool, ManipulableOracle, MockERC20s to **Base Sepolia (chainId 84532)** where KeeperHub has native support. AgentINFT stays on 0G Chain (Day 7) so 0G Track B (iNFT + Storage + Compute) is unaffected. The TEE attestation from 0G Compute is chain-agnostic and continues to work. Day 5 e2e flow re-validated on Base Sepolia (block 40723024, tx `0xf3caa2a5...`); subsequent drain reverts with IsPaused().
> **Day 6 architectural change verified live (15:38 UTC)**: all 3 agents detect → TEE attest with signer 0x83df4b8e... verified=true → gossip → 3-of-N quorum on hash 0x41026f19... → race; Agent A wins. Agent runtime now reads `contracts/deployments/<chainId>.json` based on the connected RPC's chainId, so the same code works on either chain.
> **Day 6 key-confusion mistake (logged in agent_keys.md memory)**: Day 3's "you said the addresses I generated were funded" was a misread — the user actually funded the Day-2 addresses already in root `.env`. I overwrote those keys in Day 3 before noticing, losing the Day-2 private keys forever. 0.0015 ETH on Base Sepolia at 0xd271..., 0x4a4E..., 0x5b9d... is now stranded. The currently-canonical Day-3 set was funded fresh by the deployer on Base Sepolia today (txs 0x0ca3ea77, 0x196531b6, 0x962b5ac8, 0.0005 ETH each). Stronger memory rule: never overwrite an existing root .env field; ask first when the user's "I already did X" wording is ambiguous.
> **Blockers**: USER tasks status — KeeperHub registered ✓, Gensyn Discord joined ✓, 0G Chain funded ✓, 3 OG deposited to 0G Compute ✓, Base Sepolia funded for deployer + 3 agents ✓. No pending USER tasks for Day 6.

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

- [~] **Analyzer 2** — moved up to Day 4 as analyzer 1 (oracle-manipulation, since that's the demo exploit). The "second specialist" originally planned (reentrancy via `debug_traceTransaction`) is not possible: 0G Galileo returns -32601 for that RPC method. Stretch alternative on Day 8 if slack: a rolling-volatility cross-validator on the same oracle.
- [x] 0G Compute integration: each Finding now carries a real `{summary, tee_text, tee_signature, tee_signing_address, tee_attestation_hash}`. Bridge: `og-compute/summarize-finding.ts`. Wrapper: `agents/og_compute.py`. Provider: dstack-attested chatbot at `0xa48f0128...` running qwen/qwen-2.5-7b-instruct (plan said GLM-5 — provider catalog has Qwen instead).
- [x] Attach `{ summary, tee_signature, tee_text, tee_signing_address }` to Finding before gossip — `agent.py::_on_oracle_event` calls `_attest()` after detection, before signing.
- [x] Verify enclave signature on receiving node before counting toward quorum — `Finding.verify_tee_attestation()` recovers signer from `tee_signature` over `tee_text` and matches `tee_signing_address`. `Aggregator(require_tee=True, expected_tee_signing_addresses=...)` rejects any Finding that doesn't pass.
- [ ] Update README with honest TEE scope note (Day 8 polish): *"TEE signs the LLM summary, not the raw detection."*
- [ ] **Stretch (Day 8 if slack)**: dynamic reputation rolls on iNFT manifest — update `tokenURI` storage root after each rescue.

**Done when**: end-to-end flow: attack tx → analyzer detects → 0G Compute summarizes → signed finding gossips across AXL → quorum verified → pause call emitted. ✓ (2026-04-26 14:44 UTC). Winning tx: `0x5f6db174...`. `FindingAttested` event committed `0xa2d17599cc1eed702a60b1c4decc9cfa096ca652d9fca8885c9b616bc849b6ef` as the TEE attestation hash (real keccak256(tee_text), not placeholder).

**Risk**: 0G Compute latency/rate limits. ✓ Real: dstack provider caps at 2 concurrent requests per user. With 3 agents that's a guaranteed 429 on at least one. Bridge now does 1.5–7s exponential backoff with jitter; all 3 succeed within ~30s of detection.

---

## Day 6 — Wed Apr 29 — KeeperHub + x402

**Objective**: real execution layer + real payments.

- [x] KeeperHub integration: replace direct RPC `pause()` with a KeeperHub workflow call. Use MCP `execute_workflow` from each agent. (`agents/keeperhub.py`, wired into `agents/agent.py::_fire`.)
- [x] Workflow: webhook-triggered "Write Contract" action calling `Guardian.pause(bytes[] sigs, bytes32 findingHash, bytes32 teeAttestationHash)` on Base Sepolia. Sweep step deferred to Day 7 (will be a second action node in the same workflow once we have testnet USDC or the recovery vault loaded).
- [ ] x402 bounty split — deferred to Day 7 stretch. Cleanest path: a second `web3/transfer-token` action in the same KeeperHub workflow that pays each contributing agent USDC on Base Sepolia from a Klaxon escrow. Needs testnet USDC funding for the escrow.
- [x] Log every KeeperHub friction point in `FEEDBACK.md` — six issues captured with reproduction details and unblock recommendations (chain catalog, JSON-on-200, undocumented node config, missing API docs, template-engine bug + per-execution-PATCH workaround, relayer wallet zero-gas).

**Done when**: full live chain: attacker tx → detection → 0G-attested summary → AXL gossip → quorum → KeeperHub executes pause → x402 pays 3 agents. ✓ Through "KeeperHub executes pause" (2026-04-26 18:04 UTC, agent C won). x402 payouts deferred to Day 7.

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
