# Builder Feedback — KeeperHub & 0G Compute

This file collects integration feedback for two sponsor stacks Klaxon
depends on. The KeeperHub section (Part 1) is the formal submission for
the [KeeperHub Builder Feedback Bounty](https://ethglobal.com/events/openagents/prizes/keeperhub)
($500, up to 2 teams at $250 each). The 0G Compute section (Part 2) is
included because we hit enough real friction that documenting it would
have saved us a day, and the issues are independent of KeeperHub.

Built during the ETHGlobal Open Agents hackathon (Apr 25 to May 3, 2026).
Each item is written so a brand-new user can grasp the issue from the
first paragraph and an expert can act on the technical detail in the
same item.

---

# Part 1 — KeeperHub

---

## Our use case (context for the rest of this file)

Klaxon is a decentralized exploit-protection swarm. Three independent AI agents watch a protected protocol, each one running a Python process on its own AXL (Gensyn) node. When a suspicious oracle move is detected, each agent signs a Finding object with its own secp256k1 key, gossips it across the AXL mesh, and a per-node aggregator counts signatures. Once any agent sees three distinct authorized signatures over the same finding hash, that agent races the others to submit `Guardian.pause(sigs[], findingHash, teeAttestationHash)` on chain. Whichever agent's tx lands first wins; the others revert harmlessly with `AlreadyProcessed`.

KeeperHub is the load-bearing piece that gets the pause tx onto chain reliably (private routing, retries, gas optimization). After a successful pause, an x402 V2 session settles bounty payouts to the three contributing agents.

Day 1 of integration: 2026-04-27.

---

## Issue 1: 0G Galileo testnet (chainId 16602) is not in the supported chain catalog

**Plain English.** Klaxon was originally targeting 0G Chain, one of the headline sponsor chains for this same hackathon. KeeperHub does not list 0G as a supported network and there is no public way to add a custom chain through the API or UI. We had to redeploy our entire Solidity stack to Base Sepolia just to get a KeeperHub workflow running, then design a cross-chain story so the 0G iNFT track requirements were still met. That redesign cost roughly half a day.

**Technical detail.**

- `GET https://app.keeperhub.com/api/chains` (auth: `Authorization: Bearer <KEEPERHUB_API_KEY>`) returns 19 chains. Filtering for `chainType == "evm"` yields: Ethereum (1), Sepolia (11155111), Base (8453), Base Sepolia (84532), Tempo (4217 / 42429), BNB (56 / 97), Polygon (137 / 80002), Arbitrum (42161 / 421614), Avalanche (43114 / 43113), Plasma (9745 / 9746). 0G Galileo (16602) is absent.
- `POST /api/chains` with a custom-chain payload returned an empty body. The endpoint either does not exist for end users or requires admin auth that is not documented.
- 0G Galileo is a vanilla EVM chain. Adding it should be a config-only change (RPC, chainId, explorer URL, a flag for whether their private mempool is supported there). The fact that we cannot self-add it forced an architectural compromise.

**What would unblock other builders at this same event.**

1. Add 0G Galileo (chainId 16602, RPC `https://evmrpc-testnet.0g.ai`, explorer `https://chainscan-galileo.0g.ai`) to the catalog. It is one of three headline sponsor chains for ETHGlobal Open Agents.
2. Document an "add custom chain" path for users with a plain RPC URL. Even if you cannot offer private routing on that chain, builders can still use KeeperHub for orchestration, scheduling, and logging.
3. In the chain-picker UI, show a short note next to each chain: "private mempool yes/no" so builders know up front whether your headline private-routing feature applies.

---

## Issue 2: 404 page-not-found is returned with HTTP 200 status code from API endpoints

**Plain English.** When you hit an API path that does not exist, KeeperHub returns the website's 404 HTML page instead of a JSON error. From a script's perspective the request looks successful (200 OK, body is HTML), so debugging tools default to believing the call worked. We spent five extra minutes trying to figure out whether `/api/networks` was just empty before realizing the response was actually the 404 page.

**Technical detail.**

```
$ curl -i -H "Authorization: Bearer $KEEPERHUB_API_KEY" "https://app.keeperhub.com/api/networks"
HTTP/2 200
content-type: text/html; charset=utf-8
...
<!DOCTYPE html><html lang="en"><head>...<title>404: This page could not be found.</title>...
```

Expected: `HTTP/2 404` with `Content-Type: application/json` and a body like `{"error":"unknown route","path":"/api/networks"}`.

The fix is in your Next.js API router. A catch-all 404 handler at `/api/*` that returns a JSON error (not HTML) and the correct status code would surface this immediately. Same fix likely applies to `/api/node-types`, `/api/integrations` (when no integrations exist), and any other unmounted route.

---

## Issue 3: Workflow node JSON shape is not in any public docs

**Plain English.** To create a workflow programmatically you need to know the exact JSON shape for a "Write Contract" action node, including which field names KeeperHub uses for chainId, function selector, ABI, args, signer, and gas overrides. None of this is in the public docs we found. We had to reverse-engineer the shape by reading workflows we created in the visual builder.

**Technical detail.** The example payloads on the GitHub README ([KeeperHub/keeperhub](https://github.com/KeeperHub/keeperhub), [KeeperHub/mcp](https://github.com/KeeperHub/mcp)) show the API endpoints and tool names but never the actual schema for a node's `data.config`. After listing existing workflows via `GET /api/workflows` we got a sample for the `trigger` type:

```json
{
  "id": "yFbsLfz74Fr8BTFWr_LV0",
  "data": {
    "type": "trigger",
    "label": "",
    "config": { "triggerType": "Manual" },
    "status": "idle",
    "description": ""
  },
  "type": "trigger",
  "position": { "x": 0, "y": 0 }
}
```

That tells us positions and the outer envelope, but nothing about what `config` looks like for `web3-write-contract`, `web3-read-contract`, `transfer-tokens`, etc. There is no `/api/node-types` endpoint that documents accepted `config` schemas (it returns the 404 HTML page).

**What would unblock other builders.**

1. Publish a JSON Schema for each node type at `/api/node-types/<typeId>/schema` (or similar). Even a TypeScript `.d.ts` file in the public repo would do.
2. Show one fully-worked example workflow JSON per common pattern: "trigger then write contract", "scheduled read then condition then notify", "webhook then transfer tokens".
3. The visual builder already serializes to this format internally; exposing it as a "Show JSON" button on each node in the builder would let users copy-paste.

---

## Issue 4: Mustache templates `{{...}}` in `functionArgs` are not rendered before JSON.parse, so dynamic args from the trigger payload never work

**Plain English.** KeeperHub lets you build a workflow where a webhook receives some JSON from outside and a contract action uses fields from that JSON as its arguments. The intended way to wire a webhook field into a contract argument is a Mustache-style template like `{{@webhook-trigger.data.sigs}}`. In our testing, those templates are not expanded before the workflow tries to JSON-parse the `functionArgs` string. The result is that the literal characters `{{` reach the parser, JSON parsing fails on the second `{`, and the action errors out with `Invalid function arguments JSON: Expected property name or '}' in JSON at position 2`. We could not get any template variant to work, so we fell back to a workaround: every time the agent wants to fire the workflow, it PATCHes the workflow's `functionArgs` with the concrete values baked in, then triggers the workflow with an empty input.

**Technical detail.** Reproduction:

```bash
# Workflow node config (truncated). functionArgs is a JSON-encoded string.
"functionArgs": "[{{@webhook-trigger.data.sigs}}, \"{{@webhook-trigger.data.findingHash}}\", \"{{@webhook-trigger.data.teeAttestationHash}}\"]"
```

Variants tried, all returning the same error at the same position:

| template prefix | result |
|---|---|
| `{{@webhook-trigger.data.<field>}}` | `Invalid function arguments JSON: Expected property name or '}' in JSON at position 2 (line 1 column 3)` |
| `{{@webhook-trigger.<field>}}` | same |
| `{{@webhook-trigger.body.<field>}}` | same |
| `{{@webhook-trigger.input.<field>}}` | same |
| `{{@webhook-trigger.payload.<field>}}` | same |
| `{{@webhook-trigger.output.<field>}}` | same |
| `{{webhook-trigger.data.<field>}}` (no `@`) | same |

The error message is exactly what JSON.parse returns when the second character of `[{{` is the second `{`: it has opened an array, opened an object, and is now expecting a property name or the closing `}`. So the templates clearly are not being evaluated at all in this code path.

The AI workflow generator at `POST /api/ai/generate` produces this same syntax (`{{@trigger-webhook.data.recipients}}` for an `address[]`) so an end user following AI-generated examples will hit the same wall.

**Workaround we shipped.** `agents/keeperhub.py::_patch_static_args` PATCHes the action node before each execution:

```python
n["data"]["config"]["functionArgs"] = json.dumps([sigs_hex, finding_hash_hex, tee_hash_hex])
# then PATCH /api/workflows/<id> with the modified node
# then call execute_workflow with input={}
```

This works reliably. KeeperHub's relayer wallet then signs and submits the tx with private routing on supported chains. End-to-end on Base Sepolia: agent C submitted `0x59eff596...` calldata via KeeperHub, status returned `success`, Pool.paused() became true, subsequent attacker `drain()` reverted with `IsPaused()`.

**What would unblock builders.** Either fix the template engine so `{{...}}` is expanded inside `functionArgs` before JSON.parse (the actually-intended behavior), OR document the pre-execution PATCH workaround prominently. A template engine that renders parameters from the trigger payload is the only way a third party can reasonably call your workflows from outside, so this is the load-bearing piece for any agent that wants to integrate.

---

## Issue 5: KeeperHub's relayer wallet has zero gas by default, with no UX nudge to fund it

**Plain English.** The first time we got the workflow to encode calldata correctly, the action errored with `insufficient funds for intrinsic transaction cost`. We then checked the balance of the relayer wallet KeeperHub uses for our org and found it was zero. Nothing in the dashboard or the API responses told us we had to fund this wallet, and the relayer address is not displayed anywhere prominent in the UI. We discovered it only because the error message included the `from` address.

**Technical detail.**

- `GET /api/integrations` returns `[{"id":"...","name":"0xc90e...fa84","type":"web3"}]`. The shortened address there is the relayer; the full address is not in this response.
- The full address comes through only in failed-execution error messages, embedded in the `transaction.from` field of the JSON-RPC error.
- After we sent 0.0005 ETH on Base Sepolia from our deployer wallet to `0xc90e350d8D8048d855C96CD8CD536855D1D4fa84`, the next `execute_workflow` succeeded.

**What would unblock builders.**

1. On workflow creation, if the workflow contains any `web3/write-contract`, `web3/transfer-funds`, `web3/transfer-token`, or `web3/approve-token` action, surface an "execution wallet not funded" warning that links to the wallet's address and shows current balance per chain. Even a static "this workflow's relayer is `0x...`; fund it for X chain" notice would be enough.
2. The `GET /api/integrations` response should include `address` (full) and ideally `balance` per chain.
3. When an execution fails with `insufficient funds` for the relayer, the error message should explicitly say "fund the KeeperHub relayer wallet at `0x...` on chain X" rather than just bubbling up the JSON-RPC text.

---

## Issue 6: API endpoint paths do not follow REST conventions and are not documented

**Plain English.** Several KeeperHub API endpoints use unusual paths that are different from what a developer would guess from the resource name. We had to discover most of them by sending OPTIONS requests and reading the `Allow` headers, or by sending HTTP verbs and seeing which ones came back with `400` (real route, bad payload) instead of `404` or `405`.

**Technical detail.**

Discovered by probing:

| What we tried | Status | Right path |
|---|---|---|
| `POST /api/workflows` | 405 (Allow: GET, HEAD, OPTIONS) | `POST /api/workflows/create` |
| `POST /api/workflows/<id>/execute` | 404 | use MCP `execute_workflow` tool |
| `POST /api/workflows/<id>/run` | 404 | use MCP `execute_workflow` tool |
| `POST /api/workflows/run` | 405 | use MCP `execute_workflow` tool |
| `POST /api/networks` (chains list) | 404 (HTML) | `GET /api/chains` |
| `POST /api/node-types` | 404 (HTML) | endpoint does not exist |

The MCP tool `execute_workflow` exists and works, but only after a JSON-RPC `initialize` call to obtain an `mcp-session-id`, which is then required as a header on every subsequent call. The browser-style "execute" path does not exist in the REST API at all.

**What would unblock builders.** Publish an OpenAPI spec at `/api/openapi.json` or `/api/docs`. Add a section to the GitHub README that lists the actual endpoint paths and verbs. Make the REST API mirror the MCP tools where it makes sense (an `execute_workflow` tool that has no REST counterpart is a confusing developer experience).

---

## Issue 5: API auth header convention is undocumented (Bearer vs raw key)

**Plain English.** The KeeperHub API key looks like a token but the docs do not say whether to put it in the `Authorization: Bearer <key>` header, an `X-API-Key` header, a query parameter, or a cookie. We had to try each one. `Authorization: Bearer` worked.

**Technical detail.** Pages we checked: `https://app.keeperhub.com/`, the GitHub READMEs at `KeeperHub/keeperhub` and `KeeperHub/mcp`, and the `claude mcp add --transport http keeperhub https://app.keeperhub.com/mcp` flow. None of them spell out the API key header for the REST endpoints (only the MCP-specific `MCP_API_KEY` env var is mentioned). A one-line "Authentication" section under the API docs would solve this:

```
All /api/* endpoints accept either of:
  Authorization: Bearer <key>
  X-API-Key: <key>            (legacy)
```

---

## What we appreciated (so the feedback isn't all negative)

- The visual workflow builder is genuinely good. We sketched the rescue flow there in three minutes before we attempted it programmatically. The fact that the same workflow can be exported and triggered via API is the right architecture.
- The MCP server is a real differentiator. Being able to type a workflow into Claude Code and have it create on KeeperHub is the experience that made us pick KeeperHub over a hand-rolled relayer.
- The pricing tier (free for hackathons, scaling per-execution) is friendly to indie builders. Klaxon's whole pitch is that bonded individual operators can compete with VC-funded teams; a KeeperHub-style execution layer with no minimum commitment fits that story.

---

## Our integration in one diagram

```
3 Klaxon agents (Python, on AXL nodes)
        │
        │ 1. detect oracle bump on Base Sepolia
        │ 2. summarize via 0G Compute Sealed Inference, attach TEE attestation
        │ 3. sign Finding with secp256k1 key, gossip via AXL
        │ 4. aggregate to 3-of-N quorum
        ▼
KeeperHub workflow (Webhook trigger → Write Contract action)
        │
        │ 5. POST /api/workflows/<id>/execute with {sigs[], findingHash, teeHash}
        │ 6. workflow calls Guardian.pause(...) on Base Sepolia with private routing
        ▼
Guardian.pause emits FindingAttested + Paused
Pool.paused() flips true; subsequent attacker drain reverts with IsPaused()
        │
        ▼
x402 V2 session pays the 3 contributing agents from a Klaxon escrow
```

---

# Part 2 — 0G Compute (Sealed Inference)

Feedback for the [0G Track B](https://ethglobal.com/events/openagents/prizes/0g-labs)
sponsor stack, specifically `@0glabs/0g-serving-broker` (TS SDK) and the
dstack-attested chatbot provider catalog.

## Our use case (context for the rest of this section)

Every Klaxon Finding carries a TEE-signed envelope proving which model
produced its summary. Receivers verify the envelope locally before
counting the finding toward 3-of-N quorum. The TEE attestation hash is
also committed on-chain in the `FindingAttested(findingHash, teeHash)`
event emitted by `Guardian.pause`. We use `@0glabs/0g-serving-broker`
to call the dstack-attested chatbot provider
`0xa48f01287233509FD694a22Bf840225062E67836` (Qwen 2.5 7B), then fetch
the signature envelope from the provider's `/v1/proxy/signature/<chatID>`
endpoint, then verify locally via `processResponse` before attaching to
the Finding.

Day 1 of integration: 2026-04-26 (Day 5 of the hackathon).

---

## Issue 1: SDK v0.7.5 ESM build re-exports symbols that don't exist in the chunk file

**Plain English.** The TypeScript SDK ships an ESM build, but its
`lib.esm/index.mjs` re-exports symbols under aliased names that
the bundled chunk file doesn't actually export. `import { ... } from
"@0glabs/0g-serving-broker"` from an ESM project fails at module-resolve
time. The CJS build works fine, so we kept the bridge as CJS and
sub-process it from Python — but anyone building a fully-ESM Node app
(which is the modern default) will hit this immediately.

**Technical detail.** Repro on a clean `npm init -y; npm i @0glabs/0g-serving-broker@0.7.5`:

```js
// index.mjs
import { createZGComputeNetworkBroker } from "@0glabs/0g-serving-broker";
// → SyntaxError: The requested module '@0glabs/0g-serving-broker' does not
//   provide an export named 'createZGComputeNetworkBroker'
```

The same import works from `index.cjs` (`require(...)`).

**What would unblock builders.** Either fix the `lib.esm` build to export
what `index.mjs` re-exports, or document explicitly in the README that
the SDK is CJS-only today and add `"exports": { ".": { "require": "..." } }`
to `package.json` so bundlers don't try to resolve the broken ESM path.

---

## Issue 2: `processResponse(provider, chatID, content)` arg order is undocumented and counter-intuitive

**Plain English.** The local-verification function that confirms the
provider's signature over their response takes three arguments. The
intuitive order — provider, content (the thing being signed), then
chatID (a metadata identifier) — is wrong. The actual order is provider,
chatID, content. We spent half an hour seeing `verified=false` from a
provider that was actually fine because we'd put the wrong thing in the
middle slot.

**Technical detail.**

```ts
// What we tried first (intuitive but wrong):
const verified = await broker.inference.processResponse(providerAddr, content, chatID);

// What actually works:
const verified = await broker.inference.processResponse(providerAddr, chatID, content);
```

There are no JSDoc tags on the function and no example in the SDK's
README that uses positional args explicitly enough to disambiguate. The
TypeScript types are typed as `(string, string, string)` so the compiler
doesn't catch it.

**What would unblock builders.** Rename the parameters to be self-
documenting (e.g., `providerAddr, chatId, responseContent`), add JSDoc
descriptions, and add one fully-worked round-trip example to the SDK
README that shows `chatCompletion → processResponse` with the chat ID
extraction (see Issue 3) inline.

---

## Issue 3: The `chatID` to pass into `processResponse` is the `ZG-Res-Key` response header, not the OpenAI body `id`

**Plain English.** OpenAI-style chat APIs return an `id` field in the
JSON body. That looks like the canonical request identifier. For 0G
Compute, however, the identifier you pass into `processResponse` is in
a custom HTTP response header (`ZG-Res-Key`), not in the body. We used
the body `id` first, got `verified=false` consistently, and lost about
20 minutes before we noticed the header.

**Technical detail.**

```ts
const res = await fetch(`${endpoint}/chat/completions`, { method: "POST", ... });
const json = await res.json();

const chatIDFromBody = json.id;                    // wrong
const chatIDFromHeader = res.headers.get("ZG-Res-Key");  // right (or zg-res-key, lowercase)
```

The two values are distinct strings. Using the wrong one to fetch
`/v1/proxy/signature/<chatID>` returns 404 sometimes, or returns a stale
attestation that fails `processResponse`.

**What would unblock builders.** Have the SDK extract `ZG-Res-Key`
internally and expose it as `result.chatId` on whatever the
`chatCompletion` wrapper returns. If users have to call `fetch`
themselves (because they want streaming or to inspect headers), at
least document the header name and casing in the README.

---

## Issue 4: dstack provider caps concurrent requests per user at 2; with 3 agents this guarantees one fails

**Plain English.** Klaxon has 3 agents that all detect the same exploit
at roughly the same wall-clock time and each fire an independent TEE-
attestation request to the same provider. The dstack-attested chatbot
provider rate-limits to 2 concurrent requests per user wallet. The
third request comes back as HTTP 429 ("too many concurrent") *or*, more
insidiously, as a TCP socket hang-up mid-request. Without retry, that
agent's finding has no TEE envelope and the other two agents reject it
on receive — quorum drops from 3 to 2 and the rescue can't fire.

**Technical detail.** Reproduced live on 2026-04-26 and again on
2026-05-01 cycle 3 of our integration test (after two clean cycles).
Symptoms:

- HTTP 429 with body containing `"too many concurrent"` (handled)
- Socket hang-up: `fetch()` throws with `socket hang up` or
  `UND_ERR_SOCKET` *before* an HTTP status is set — was unhandled until
  we wrapped the fetch in try/catch
- Provider response with `verified=false` (no clear cause; possibly
  partial response truncation under load)

Our mitigation, all in `og-compute/summarize-finding.ts` and
`agents/agent.py`:

1. Bridge wraps `fetch()` in try/catch and treats network errors the
   same as HTTP 429 (retry with backoff up to 12 attempts).
2. Per-agent `time.sleep` offset (a=0s, b=8s, c=16s) before invoking
   the bridge, so three agents don't hit the provider simultaneously.

Even with both mitigations, on 2026-05-01 the provider was degraded
enough that one of three agents could not get a verified attestation
within 180s. This is an external-dependency reality, not a Klaxon bug.

**What would unblock builders.**

1. Document the per-user concurrency cap explicitly in the dstack
   provider's metadata so callers can preemptively rate-limit themselves.
2. Return HTTP 429 (with `Retry-After`) consistently rather than killing
   the TCP socket — socket hang-ups make every HTTP client think they
   hit a network glitch and either fail-fast or retry too aggressively.
3. Add a lightweight per-user request queue server-side, or expose one
   in the SDK, so callers don't have to roll their own backoff.
4. Provide more than one attested-chatbot provider in the catalog. Today
   `list-providers` returns only one chatbot provider and one image-
   editing provider; if the chatbot provider is degraded there is no
   fallback.

---

## Issue 5: 0G TS SDK chain of `axios` / `open-jsonrpc-provider` is incompatible with Node 25

**Plain English.** We tried to upload our agent manifests to 0G Storage
so the iNFT `tokenURI` could point at a real fetched file. Both
`@0gfoundation/0g-ts-sdk@1.2.6` and `@0glabs/0g-ts-sdk@0.3.3` fail to
load on Node 25 because of a transitive dependency on
`open-jsonrpc-provider`, which depends on a version of `axios` that was
incompatible with Node 25's stricter HTTP behaviour. We worked around
this by committing the manifests to the repo and committing only the
content hash to the iNFT — the on-chain commitment is still cryptographic
proof of the manifest, but the actual file fetch is local.

**Technical detail.** The error chain is `0g-ts-sdk` → `open-jsonrpc-provider`
→ `axios` → an HTTP transport assumption that Node 25 invalidated. Both
SDK versions blow up at import time, before any 0G API is called. We
did not file individual GitHub issues because the fix is on
`open-jsonrpc-provider`'s side and the SDKs would need to bump.

**What would unblock builders.** Pin a Node-compatible version of
`open-jsonrpc-provider` (or fork the bit of it the SDK actually uses)
in the next 0G TS SDK release. Today the SDK only works on Node 18-22
in our experience.

---

## What we appreciated about 0G Compute

- The local-verification model (no provider round-trip on the receive
  path) is the right design for a swarm. Once we attached the TEE
  envelope to the Finding, every agent in the swarm could verify it
  with `processResponse` against `(tee_text, tee_signature, signing_address)`
  — no extra trust in the provider, no extra latency on the gossip path.
  This is what made the TEE attestation feasible to gate quorum on.
- The dstack TEE flow is genuinely cool. `keccak256(tee_text)` as the
  on-chain commitment of *which model reviewed the finding* is a real
  thing you can build slashing on top of.
- The broker's auto-deposit + auto-acknowledge flow is friendly; we
  topped up the deposit account once (3 OG) and didn't have to think
  about it for the rest of the build.

