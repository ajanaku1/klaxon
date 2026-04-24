# AI Usage Attribution

Per ETHGlobal Open Agents rules, this file documents where and how AI tools were used in the Klaxon project.

## Tools used

- **AI pair-programming assistant** — used for drafting architecture, Solidity, Python agent code, Next.js dashboard, and demo video script. Every output reviewed and edited by a human before commit.

## Spec-driven workflow

All planning artifacts, prompts, and specifications are committed under [`specs/`](./specs/):

- [`specs/architecture.md`](./specs/architecture.md) — system architecture
- `specs/prompts/` — captured prompts for major AI-assisted sessions (added as work progresses)
- [`PLAN.md`](./PLAN.md) — day-by-day build plan

## Per-file attribution

_Filled in as files are written. Format: `path — description of AI contribution / human review status`._

| File | AI contribution | Human review |
|---|---|---|
| `PLAN.md` | Drafted with AI assistance from a 9-day planning session | Reviewed + edited by human |
| `specs/architecture.md` | Drafted with AI assistance | Reviewed + edited by human |
| `README.md` | Drafted with AI assistance | Reviewed + edited by human |

## Human contribution

- Project ideation, prize-track selection, architecture trade-offs (pause-oracle vs rescue-first framing)
- Critique + hole-poking of the concept; corrections to sponsor-stack assumptions (KeeperHub is not Flashbots, x402 is not streaming, AXL has no native broadcast)
- Every committed line reviewed by human before push
- Demo video voiceover, recording, editing (human only — ETHGlobal prohibits TTS/AI voiceover)
