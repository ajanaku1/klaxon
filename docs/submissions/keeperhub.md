# Klaxon · KeeperHub Submission

**Tracks:**
- [KeeperHub — Best use of KeeperHub] ($4,500)
- [KeeperHub — Builder Feedback Bounty] ($500, see `FEEDBACK.md`)

**Project:** Klaxon — an agent arena for DeFi exploit detection. Three bonded
analyzer iNFTs compete to spot exploits, cross-verify each other inside a TEE,
and trigger a protocol pause on 3-of-N quorum.

---

## Why KeeperHub is load-bearing here

The whole product claim collapses if the rescue tx loses the race. Klaxon
detects an exploit *before* it lands. The attacker's two-tx exploit
(oracle bump in block N, drain in block N+1) gives the swarm one block
window to pause. The rescue tx has to submit fast enough to make block
N+1, stay out of the public mempool where blackhat bots watching for
`Guardian.pause` selectors could front-run the rescue itself, and get
re-submitted automatically on the inevitable transient RPC errors.

That's not something we were going to build from scratch in a hackathon.
KeeperHub gives us private routing, retries, gas handling, and a relayer
wallet that pays the gas, all behind a workflow any agent in the swarm
can fire.

## What we built

### One workflow, three agents, race-safe execution

We define a single KeeperHub workflow that wraps `Guardian.pause`:

- **Workflow ID:** `1swcv2sbszrgj6z4rrgd5`
- **Trigger:** webhook
- **Action:** `web3-write-contract` calling `Guardian.pause(bytes[] sigs, bytes32 findingHash, bytes32 teeAttestationHash)` on Base Sepolia
- **Relayer:** KeeperHub's wallet `0xc90e350d8D8048d855C96CD8CD536855D1D4fa84`
  (we funded it 0.0005 ETH on Day 6 so executions don't OOG)

When 3-of-N quorum forms on a node, that node calls
`KeeperHubClient.execute(sigs, findingHash, teeHash)`
(`agents/keeperhub.py`). Multiple agents reach quorum at roughly the
same time, so all three race to fire the workflow. KeeperHub submits
each call, the first one mines, and the others revert harmlessly with
`AlreadyProcessed` (selector `0x57eee766`). That race is the *correct*
outcome: it's what keeps the rescue working when any single agent (or
KeeperHub itself) is down.

### Live verification

Day-6 hard gate cleared at 18:04 UTC, 2026-04-26:

- Bump tx lands at block N
- 3 agents detect, each TEE-attests via 0G Compute, gossips signed
  Finding across AXL
- 3-of-N quorum forms on hash `0x41026f19...`
- All three agents call `KeeperHubClient.execute(...)` independently
- Agent A's execution wins; KeeperHub relayer submits
  `Guardian.pause`, mined in block N+1
- Pool.paused() flips true; the attacker's follow-up `drain()` reverts
  with `IsPaused()`
- Agents B and C's executions revert with `AlreadyProcessed`,
  observable in their logs

We've re-run this end-to-end several times since. Cycles 1 and 2 of the
×N integration test on 2026-05-01 both passed clean: agent C wins
cycle 1 in 64s, agent A wins cycle 2 in 64s.

### Cross-chain compatibility built into the agent runtime

Klaxon's agent runtime auto-selects the deployment file based on the
RPC's `chainId`, so the same Python code works on either Base Sepolia
or 0G Galileo. We pivoted Guardian + Pool + Oracle to Base Sepolia on
Day 6 because KeeperHub didn't support 0G Galileo (see `FEEDBACK.md`
Issue 1). The pivot was a config change, not a code change.

## Why "race-safe" was non-trivial

A naïve design has one designated agent submit the pause tx. That
hands an attacker a single point of failure: take down agent A and the
rescue never fires. We instead let *every* agent that sees quorum fire
its own KeeperHub execution. KeeperHub's relayer submits each one, and
on-chain dedupe (`Guardian` rejects an already-processed `findingHash`)
makes sure only the first lands.

This depends on KeeperHub being able to absorb 3 simultaneous
`/api/workflows/<id>/execute` calls without dropping any, which it
does. The cost is 2 wasted relayer txs per rescue, which is a fine
price for removing the SPOF.

## Workarounds we shipped (and why)

We needed two workarounds on top of KeeperHub. Both are written up
with reproduction steps and proposed fixes in `FEEDBACK.md` (Issues 4
and 6). Short version:

1. **Mustache template `{{...}}` not rendered before JSON.parse** in
   action `functionArgs`. Workaround: every execution PATCHes the
   workflow's `functionArgs` with concrete sigs/findingHash/teeHash
   baked in, then triggers with empty input
   (`agents/keeperhub.py::_patch_static_args`).
2. **Relayer wallet ships with zero gas and address is not surfaced
   in the dashboard.** We discovered the relayer address from a
   failed-tx error message, then funded it 0.0005 ETH on Base
   Sepolia. Without this, every workflow execution would have OOG.

We mention both because they show the real friction we worked through
to make KeeperHub load-bearing. The product itself worked.

## Builder Feedback bounty

`FEEDBACK.md` is structured for the dual-audience requirement of the
Builder Feedback bounty. Each issue leads with plain-English context,
then technical reproduction, then a specific unblock recommendation.
Six issues total, all hit during real integration:

1. 0G Galileo not in the chain catalog (forced the chain pivot)
2. 404 page returned with HTTP 200 status code
3. Workflow node JSON shape not in any public docs
4. Mustache templates not rendered before JSON.parse (with workaround)
5. Workflow create endpoint is `/api/workflows/create`, not REST-conventional
6. Relayer wallet ships with zero gas and address not surfaced in dashboard

## Live artifacts

- Workflow: `1swcv2sbszrgj6z4rrgd5` on app.keeperhub.com
- Guardian: [`0x...`](https://sepolia.basescan.org/address/...) (latest in `contracts/deployments/84532.json`)
- Day-6 rescue tx: see `klaxon receipts --chain base-sepolia` for the
  block / finding hash
- Code: `agents/keeperhub.py` (KeeperHub MCP/HTTP client),
  `agents/agent.py::_fire` (the call site)
