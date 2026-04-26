/**
 * Klaxon — upload a JSON manifest to 0G Storage on Galileo.
 *
 * stdin : JSON object (any shape; serialized verbatim before upload)
 * stdout: { "rootHash": "0x...", "txHash": "0x..." | null }
 *
 * Mirrors the 0g-storage-ts-starter-kit pattern: write bytes to a temp
 * file, use ZgFile.fromFilePath, let the indexer.upload call compute the
 * Merkle tree internally and return the tx hash plus root.
 *
 * Run:  cat manifest.json | node_modules/.bin/tsx upload-manifest.ts
 */

import { config as loadDotenv } from "dotenv";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import * as crypto from "crypto";
import { ethers } from "ethers";
import { ZgFile, Indexer } from "@0glabs/0g-ts-sdk";

loadDotenv({ path: path.join(__dirname, "..", ".env") });

const RPC = process.env.OG_CHAIN_RPC_URL ?? "https://evmrpc-testnet.0g.ai";
const INDEXER_RPC = process.env.OG_STORAGE_INDEXER ?? "https://indexer-storage-testnet-turbo.0g.ai";
const PK = process.env.DEPLOYER_PRIVATE_KEY ?? process.env.PRIVATE_KEY;

if (!PK) {
  process.stderr.write("Set DEPLOYER_PRIVATE_KEY in /.env\n");
  process.exit(1);
}

async function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    let buf = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (c) => (buf += c));
    process.stdin.on("end", () => resolve(buf));
    process.stdin.on("error", reject);
  });
}

async function main() {
  const inputRaw = await readStdin();
  const obj = JSON.parse(inputRaw);
  const canonical = JSON.stringify(obj, Object.keys(obj).sort());

  const tmp = path.join(os.tmpdir(), `klaxon-manifest-${crypto.randomBytes(8).toString("hex")}.json`);
  fs.writeFileSync(tmp, canonical);
  try {
    const provider = new ethers.JsonRpcProvider(RPC);
    const wallet = new ethers.Wallet(PK!, provider);
    const indexer = new Indexer(INDEXER_RPC);

    const file = await ZgFile.fromFilePath(tmp);
    const [tree, treeErr] = await file.merkleTree();
    if (treeErr || !tree) {
      process.stderr.write(`merkleTree failed: ${treeErr}\n`);
      process.exit(2);
    }
    const rootHash = tree.rootHash();

    const [tx, err] = await indexer.upload(file, RPC, wallet);
    if (err) {
      process.stderr.write(`upload err: ${err}\n`);
    }

    const out = { rootHash, txHash: tx ?? null, size: canonical.length };
    process.stdout.write(JSON.stringify(out) + "\n");

    await file.close();
  } finally {
    try { fs.unlinkSync(tmp); } catch {}
  }
}

main().catch((e: any) => {
  process.stderr.write(`FAILED: ${e?.message ?? e}\n${e?.stack ?? ""}\n`);
  process.exit(1);
});
