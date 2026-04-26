/**
 * Klaxon — smoke-test 0G Compute Sealed Inference + signature fetch.
 *
 * Calls /chat/completions, captures the chat ID, then probes
 * /v1/proxy/signature/<chatID>?model=... directly to see exactly what
 * the provider returns. processResponse internally fails when that GET
 * is non-200, with the unhelpful "getting signature error".
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

  const userPrompt = "Say 'klaxon-attestation-test' and nothing else.";
  const headers = await broker.inference.getRequestHeaders(PROVIDER!, userPrompt);
  const body = {
    model: md.model,
    messages: [{ role: "user", content: userPrompt }],
    temperature: 0,
    max_tokens: 16,
  };

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
  // The verifiable chat ID for processResponse comes from the ZG-Res-Key
  // response header, NOT the OpenAI-style `id` in the body.
  const chatId =
    res.headers.get("ZG-Res-Key") ||
    res.headers.get("zg-res-key") ||
    json?.id;
  console.log("ZG-Res-Key header:", res.headers.get("ZG-Res-Key"));
  console.log("body.id          :", json?.id);
  console.log("chatId chosen    :", chatId);
  console.log("content :", JSON.stringify(content));

  // svc.url is the base; signature endpoint = ${svc.url}/v1/proxy/signature/<chatID>?model=<model>
  // svc.url is endpoint without "/v1/proxy" suffix
  const baseUrl = md.endpoint.replace(/\/v1\/proxy$/, "");
  const sigUrl = `${baseUrl}/v1/proxy/signature/${chatId}?model=${md.model}`;
  console.log("sigUrl  :", sigUrl);

  // Try a couple of retry-after-delay attempts — the provider may take
  // a moment to persist the signed response.
  for (let i = 0; i < 5; i++) {
    const sigRes = await fetch(sigUrl, { headers: { "Content-Type": "application/json" } });
    console.log(`[try ${i + 1}] sig HTTP ${sigRes.status}`);
    if (sigRes.ok) {
      const sigJson: any = await sigRes.json();
      console.log("sig body:", JSON.stringify(sigJson, null, 2).slice(0, 500));
      break;
    } else {
      const text = await sigRes.text();
      console.log("sig body:", text.slice(0, 300));
    }
    await new Promise((r) => setTimeout(r, 1500));
  }

  // Now drive processResponse with the (correct) arg order and time it
  console.log("\ncalling broker.inference.processResponse(provider, chatID, content)...");
  try {
    const valid = await broker.inference.processResponse(PROVIDER!, chatId, content);
    console.log("processResponse ->", valid);
  } catch (e: any) {
    console.warn("processResponse failed:", e?.message ?? e);
  }
}

main().catch((e) => {
  console.error("FAILED:", e?.message ?? e);
  process.exit(1);
});
