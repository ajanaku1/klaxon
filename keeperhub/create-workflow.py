"""Create the Klaxon rescue workflow on KeeperHub.

Builds a Webhook-triggered workflow with one Write Contract action that
calls Guardian.pause(bytes[] sigs, bytes32 findingHash, bytes32 teeHash)
on Base Sepolia. The workflow is private to the user's org. Saves the
returned workflow ID + webhook URL into keeperhub/workflow.json so the
agent runtime can load them at start-up.

Run:  .venv/bin/python keeperhub/create-workflow.py
Env required (from repo-root .env):
  KEEPERHUB_API_KEY
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOYMENT_PATH = REPO_ROOT / "contracts" / "deployments" / "84532.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "workflow.json"
KEEPERHUB_BASE = "https://app.keeperhub.com"

GUARDIAN_PAUSE_ABI = [{
    "name": "pause",
    "type": "function",
    "inputs": [
        {"type": "bytes[]", "name": "sigs"},
        {"type": "bytes32", "name": "findingHash"},
        {"type": "bytes32", "name": "teeAttestationHash"},
    ],
    "outputs": [],
    "stateMutability": "nonpayable",
}]


def main() -> int:
    # Load env from root .env without dotenv dep
    env = {}
    for line in (REPO_ROOT / ".env").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    api_key = env.get("KEEPERHUB_API_KEY") or os.environ.get("KEEPERHUB_API_KEY")
    if not api_key:
        print("Set KEEPERHUB_API_KEY in /.env")
        return 1

    deployment = json.loads(DEPLOYMENT_PATH.read_text())
    if deployment["chainId"] != 84532:
        print(f"Expected Base Sepolia (84532) deployment; got {deployment['chainId']}")
        return 1
    guardian = deployment["guardian"]

    workflow = {
        "name": "Klaxon Rescue Pause",
        "description": "Webhook-triggered Guardian.pause on Base Sepolia, called by Klaxon agents once 3-of-N quorum forms.",
        "visibility": "private",
        "enabled": True,
        "workflowType": "write",
        "chain": "Base Sepolia",
        "nodes": [
            {
                "id": "webhook-trigger",
                "type": "trigger",
                "position": {"x": 100, "y": 200},
                "data": {
                    "label": "Webhook Trigger",
                    "type": "trigger",
                    "config": {
                        "triggerType": "Webhook",
                        "webhookPath": "/webhooks/klaxon-rescue",
                    },
                    "status": "idle",
                },
            },
            {
                "id": "pause-contract",
                "type": "action",
                "position": {"x": 350, "y": 200},
                "data": {
                    "label": "Guardian.pause",
                    "type": "action",
                    "config": {
                        "actionType": "web3/write-contract",
                        "network": "Base Sepolia",
                        "contractAddress": guardian,
                        "abi": json.dumps(GUARDIAN_PAUSE_ABI),
                        "abiFunction": "pause",
                        "functionArgs": json.dumps([
                            {"$extract": "sigs"},
                            {"$extract": "findingHash"},
                            {"$extract": "teeAttestationHash"},
                        ]),
                        "gasLimitMultiplier": "1.2",
                    },
                    "status": "idle",
                },
            },
        ],
        "edges": [
            {
                "id": "edge-webhook-pause",
                "source": "webhook-trigger",
                "target": "pause-contract",
                "type": "default",
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # Note: creation endpoint is /api/workflows/create, NOT REST-conventional
    # POST /api/workflows. The latter returns 405 Method Not Allowed (Allow:
    # GET, HEAD, OPTIONS).
    r = requests.post(f"{KEEPERHUB_BASE}/api/workflows/create", headers=headers, json=workflow, timeout=30)
    if not r.ok:
        print(f"create failed: HTTP {r.status_code}\n{r.text[:500]}")
        return 2
    created = r.json()
    workflow_id = created.get("id")
    print(f"created workflow: {workflow_id}")
    print(f"  enabled : {created.get('enabled')}")
    print(f"  chain   : {created.get('chain')}")

    # Webhook trigger URL convention (verify after first execution).
    webhook_url = f"{KEEPERHUB_BASE}/api/webhooks/klaxon-rescue"
    out = {
        "workflow_id": workflow_id,
        "webhook_url": webhook_url,
        "guardian": guardian,
        "chainId": deployment["chainId"],
        "createdAt": created.get("createdAt"),
    }
    OUTPUT_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(f"saved {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
