/**
 * Klaxon — list 0G Compute inference providers on Galileo.
 * Run:  node_modules/.bin/tsx list-providers.ts
 */

import { config as loadDotenv } from "dotenv";
import * as path from "path";
import { ethers } from "ethers";
import { createZGComputeNetworkBroker } from "@0glabs/0g-serving-broker";

loadDotenv({ path: path.join(__dirname, "..", ".env") });

const RPC = process.env.OG_CHAIN_RPC_URL ?? "https://evmrpc-testnet.0g.ai";
const PK = process.env.DEPLOYER_PRIVATE_KEY ?? process.env.PRIVATE_KEY;
if (!PK) { console.error("Set DEPLOYER_PRIVATE_KEY"); process.exit(1); }

async function main() {
  const provider = new ethers.JsonRpcProvider(RPC);
  const wallet = new ethers.Wallet(PK!, provider);
  const broker = await createZGComputeNetworkBroker(wallet);

  const services = await broker.inference.listService();
  console.log(`found ${services.length} providers:`);
  for (const s of services) {
    console.log(JSON.stringify(s, (_, v) => typeof v === "bigint" ? v.toString() : v, 2));
  }
}

main().catch((e) => {
  console.error("FAILED:", e?.message ?? e);
  process.exit(1);
});
