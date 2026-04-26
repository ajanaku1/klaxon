/**
 * Klaxon — acknowledge a 0G Compute provider so we can call inference.
 * Required before any /v1/chat/completions call.
 *
 * Run:  node_modules/.bin/tsx acknowledge.ts
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

  console.log(`acknowledging provider ${PROVIDER}...`);
  try {
    await broker.inference.acknowledgeProviderSigner(PROVIDER!);
    console.log("ack OK");
  } catch (e: any) {
    const msg = String(e?.message ?? e);
    if (msg.toLowerCase().includes("already") || msg.toLowerCase().includes("acknowledged")) {
      console.log("already acknowledged — fine");
    } else {
      throw e;
    }
  }

  // Show the metadata the broker will use to talk to the provider
  const md = await broker.inference.getServiceMetadata(PROVIDER!);
  console.log("metadata:", md);
}

main().catch((e) => {
  console.error("FAILED:", e?.message ?? e);
  process.exit(1);
});
