"""KeeperHub MCP client (HTTP transport).

Klaxon agents use this to submit Guardian.pause via a pre-defined KeeperHub
workflow instead of sending the tx themselves. KeeperHub's relayer wallet
pays gas and uses private routing on supported chains; the agents only
need to provide the signed quorum payload.

Wire-level shape (as of 2026-04-26 against https://app.keeperhub.com/mcp):

  1. POST /api/workflows/<id>  PATCH the action node's `functionArgs` with
                               concrete sigs/findingHash/teeHash baked in.
                               Workaround for the Mustache template engine
                               not running before JSON.parse on dynamic
                               args. See FEEDBACK.md issue 6.
  2. POST /mcp  initialize     (returns mcp-session-id header)
  3. POST /mcp  tools/call name=execute_workflow  with input={}
                returns {executionId, status: "running"}
  4. POST /mcp  tools/call name=get_execution_status  to poll until done

`execute_workflow` returns immediately; the actual tx submission happens
asynchronously inside KeeperHub. Caller polls `wait_for_execution` to
get the final outcome.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / "keeperhub" / "workflow.json"
KEEPERHUB_BASE = "https://app.keeperhub.com"
KEEPERHUB_MCP_URL = f"{KEEPERHUB_BASE}/mcp"

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

log = logging.getLogger("keeperhub")


@dataclass
class ExecutionResult:
    execution_id: str
    status: str  # "success" | "error" | "running"
    error: str | None = None
    last_node: str | None = None


class KeeperHubClient:
    def __init__(self, api_key: str | None = None, workflow_id: str | None = None):
        self.api_key = api_key or _load_api_key()
        if not self.api_key:
            raise RuntimeError("KEEPERHUB_API_KEY not set in /.env or env")
        if workflow_id is None:
            wf = json.loads(WORKFLOW_PATH.read_text())
            workflow_id = wf["workflow_id"]
        self.workflow_id = workflow_id
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json,text/event-stream",
        })
        self._mcp_session_id: str | None = None

    def _initialize(self) -> str:
        r = self.session.post(
            KEEPERHUB_MCP_URL,
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "klaxon-agent", "version": "0.1"},
                },
            },
            timeout=15,
        )
        r.raise_for_status()
        sid = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id")
        if not sid:
            raise RuntimeError(f"no mcp-session-id in response headers: {dict(r.headers)}")
        return sid

    def _ensure_session(self) -> str:
        if self._mcp_session_id is None:
            self._mcp_session_id = self._initialize()
        return self._mcp_session_id

    def _call_tool(self, name: str, arguments: dict, request_id: int = 2) -> dict:
        sid = self._ensure_session()
        r = self.session.post(
            KEEPERHUB_MCP_URL,
            headers={"mcp-session-id": sid},
            json={
                "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            raise RuntimeError(f"MCP {name} error: {body['error']}")
        # Each tool result is wrapped as {result:{content:[{type:"text",text:"<json>"}]}}
        content = body["result"]["content"]
        if not content or content[0].get("type") != "text":
            raise RuntimeError(f"unexpected MCP content shape: {body}")
        return json.loads(content[0]["text"])

    def _patch_static_args(self, sigs_hex: list[str], finding_hash_hex: str, tee_hash_hex: str) -> str:
        """Bake concrete pause args into the workflow's functionArgs and
        return the contract address used. KeeperHub's Mustache template
        engine doesn't render `{{...}}` before JSON.parse on dynamic args
        in our testing, so we patch the action node per execution instead."""
        wf_record = json.loads(WORKFLOW_PATH.read_text())
        guardian = wf_record["guardian"]
        deploy_path = REPO_ROOT / "contracts" / "deployments" / f"{wf_record['chainId']}.json"
        if deploy_path.exists():
            guardian = json.loads(deploy_path.read_text())["guardian"]

        wf = self.session.get(f"{KEEPERHUB_BASE}/api/workflows/{self.workflow_id}", timeout=15).json()
        for n in wf["nodes"]:
            if n["id"] == "pause-contract":
                n["data"]["config"] = {
                    "actionType": "web3/write-contract",
                    "network": "base-sepolia",
                    "contractAddress": guardian,
                    "abi": json.dumps(GUARDIAN_PAUSE_ABI),
                    "abiFunction": "pause",
                    "functionArgs": json.dumps([sigs_hex, finding_hash_hex, tee_hash_hex]),
                    "gasLimitMultiplier": "1.2",
                }
        r = self.session.patch(
            f"{KEEPERHUB_BASE}/api/workflows/{self.workflow_id}",
            json={"nodes": wf["nodes"], "edges": wf["edges"]},
            timeout=15,
        )
        r.raise_for_status()
        return guardian

    def execute(self, sigs_hex: list[str], finding_hash_hex: str, tee_hash_hex: str) -> str:
        """Trigger the rescue workflow. Returns the executionId."""
        self._patch_static_args(sigs_hex, finding_hash_hex, tee_hash_hex)
        out = self._call_tool("execute_workflow", {
            "workflowId": self.workflow_id,
            "input": {},
        }, request_id=2)
        execution_id = out.get("executionId")
        if not execution_id:
            raise RuntimeError(f"no executionId in execute_workflow response: {out}")
        log.info("started execution %s for workflow %s", execution_id, self.workflow_id)
        return execution_id

    def get_status(self, execution_id: str) -> ExecutionResult:
        out = self._call_tool("get_execution_status", {"executionId": execution_id}, request_id=3)
        status = out.get("status", "unknown")
        ctx = out.get("errorContext") or {}
        return ExecutionResult(
            execution_id=execution_id,
            status=status,
            error=ctx.get("error"),
            last_node=ctx.get("lastSuccessfulNodeName"),
        )

    def wait_for_execution(self, execution_id: str, timeout_s: float = 60.0, poll_s: float = 2.0) -> ExecutionResult:
        deadline = time.time() + timeout_s
        last: ExecutionResult | None = None
        while time.time() < deadline:
            last = self.get_status(execution_id)
            if last.status in ("success", "error", "failed"):
                return last
            time.sleep(poll_s)
        return last or ExecutionResult(execution_id, "timeout")


def _load_api_key() -> str | None:
    if v := os.environ.get("KEEPERHUB_API_KEY"):
        return v
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if line.startswith("KEEPERHUB_API_KEY="):
            return line.split("=", 1)[1].strip()
    return None
