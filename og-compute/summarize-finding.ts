/**
 * Klaxon Finding ↔ 0G Compute bridge.
 *
 * stdin : {"prompt": "...", "max_tokens": 80}
 * stdout: { "summary": str,
 *           "tee_attestation_hash": "0x...",   // keccak256(tee_text)
 *           "tee_text": str,
 *           "tee_signature": "0x...",
 *           "tee_signing_address": "0x...",
 *           "verified": bool }
 *
 * Agents call this once per detection. The signed quadruple
 *   (tee_text, tee_signature, tee_signing_address, verified)
 * lets any peer re-verify the attestation locally via ecrecover, with no
 * round-trip to the provider on the receive path.
 *
 * Run:  cat payload.json | node_modules/.bin/tsx summarize-finding.ts
 */

import { config as loadDotenv } from "dotenv";
import * as path from "path";
import * as fs from "fs";
import { ethers } from "ethers";
import { createZGComputeNetworkBroker } from "@0glabs/0g-serving-broker";

loadDotenv({ path: path.join(__dirname, "..", ".env") });

const RPC = process.env.OG_CHAIN_RPC_URL ?? "https://evmrpc-testnet.0g.ai";
const PK = process.env.DEPLOYER_PRIVATE_KEY ?? process.env.PRIVATE_KEY;
const PROVIDER = process.env.OG_COMPUTE_PROVIDER_ADDRESS;

if (!PK || !PROVIDER) {
  process.stderr.write("Set DEPLOYER_PRIVATE_KEY and OG_COMPUTE_PROVIDER_ADDRESS\n");
  process.exit(1);
}

interface Input {
  prompt: string;
  max_tokens?: number;
  temperature?: number;
}

interface Output {
  summary: string;
  tee_attestation_hash: string;
  tee_text: string;
  tee_signature: string;
  tee_signing_address: string;
  verified: boolean;
}

async function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    let buf = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (buf += chunk));
    process.stdin.on("end", () => resolve(buf));
    process.stdin.on("error", reject);
  });
}

async function main() {
  const inputRaw = await readStdin();
  const input: Input = JSON.parse(inputRaw);

  const provider = new ethers.JsonRpcProvider(RPC);
  const wallet = new ethers.Wallet(PK!, provider);
  const broker = await createZGComputeNetworkBroker(wallet);
  const md = await broker.inference.getServiceMetadata(PROVIDER!);

  const headers = await broker.inference.getRequestHeaders(PROVIDER!, input.prompt);
  const body = {
    model: md.model,
    messages: [{ role: "user", content: input.prompt }],
    temperature: input.temperature ?? 0.2,
    max_tokens: input.max_tokens ?? 80,
  };

  // The dstack provider caps concurrent requests per user. With 3 agents
  // attesting in parallel we routinely see HTTP 429. Back off + retry so
  // every agent eventually gets its envelope.
  let res: Response | null = null;
  let json: any = null;
  for (let attempt = 0; attempt < 12; attempt++) {
    try {
      res = await fetch(`${md.endpoint}/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(body),
      });
    } catch (e: any) {
      // Provider closes the TCP socket under concurrent load; treat like a 429.
      const wait = 1500 + attempt * 750 + Math.floor(Math.random() * 500);
      process.stderr.write(`network error (${e?.message ?? e}); sleeping ${wait}ms\n`);
      await new Promise((r) => setTimeout(r, wait));
      continue;
    }
    if (res.ok) {
      json = await res.json();
      break;
    }
    const text = await res.text();
    if (res.status === 429 || /too many concurrent/i.test(text)) {
      const wait = 1500 + attempt * 750 + Math.floor(Math.random() * 500);
      process.stderr.write(`429 throttled (attempt ${attempt + 1}); sleeping ${wait}ms\n`);
      await new Promise((r) => setTimeout(r, wait));
      continue;
    }
    process.stderr.write(`HTTP ${res.status}: ${text}\n`);
    process.exit(2);
  }
  if (!json || !res) {
    process.stderr.write(`exhausted retries on /chat/completions\n`);
    process.exit(2);
  }
  const summary = json?.choices?.[0]?.message?.content ?? "";
  const chatID =
    res.headers.get("ZG-Res-Key") ||
    res.headers.get("zg-res-key") ||
    json?.id;

  // Fetch the signed attestation envelope from the provider.
  const baseUrl = md.endpoint.replace(/\/v1\/proxy$/, "");
  const sigUrl = `${baseUrl}/v1/proxy/signature/${chatID}?model=${md.model}`;
  const sigRes = await fetch(sigUrl);
  if (!sigRes.ok) {
    process.stderr.write(`signature HTTP ${sigRes.status}: ${await sigRes.text()}\n`);
    process.exit(3);
  }
  const sigJson: any = await sigRes.json();
  const teeText: string = sigJson.text;
  const teeSignature: string = sigJson.signature;
  const teeSigner: string = sigJson.signing_address;

  // Re-run the SDK's verification so we know it'll pass on the receive side.
  let verified = false;
  try {
    const v = await broker.inference.processResponse(PROVIDER!, chatID, summary);
    verified = v === true;
  } catch (e: any) {
    process.stderr.write(`processResponse failed: ${e?.message ?? e}\n`);
  }

  const teeAttestationHash = ethers.keccak256(ethers.toUtf8Bytes(teeText));

  const out: Output = {
    summary,
    tee_attestation_hash: teeAttestationHash,
    tee_text: teeText,
    tee_signature: teeSignature,
    tee_signing_address: teeSigner,
    verified,
  };
  process.stdout.write(JSON.stringify(out) + "\n");
}

main().catch((e: any) => {
  process.stderr.write(`FAILED: ${e?.message ?? e}\n`);
  process.exit(1);
});
