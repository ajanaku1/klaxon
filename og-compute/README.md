# 0G Compute helpers

Node-side helpers for the parts of Klaxon that need the `@0glabs/0g-serving-broker` SDK (the Python agent stack uses these via subprocess in Day 5; for now they are run directly by the operator).

## Setup

```bash
cd og-compute
npm install            # or pnpm install
node_modules/.bin/tsx deposit.ts          # deposit 3 OG to the broker ledger
node_modules/.bin/tsx list-providers.ts   # list available inference providers
node_modules/.bin/tsx acknowledge.ts      # acknowledge OG_COMPUTE_PROVIDER_ADDRESS
node_modules/.bin/tsx test-inference.ts   # smoke-test a sealed-inference call
```

Reads from the repo-root `.env` (gitignored). Required vars:

- `DEPLOYER_PRIVATE_KEY` — pays for the deposit and signs broker txs
- `OG_CHAIN_RPC_URL` — defaults to `https://evmrpc-testnet.0g.ai`
- `OG_COMPUTE_PROVIDER_ADDRESS` — set after `list-providers` picks one

## Picked provider

For Klaxon's Day 5 finding-summary inference we use:

| field | value |
|---|---|
| address | `0xa48f01287233509FD694a22Bf840225062E67836` |
| service | `chatbot` |
| model | `qwen/qwen-2.5-7b-instruct` |
| endpoint | `https://compute-network-6.integratenetwork.work/v1/proxy` |
| TEE verifier | `dstack` (https://github.com/Dstack-TEE/dstack) |

Plan originally targeted `glm-5`; that model isn't on this provider's catalog, so we shipped with Qwen 2.5-7B (also dstack-attested). README needs to reflect this swap.

## Known issues

- The SDK's ESM build (`lib.esm/index.mjs` in 0.7.5) re-exports under aliased names that don't exist in the underlying chunk file, breaking `import` from a `"type": "module"` package. We work around it by keeping this package CommonJS and using `import * as path` / `__dirname`.
- `broker.inference.processResponse(...)` returns "getting signature error" on our test call. The HTTP response is OK, the model output is correct — the verification path needs a different argument shape than we're passing. Day 5 fix: dig into the SDK's expected `chatID` format or use the `id` field from the assistant message rather than the OpenAI-style `chat.completions.id`.

## Cost note

The inference test consumed a small amount of OG from the ledger (under 0.001 OG per short summary). 3 OG covers thousands of demo runs.
