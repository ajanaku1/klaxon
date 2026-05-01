# AI Usage Attribution

Per ETHGlobal Open Agents rules, this file documents where and how AI tools
were used in the Klaxon project. It is structured to lead with the human
contribution (what was decided and validated) before the per-file table
(what was code-generated under direction), because the human-driven
parts are what determined the architecture, prize-track integrations,
and shipped behavior.

## Tools used

- **Claude Code (Anthropic), Opus 4.7 1M context** — primary pair-
  programmer for the entire build. Used not just as an autocomplete but
  as an executor: read files, ran `forge`, ran the `klaxon` CLI, queried
  on-chain state, edited code in place, and executed integration cycles.
  Every committed file was read, reviewed, and edited by the human
  before push.
- **Editor:** VS Code (`.vscode/` is committed).
- **Git commits:** authored by the human; no AI co-author trailer is
  used in commit messages.
- **No AI voiceover or TTS.** The demo video voiceover is human-recorded.
  ETHGlobal Open Agents explicitly prohibits AI-generated voice in the
  submission video.

## Direction artifacts (how the AI was steered)

Klaxon was **not** built with a formal spec-driven framework like
OpenSpec, Kiro, or spec-kit. AI direction is captured in three durable
artifacts that are all committed to this repo:

- [`PLAN.md`](./PLAN.md) — the day-by-day build plan with a "Resume
  point" block updated at the end of every working session. The resume
  block is the canonical record of what the human directed each day,
  what the hard gates were, what was scope-cut, and which gotchas were
  hit. A fresh AI session reads this block first to re-derive context.
- [`specs/architecture.md`](./specs/architecture.md) — the original
  one-pager (3 contracts, 3 agents, data flow). Drafted with AI from a
  human-authored prompt, then iterated.
- [`FEEDBACK.md`](./FEEDBACK.md) — gotcha log written *after* each
  external-dependency fight (KeeperHub, 0G Compute SDK). Each issue
  was reproduced live by the human before being committed; the file
  doubles as the dual-audience submission for the KeeperHub Builder
  Feedback Bounty and the 0G Compute SDK feedback section.

We also maintain a **local Claude memory file** at
`~/.claude/projects/.../memory/` (outside this repo, not committed —
it contains private session metadata) with two project entries:
`klaxon.md` (concept spec snapshot) and `agent_keys.md` (key-management
mistakes and lessons learned). All operational decisions in memory are
mirrored into `PLAN.md` or `FEEDBACK.md` so the public record is
self-contained.

## Human contribution (what the AI did *not* decide)

Architectural decisions — every one of these was human-authored after
the AI proposed alternatives, and every one shaped what shipped:

- Project ideation, prize-track selection (3-cap on 0G Track B + Gensyn
  AXL + KeeperHub), agent-arena framing, the *"when one finds it, a
  thousand answer"* tagline
- **Pause-oracle vs full-rescue-first design** — chose pause-only for
  hackathon scope; rescue/sweep deferred
- **Race-safe execution** — every agent fires KeeperHub independently,
  first wins, others revert with `AlreadyProcessed`. The naïve
  designated-submitter design was AI-suggested and human-rejected
  because it would have created a single point of failure
- **Cross-chain split** — iNFT + 0G Compute on 0G Galileo, Guardian +
  Pool + Oracle on Base Sepolia, after the Day-6 finding that
  KeeperHub doesn't list 0G Galileo in its chain catalog. Decision
  made by human, FEEDBACK Issue 1 written from that experience
- **secp256k1 vs Ed25519 for finding signatures** — chose secp256k1 for
  cheap on-chain `ecrecover`; Ed25519 stays as AXL transport. Decision
  made on Day 3 noon
- **Two-key model for agent identity** — transport vs finding-signing.
  Day-3 mistake (overwriting Day-2 funded keys) caught and recorded
  in `agent_keys.md` memory + `PLAN.md`; led to the explicit "never
  overwrite root .env" rule
- **CLI-first pivot on Day 7** — killed the planned Next.js dashboard
  after the human determined the product is a terminal tool, not a SaaS.
  AI-generated three React proposals; human dropped all three and
  redirected to a Typer CLI + single-file `demo.html`
