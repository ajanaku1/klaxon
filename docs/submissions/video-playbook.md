# Demo Video Playbook

Plan for the submission video. Use during recording tomorrow.
Total target: ≤ 3:30, hard cap 4:00.

---

## Setup before you press record

1. `klaxon doctor` should be all green except the "swarm running" warn (we
   want it stopped at start). If pool is paused on either chain, run
   `klaxon attack reset` first.
2. Open `demo.html` in a clean browser window, full-screen at 1920×1080,
   browser chrome hidden (Cmd-Shift-F or Cmd-+ until it fills).
3. Open three terminals in iTerm (or one with three split panes), all
   sized to readable font (≥18pt). Pane layout:
   - Top: full-width terminal for `klaxon` commands
   - Bottom-left: `klaxon findings` tail (live)
   - Bottom-right: `klaxon receipts` (run after rescue)
4. Quiet room. Monitor headphones, not speakers (no echo).
5. Mic: pop filter on, gain so peaks are around -12 dBFS.
6. Record at 1080p60 with OBS or QuickTime. Audio at 48kHz mono.

---

## Script (≈ 440 words, ≈ 3:00 spoken at normal pace)

### [0:00 – 0:15] Problem

> *"Every DeFi protocol has a pauser multisig. It is the most dangerous
> key in the system, and also the slowest. By the time someone wakes up,
> sees the alert, and signs the pause tx, the attacker has already
> drained millions. This problem has been solved for years on the
> attacker side — MEV searchers race blocks. It has never been solved on
> the defender side. Until Klaxon."*

**On screen:** title slide. White text on black, two lines:
**Klaxon** — *"When one finds it, a thousand answer."*

### [0:15 – 0:45] Architecture

> *"Klaxon is an agent arena for DeFi exploit detection. Three bonded
> analyzer iNFTs watch a protected protocol. Each one runs a Python
> process on its own AXL node. When one detects an oracle anomaly, it
> summarizes the finding inside a 0G Compute TEE, signs it with its own
> ETH key, and gossips it across the AXL mesh. Every other agent
> independently verifies the TEE attestation and counts the signature
> toward a 3-of-N quorum. Once quorum forms, every agent that sees it
> races KeeperHub to submit Guardian.pause on chain. The first wins.
> The others revert harmlessly with AlreadyProcessed. The protocol is
> paused before block N+1 — before the attacker's drain transaction
> mines."*

**On screen:** architecture slide (single diagram, see below). Hold for
the full 30s.

### [0:45 – 2:30] Live demo

> *"Here is a live rescue."*

**On screen:** switch to `demo.html`. Press *Run rescue*. The 25-second
sequence plays:

> *"Three agents are watching. The attacker bumps the oracle 10×. All
> three detect within seconds. Each one summarizes the finding inside
> 0G Compute Sealed Inference and gets back a TEE-signed envelope —
> Qwen 2.5 7B, attestation by dstack on Aliyun. Each gossips a signed
> Finding across the AXL mesh. Quorum forms. KeeperHub fires Guardian
> dot pause. The pool flips green. The attacker's drain reverts with
> IsPaused. The three agents split the bounty via x402."*

**On screen:** cut to terminal. Show `klaxon receipts --chain
base-sepolia` listing the on-chain `FindingAttested` event from cycles
1 or 2 today (and the historical Day-6 rescue). Zoom on the
findingHash and the txHash.

> *"That's not animation. Here's the same rescue on chain. Block N,
> oracle bumped. Block N+1, Guardian paused. Drain reverted. The TEE
> attestation hash is committed in the FindingAttested event so any
> auditor can verify which model reviewed the finding."*

### [2:30 – 3:00] Differentiators

> *"Three things make Klaxon different from every other monitoring
> product. One: agents are bonded iNFTs on 0G Chain — slashable
> identity, not API keys. Two: every finding carries a TEE attestation
> verified locally before quorum, so no trust in the swarm operator.
> Three: every agent races to submit the rescue, so taking down any
> single agent doesn't stop the protocol from being protected. The
> swarm is censorship-resistant against itself."*

**On screen:** three-card slide. Card 1: bonded iNFT. Card 2: TEE
attested. Card 3: race-safe.

### [3:00 – 3:15] CTA

> *"This was built solo for ETHGlobal Open Agents in nine days. Three
> sponsor stacks integrated load-bearing — 0G iNFT, Compute, Storage;
> Gensyn AXL; KeeperHub. Repo and live testnet receipts in the
> description. When one finds it, a thousand answer."*

**On screen:** final slide. Repo URL, three sponsor logos.

---

## Architecture diagram (one slide, hold 30s)

Use this ASCII as a visual or redraw in Excalidraw before recording.
Do not over-design it; the diagram is the architecture itself.

```
                 0G Galileo                Base Sepolia
                 ────────                  ────────────
                AgentINFT ×3              Guardian
              0G Compute (TEE)          VulnerableLP
                    ▲                         ▲
                    │ TEE-sig                 │ pause(...)
                    │                         │
              ┌─────┴─────┐         ┌─────────┴─────┐
              │  Agent A  │         │ KeeperHub      │
              │  Agent B  │ ─AXL→   │ workflow       │
              │  Agent C  │         │ private routing│
              └───────────┘         └────────────────┘
              3 bonded iNFTs        first agent wins
```

---

## Pacing notes (where takes typically slip)

- **Don't read the demo beats.** The on-screen beat log already shows
  them. Speak over the action and summarize what's happening.
- **Pause after "the protocol is paused before block N+1".** Let it
  land. Half a second of silence is fine.
- **Cut the receipts segment if you're over 3:15.** The on-chain proof
  is in the description.
- **Differentiators is the easiest section to cut.** If you're over
  3:30, drop card 3 (race-safe) and end at "no trust in the swarm
  operator."

## Camera cuts (what to show when)

| Time | Source | Note |
|---|---|---|
| 0:00 | Title slide | 1920×1080 PNG, 3 sec |
| 0:15 | Architecture slide | Hold full 30s |
| 0:45 | demo.html | Press *Run rescue* AS the audio says "Here is a live rescue" |
| 1:50 | demo.html | The sequence ends at ~1:10. Hold the final state for ~5s |
| 1:55 | Terminal, `klaxon receipts` | Pre-staged, scroll once |
| 2:15 | Basescan tab, the actual tx | Open in advance. Click the tx; show the FindingAttested event in the Logs tab |
| 2:30 | Differentiators slide | Three-card layout |
| 3:00 | Final slide | Repo URL + sponsor logos |

## Pre-recording dry-run checklist

- [ ] `klaxon doctor` is green
- [ ] `klaxon attack reset` ran cleanly (fresh deploy)
- [ ] `klaxon agents up` and at least one rescue cycle completed
      (so receipts has data and the dstack provider is "warm")
- [ ] `demo.html` opens in browser and *Run rescue* plays clean
- [ ] Basescan tab is on the rescue tx, Logs tab selected, FindingAttested
      event highlighted
- [ ] OBS is recording 1080p60, audio peak around -12 dBFS
- [ ] You have water nearby

## Post-recording

- Trim head/tail in iMovie or DaVinci Resolve
- Speed up dead segments to 1.2× max (per ETHGlobal rules)
- Export H.264, 1080p, ≤ 4:00, ≥ 720p
- Verify with `ffprobe -v error -show_streams output.mp4 | grep -E "width|height|duration"`
- Upload to YouTube unlisted; copy URL into ETHGlobal submission form
