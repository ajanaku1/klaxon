/**
 * Klaxon — smoke-test 0G Compute Sealed Inference.
 *
 * Sends "summarize this exploit finding in one sentence for a human operator"
 * (the actual Day 5 prompt) and prints the model's response. Verifies the
 * round-trip works end-to-end so Day 5 can wire it into the agent runtime.
 *
 * Run:  node_modules/.bin/tsx test-inference.ts
 */

import { config as loadDotenv } from "dotenv";
import * as path from "path";
import { ethers } from "ethers";
import { createZGComputeNetworkBroker } from "@0glabs/0g-serving-broker";

loadDotenv({ path: path.join(__dirname, "..", ".env") });

const RPC = process.env.OG_CHAIN_RPC_URL ?? "https://evmrpc-testnet.0g.ai";
const PK = process.env.DEPLOYER_PRIVATE_KEY ?? process.env.PRIVATE_KEY;
const PROVIDER = process.env.OG_COMPUTE_PROVIDER_ADDRESS;

if (!PK || !PROVIDER) {
  console.error("Set DEPLOYER_PRIVATE_KEY and OG_COMPUTE_PROVIDER_ADDRESS");
  process.exit(1);
}

async function main() {
  const provider = new ethers.JsonRpcProvider(RPC);
  const wallet = new ethers.Wallet(PK!, provider);
  const broker = await createZGComputeNetworkBroker(wallet);

  const md = await broker.inference.getServiceMetadata(PROVIDER!);
  console.log("provider endpoint:", md.endpoint);
  console.log("model            :", md.model);

  const findingPayload = {
    chain_id: 16602,
    finding_type: "oracle_manipulation",
    pool: "0x51A3f25C391C9CDf1421198e94E3aBB71b96A18c",
    evidence: { old_price: "5e21", new_price: "5e22", ratio: 10 },
    block_number: 29923363,
  };
  const userPrompt =
    "Summarize this exploit finding in one sentence for a human operator. " +
    "Be concrete about what the attacker did and why it matters.\n\n" +
    JSON.stringify(findingPayload);

  const headers = await broker.inference.getRequestHeaders(PROVIDER!, userPrompt);

  const body = {
    model: md.model,
    messages: [{ role: "user", content: userPrompt }],
    temperature: 0.2,
    max_tokens: 80,
  };

  console.log("calling /chat/completions...");
  const res = await fetch(`${md.endpoint}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  const json: any = await res.json();
  if (!res.ok) {
    console.error("HTTP", res.status, json);
    process.exit(1);
  }
  const content = json?.choices?.[0]?.message?.content ?? "";
  const chatId = json?.id;
  console.log("\n--- model output ---");
  console.log(content);
  console.log("---");

  // Verify the response was signed by the enclave (this is the TEE attestation
  // step Klaxon's quorum logic needs).
  try {
    const valid = await broker.inference.processResponse(PROVIDER!, content, chatId);
    console.log("processResponse (TEE verification) ->", valid);
  } catch (e: any) {
    console.warn("processResponse failed:", e?.message ?? e);
  }
}

main().catch((e) => {
  console.error("FAILED:", e?.message ?? e);
  process.exit(1);
});