- **Per-agent TEE stagger (Day 8)** — human-diagnosed root cause of
  cycle-3 flake (dstack 2-concurrent cap), AI implemented the
  staggered-offset fix per the human's specification
- **Mustache-template PATCH workaround for KeeperHub** — human
  reproduced the bug live, AI implemented the per-execution PATCH
  workaround to the human's design

Operational work (entirely human):

- All testnet funding decisions and faucet operations
- All agent and deployer key generation, custody, and on-chain
  funding txs
- All deployer-account broadcast operations (`forge script
  --broadcast`, etc.) — confirmed live before each one
- KeeperHub workflow creation in the visual builder before the API
  reverse-engineering
- Demo video script direction, recording, voiceover, editing
- Final commit, push, and submission decisions

Critique and hole-poking (entirely human):

- Corrected AI's initial assumption that KeeperHub is "Flashbots-like"
- Corrected AI's initial assumption that x402 supports streaming
  (it doesn't — discrete sessions only)
- Corrected AI's initial assumption that AXL has native broadcast
  (it doesn't — `/topology["peers"]` is direct TCP only; we
  iterate a roster instead)
- Caught AI's GLM-5 hallucination in the original Tech Stack section
  (provider catalog has Qwen 2.5 7B, not GLM-5)
- Caught AI's overwriting of Day-2 root `.env` keys on Day 3 — led
  to the new "never overwrite an existing root .env field" rule

**Rough split:** the human authored 100% of the architectural decisions
and ~100% of the on-chain operations; Claude Code generated the bulk of
the code text under tight human direction with ~100% of files
human-reviewed before commit. The hackathon submission would not exist
in any recognizable form without either party.

## Per-file attribution

The pattern in every row: human specified the behavior, Claude Code
generated the implementation, human reproduced or validated the result
before commit. Where a row says "iterated", that means the human
directed a re-write or fix after the first generation didn't meet spec.

| Area | What the human specified / validated | What Claude Code generated |
|---|---|---|
| `PLAN.md` | Day-level scope, prize-track selection, hard-gate criteria, scope cuts | Initial 9-day plan + every "Resume point" block update |
| `specs/architecture.md` | 3 contracts, 3 agents, data flow shape | Document text |
| `README.md` | Pitch, prize-track framing, honest TEE scope, CLI-driven Running Locally section | Document text; refactored Day 8 to reflect CLI pivot |
| `AI_USAGE.md` (this file) | Structure, leading with human contribution; truthful framing | Document text |
| `LICENSE` | MIT choice | Generated standard MIT text |
| `pyproject.toml` | Package layout, dependencies, `klaxon` console-script entry | Manifest text |
| `.env.example` | Which integration secrets are required and naming convention | Template text |
| `contracts/src/Guardian.sol` | 3-of-N quorum design, `FindingAttested` event with TEE attestation hash, owner kill-switch, only-pool-target invariant | Solidity scaffold |
| `contracts/src/VulnerableLendingPool.sol` | Vulnerability shape: 2-tx exploit (oracle bump in N, drain in N+1) so the detection window is real | Solidity implementation |
| `contracts/src/ManipulableOracle.sol` | Single-asset oracle with permissioned `setPrice` for the attacker script | Solidity implementation |
| `contracts/src/AgentINFT.sol` | ERC-7857 mint-only; `setStorageRoot` so manifest can be updated post-rescue | Solidity implementation |
| `contracts/src/MockERC20.sol` | Two demo ERC-20s for collateral + debt | Standard implementation |
| `contracts/script/Deploy.s.sol` | Determine which addresses get authorized, write deployment JSON for the agent runtime to read | Foundry script |
| `contracts/script/Attacker.s.sol` | `bump`, `drain`, `reset` signatures so the demo is one ergonomic call per beat | Foundry script |
| `contracts/test/*` | Coverage areas: quorum, replay, dedupe, unauthorized signer, full exploit reproducibility | Forge tests (11/11 passing on Day 3) |
| `agents/agent.py` | TEE-attestation gating before quorum (Day 5); cross-chain auto-detection (Day 6); per-agent TEE stagger to spread dstack load (Day 8) | Python implementation |
| `agents/aggregator.py` | 3-of-N quorum with signer authorization + TEE re-verification on receive | Python implementation |
| `agents/analyzer_oracle.py` | Detect oracle manipulation via `newPrice >= oldPrice * 5` event filter | Python implementation |
| `agents/axl_client.py` | Roster-based broadcast (after `/topology` investigation showed direct-TCP only); single-poll `/recv` loop | Python implementation |
| `agents/finding.py` | Pydantic Finding model with deterministic canonical-JSON signing for ecrecover | Python implementation |
| `agents/keeperhub.py` | Per-execution PATCH workaround for the Mustache-template bug; client retry shape | Python implementation |
| `agents/og_compute.py` | Subprocess wrapper around the TS bridge; 180s timeout for retries | Python implementation |
| `agents/finding.py`, `agents/aggregator.py` and friends test files (`agents/test_*.py`) | Coverage targets: aggregator quorum, analyzer detection threshold, finding canonical-sign roundtrip, Guardian integration, KeeperHub live happy-path, og-compute round-trip | pytest tests |
| `agents/run_agent.py`, `agents/build_manifests.py`, `agents/smoke_test_axl.py` | One-shot operator scripts for boot and ad-hoc smoke tests | Python implementation |
| `og-compute/summarize-finding.ts` | Bridge contract: stdin payload → broker init → `/chat/completions` → fetch signed envelope → local `processResponse` verify; Day-5 SDK gotchas (CJS vs ESM, `processResponse` arg order, `ZG-Res-Key` header) all reproduced live by human; Day-8 socket-hang-up retry directed after live failure | TypeScript bridge |
| `og-compute/acknowledge.ts`, `deposit.ts`, `list-providers.ts`, `test-inference.ts` | Operator scripts for broker setup and one-shot inference smoke tests | TypeScript scripts |
| `og-compute/README.md` | Setup notes for the bridge | Document text |
| `klaxon/cli.py`, `klaxon/_paths.py`, `klaxon/__init__.py` | CLI entry point, command grouping, environment path resolution | Python implementation |
| `klaxon/commands/{doctor,agents,attack,findings,receipts}.py` | What each subcommand should output; doctor's 28 checks specified by human; pivot to CLI was human-authored | Python implementation |
| `demo.html` | Single-file rescue replay, 1080p-friendly canvas, ~25s sequence, no build step. Pivot from React dashboard authored by human | Vanilla HTML/CSS/JS implementation |
| `manifests/{agent-a,agent-b,agent-c,manifests}.json` | Manifest schema (agentId, pubkey, analyzerCodeHash, reputation), per-agent self-signature requirement | JSON files + signing flow |
| `axl/agent-roster.json`, `axl/node-{a,b,c}-config.json`, `axl/README.md` | Yggdrasil mesh / `tcp_port` config validated by human after on-the-mesh testing; PEM keys generated by human via openssl | Config text and the roster JSON |
| `keeperhub/*.json` (workflow definitions) | Workflow shape directed by human after KeeperHub builder reverse-engineering; per-execution PATCH workaround spec authored after human reproduced the Mustache bug | JSON files |
| `FEEDBACK.md` | Each issue reproduced live by human before commit; recommendations authored jointly | Document text |
| `docs/submissions/{0g,gensyn,keeperhub}.md` | Which prize-track claims are load-bearing vs decorative; on-chain artifact citations validated against repo state | Document text |
| `docs/submissions/video-playbook.md` | Script tone, segment timings, what to show when; recording will be human-only | Document text + camera-cut table |

## How a fresh Claude session can resume context

The `PLAN.md` "Resume point" block is updated at the end of every working
session. On a new session start, Claude reads that block first to
re-derive the current day, last completed work, known gotchas, and next
action — so AI assistance is reproducible across sessions even when this
project's solo human operator switches devices or sleeps. This is the
*actual* spec-driven artifact for this project: a versioned plan with
durable resume state, kept in git rather than in a separate spec
framework.
