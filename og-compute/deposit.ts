/**
 * Klaxon — 0G Compute ledger setup.
 *
 * Loads PRIVATE_KEY from the repo-root .env, creates the broker, and either
 * adds a fresh ledger or tops up the existing one. Defaults to 3 OG.
 *
 * Run:  pnpm deposit  (or `npm run deposit`)
 */

import { config as loadDotenv } from "dotenv";
import * as path from "path";
loadDotenv({ path: path.join(__dirname, "..", ".env") });
import { ethers } from "ethers";
import { createZGComputeNetworkBroker } from "@0glabs/0g-serving-broker";

const RPC = process.env.OG_CHAIN_RPC_URL ?? "https://evmrpc-testnet.0g.ai";
const PK = process.env.DEPLOYER_PRIVATE_KEY ?? process.env.PRIVATE_KEY;
const AMOUNT_OG = Number(process.env.OG_COMPUTE_DEPOSIT_OG ?? 3);

if (!PK) {
  console.error("Set DEPLOYER_PRIVATE_KEY (or PRIVATE_KEY) in .env");
  process.exit(1);
}

async function main() {
  const provider = new ethers.JsonRpcProvider(RPC);
  const wallet = new ethers.Wallet(PK!, provider);
  console.log(`wallet  : ${wallet.address}`);
  console.log(`balance : ${ethers.formatEther(await provider.getBalance(wallet.address))} OG`);

  const broker = await createZGComputeNetworkBroker(wallet);

  // Try reading existing ledger; if it doesn't exist, addLedger creates it.
  let existing: any = null;
  try {
    existing = await broker.ledger.getLedger();
    console.log("existing ledger:", {
      totalBalance: existing.totalBalance?.toString?.() ?? String(existing.totalBalance),
      locked: existing.locked?.toString?.() ?? String(existing.locked),
    });
  } catch (e: any) {
    console.log("no existing ledger — will create one");
  }

  if (existing == null) {
    console.log(`creating ledger with ${AMOUNT_OG} OG...`);
    const tx = await broker.ledger.addLedger(AMOUNT_OG);
    console.log("addLedger tx:", tx);
  } else {
    console.log(`topping up ledger with ${AMOUNT_OG} OG...`);
    const tx = await broker.ledger.depositFund(AMOUNT_OG);
    console.log("depositFund tx:", tx);
  }

  const after = await broker.ledger.getLedger();
  console.log("ledger after:", {
    totalBalance: after.totalBalance?.toString?.() ?? String(after.totalBalance),
    locked: after.locked?.toString?.() ?? String(after.locked),
  });
}

main().catch((e) => {
  console.error("FAILED:", e?.message ?? e);
  process.exit(1);
});
