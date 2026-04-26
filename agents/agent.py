"""Klaxon agent runtime.

One process per agent. Three threads:

  scan   : tail oracle PriceBumped events, run analyzer, sign + broadcast
           Findings via AXL.
  listen : drain the local AXL inbox, deserialize Findings, hand to aggregator.
  fire   : when the aggregator forms quorum, race to submit Guardian.pause.
           Self-findings hit the aggregator too, so a single agent that sees
           the event AND receives 2 peer Findings can fire from any thread —
           the firing path is goroutine-safe via a lock + already_fired guard.

All three agents will independently form quorum and try to pause; Guardian's
processedFindings mapping rejects all but the first tx with AlreadyProcessed,
which we treat as success on this side.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from eth_account import Account
from web3 import Web3

from aggregator import Aggregator, Quorum
from analyzer_oracle import OracleManipulationAnalyzer, PriceBumpedEvent
from axl_client import AxlClient, load_roster
from finding import Finding

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOYMENT_PATH = REPO_ROOT / "contracts" / "deployments" / "16602.json"
KEYS_PATH = REPO_ROOT / "axl" / "agent-eth-keys.json"

# ManipulableOracle.PriceBumped(address indexed by, uint256 oldPrice, uint256 newPrice)
PRICE_BUMPED_TOPIC = Web3.keccak(text="PriceBumped(address,uint256,uint256)")

GUARDIAN_PAUSE_ABI = {
    "inputs": [
        {"name": "sigs", "type": "bytes[]"},
        {"name": "findingHash", "type": "bytes32"},
        {"name": "teeAttestationHash", "type": "bytes32"},
    ],
    "name": "pause",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function",
}

# Guardian custom-error selector for AlreadyProcessed
ALREADY_PROCESSED_SELECTOR = Web3.keccak(text="AlreadyProcessed()")[:4].hex()


@dataclass
class AgentConfig:
    agent_id: str
    rpc_url: str
    poll_interval_s: float = 1.5
    priority_gas_price_gwei: int = 2  # 0G Galileo minimum


def _load_eth_key(agent_id: str) -> tuple[str, str]:
    """Return (address, private_key) for `agent_id` from gitignored JSON."""
    data = json.loads(KEYS_PATH.read_text())
    for a in data["agents"]:
        if a["id"] == agent_id:
            return a["address"], a["privateKey"]
    raise KeyError(f"agent {agent_id!r} not in {KEYS_PATH}")


def _decode_price_bumped(log) -> PriceBumpedEvent:
    by = "0x" + log["topics"][1].hex()[-40:]
    data = bytes(log["data"])
    old_price = int.from_bytes(data[0:32], "big")
    new_price = int.from_bytes(data[32:64], "big")
    return PriceBumpedEvent(
        by=by,
        old_price=old_price,
        new_price=new_price,
        tx_hash=log["transactionHash"].hex(),
        block_number=log["blockNumber"],
    )


class Agent:
    def __init__(self, cfg: AgentConfig):
        self.cfg = cfg
        self.log = logging.getLogger(f"agent[{cfg.agent_id}]")
        self.eth_address, self.private_key = _load_eth_key(cfg.agent_id)
        self.deployment = json.loads(DEPLOYMENT_PATH.read_text())
        self.roster = load_roster()
        self.axl = AxlClient(self_id=cfg.agent_id, roster=self.roster)
        self.w3 = Web3(Web3.HTTPProvider(cfg.rpc_url))

        self.analyzer = OracleManipulationAnalyzer(
            chain_id=self.deployment["chainId"],
            pool_address=self.deployment["pool"],
            oracle_address=self.deployment["oracle"],
            agent_id=cfg.agent_id,
            agent_address=self.eth_address,
        )
        self.aggregator = Aggregator(
            authorized_signers=frozenset(a.eth_address.lower() for a in self.roster),
            quorum_size=3,
        )

        self.guardian = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.deployment["guardian"]),
            abi=[GUARDIAN_PAUSE_ABI],
        )
        self._fire_lock = threading.Lock()
        self._stop = threading.Event()

    # ----- scan loop -----

    def scan_oracle_events(self) -> int:
        """Tail the oracle for PriceBumped events. Returns the next block to scan."""
        oracle_addr = Web3.to_checksum_address(self.deployment["oracle"])
        head = self.w3.eth.block_number
        from_block = max(head - 5, 0)  # small look-back for safety on cold start
        last_block = from_block

        self.log.info("scan starting at block %d (head %d)", from_block, head)
        while not self._stop.is_set():
            try:
                head = self.w3.eth.block_number
                if head <= last_block:
                    time.sleep(self.cfg.poll_interval_s)
                    continue
                logs = self.w3.eth.get_logs({
                    "address": oracle_addr,
                    "topics": [PRICE_BUMPED_TOPIC],
                    "fromBlock": last_block + 1,
                    "toBlock": head,
                })
                for log in logs:
                    self._on_oracle_event(_decode_price_bumped(log))
                last_block = head
            except Exception as e:
                self.log.warning("scan error: %s", e)
                time.sleep(self.cfg.poll_interval_s)
        return last_block

    def _on_oracle_event(self, evt: PriceBumpedEvent):
        unsigned = self.analyzer.analyze_event(evt)
        if unsigned is None:
            return
        signed = unsigned.sign(self.private_key)
        self.log.info(
            "DETECTED %s ratio=%dx tx=%s block=%d",
            signed.finding_type, signed.evidence["ratio"], evt.tx_hash, evt.block_number,
        )
        # Self-vote first
        self._ingest(signed)
        # Then gossip to peers
        results = self.axl.broadcast(signed.to_wire())
        self.log.info("broadcast: %s", results)

    # ----- listen loop -----

    def listen_for_findings(self):
        self.log.info("listening on AXL inbox port %d", self.axl.me.api_port)
        for _from_pubkey, body in self.axl.listen():
            if self._stop.is_set():
                return
            try:
                f = Finding.from_wire(body)
            except Exception as e:
                self.log.warning("bad inbound payload: %s", e)
                continue
            self._ingest(f)

    def _ingest(self, f: Finding):
        q = self.aggregator.add_finding(f)
        if q is not None:
            self._fire(q)

    # ----- fire loop -----

    def _fire(self, q: Quorum):
        with self._fire_lock:
            self.log.info(
                "QUORUM hash=0x%s signers=%s — submitting Guardian.pause",
                q.finding_hash.hex()[:16],
                [s[:10] for s in q.signers],
            )
            tee_hash = bytes.fromhex(
                q.representative.tee_attestation_hash[2:]
                if q.representative.tee_attestation_hash.startswith("0x")
                else q.representative.tee_attestation_hash
            )
            try:
                tx = self.guardian.functions.pause(q.sigs, q.finding_hash, tee_hash).build_transaction({
                    "from": self.eth_address,
                    "nonce": self.w3.eth.get_transaction_count(self.eth_address),
                    "gas": 500_000,
                    "maxFeePerGas": self.w3.eth.gas_price + Web3.to_wei(self.cfg.priority_gas_price_gwei, "gwei"),
                    "maxPriorityFeePerGas": Web3.to_wei(self.cfg.priority_gas_price_gwei, "gwei"),
                    "chainId": self.deployment["chainId"],
                })
                signed_tx = Account.sign_transaction(tx, self.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                self.log.info("pause submitted: %s", tx_hash.hex())
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                self.log.info("pause receipt status=%d block=%d", receipt.status, receipt.blockNumber)
            except Exception as e:
                msg = str(e)
                if ALREADY_PROCESSED_SELECTOR in msg.lower() or "alreadyprocessed" in msg.lower():
                    self.log.info("pause: another agent got there first (AlreadyProcessed) — fine")
                else:
                    self.log.error("pause failed: %s", e)

    # ----- driver -----

    def start(self):
        threads = [
            threading.Thread(target=self.listen_for_findings, daemon=True, name="listen"),
            threading.Thread(target=self.scan_oracle_events, daemon=True, name="scan"),
        ]
        for t in threads:
            t.start()
        self.log.info("agent started; threads: %s", [t.name for t in threads])
        try:
            while not self._stop.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self.log.info("stopping")
            self._stop.set()
