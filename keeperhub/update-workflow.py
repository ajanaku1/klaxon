"""Update the Klaxon rescue workflow's nodes/edges to use the correct
Mustache template syntax and lowercase network slug.

PATCH endpoint accepts {"nodes":[...], "edges":[...], "name":..., ...}.

Run:  .venv/bin/python keeperhub/update-workflow.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOYMENT_PATH = REPO_ROOT / "contracts" / "deployments" / "84532.json"
WORKFLOW_OUT = Path(__file__).resolve().parent / "workflow.json"
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


def load_env_value(key: str) -> str:
    for line in (REPO_ROOT / ".env").read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"{key} not in /.env")


def main() -> int:
    api_key = load_env_value("KEEPERHUB_API_KEY")
    deployment = json.loads(DEPLOYMENT_PATH.read_text())
    guardian = deployment["guardian"]

    workflow_record = json.loads(WORKFLOW_OUT.read_text())
    workflow_id = workflow_record["workflow_id"]

    nodes = [
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
                    "network": "base-sepolia",
                    "contractAddress": guardian,
                    "abi": json.dumps(GUARDIAN_PAUSE_ABI),
                    "abiFunction": "pause",
                    # Mustache templating with @<nodeId>.data.<field>.
                    # The trigger payload's `sigs` field is an array; the
                    # template inlines it as an array literal.
                    "functionArgs": (
                        '[{{@webhook-trigger.data.sigs}}, '
                        '"{{@webhook-trigger.data.findingHash}}", '
                        '"{{@webhook-trigger.data.teeAttestationHash}}"]'
                    ),
                    "gasLimitMultiplier": "1.2",
                },
                "status": "idle",
            },
        },
    ]

    edges = [{
        "id": "edge-webhook-pause",
        "source": "webhook-trigger",
        "target": "pause-contract",
        "type": "default",
    }]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    r = requests.patch(
        f"{KEEPERHUB_BASE}/api/workflows/{workflow_id}",
        headers=headers,
        json={"nodes": nodes, "edges": edges, "enabled": True},
        timeout=30,
    )
    if not r.ok:
        print(f"update failed: HTTP {r.status_code}\n{r.text[:500]}")
        return 2
    body = r.json()
    print(f"updated workflow {workflow_id}")
    print(f"  enabled : {body.get('enabled')}")
    print(f"  pause node config.functionArgs:")
    for n in body["nodes"]:
        if n["id"] == "pause-contract":
            print(f"    {n['data']['config']['functionArgs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
