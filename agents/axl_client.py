"""Klaxon AXL client.

Thin wrapper over an AXL node's HTTP API. Each Klaxon agent runs alongside its
own AXL node and uses this client to broadcast signed Findings to the rest of
the swarm and to drain its inbox.

Roster-based broadcast: AXL has no native broadcast and `/topology["peers"]`
only lists direct TCP links (the Gensyn bootstrap servers in our setup). We
broadcast by iterating `axl/agent-roster.json` and `/send`-ing to every other
agent's AXL pubkey — Yggdrasil routes across the mesh.

`/recv` is a single poll, not a long-poll: 200 + body when a message is queued,
204 when empty. `listen()` returns each message as it arrives.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
ROSTER_PATH = REPO_ROOT / "axl" / "agent-roster.json"


@dataclass(frozen=True)
class AgentRosterEntry:
    id: str
    eth_address: str
    axl_pubkey: str
    api_port: int


def load_roster(path: Path = ROSTER_PATH) -> list[AgentRosterEntry]:
    data = json.loads(path.read_text())
    return [
        AgentRosterEntry(
            id=a["id"],
            eth_address=a["ethAddress"],
            axl_pubkey=a["axlPubkey"],
            api_port=a["apiPort"],
        )
        for a in data["agents"]
    ]


class AxlClient:
    """One AXL HTTP client bound to a single local agent node."""

    def __init__(self, self_id: str, roster: list[AgentRosterEntry] | None = None, host: str = "127.0.0.1"):
        self.roster = roster or load_roster()
        try:
            self.me = next(a for a in self.roster if a.id == self_id)
        except StopIteration:
            raise ValueError(f"agent id {self_id!r} not in roster") from None
        self.host = host
        self.base_url = f"http://{host}:{self.me.api_port}"

    @property
    def others(self) -> list[AgentRosterEntry]:
        return [a for a in self.roster if a.id != self.me.id]

    def topology(self) -> dict:
        r = requests.get(f"{self.base_url}/topology", timeout=5)
        r.raise_for_status()
        return r.json()

    def send(self, dest_pubkey: str, payload: bytes, timeout: float = 5.0) -> None:
        r = requests.post(
            f"{self.base_url}/send",
            headers={"X-Destination-Peer-Id": dest_pubkey},
            data=payload,
            timeout=timeout,
        )
        if not r.ok:
            raise RuntimeError(f"/send -> {r.status_code}: {r.text.strip()}")

    def broadcast(self, payload: bytes) -> dict[str, str]:
        """Send `payload` to every other agent in the roster.

        Returns a {agent_id: status} map — "ok" for success, the error string
        otherwise. Failures don't raise, since gossip is best-effort and the
        aggregator only needs quorum, not full delivery.
        """
        results: dict[str, str] = {}
        for peer in self.others:
            try:
                self.send(peer.axl_pubkey, payload)
                results[peer.id] = "ok"
            except Exception as e:
                results[peer.id] = f"err: {e}"
        return results

    def recv_once(self, timeout: float = 5.0) -> tuple[str, bytes] | None:
        """Single poll. Returns (from_pubkey, body) on 200, None on 204."""
        r = requests.get(f"{self.base_url}/recv", timeout=timeout)
        if r.status_code == 204:
            return None
        r.raise_for_status()
        return r.headers.get("X-From-Peer-Id", ""), r.content

    def listen(self, poll_interval: float = 0.1) -> Iterator[tuple[str, bytes]]:
        """Yield (from_pubkey, body) tuples as messages arrive. Blocks forever."""
        while True:
            msg = self.recv_once()
            if msg is None:
                time.sleep(poll_interval)
                continue
            yield msg

    def pubkey_to_agent_id(self, pubkey: str) -> str | None:
        """Map an AXL pubkey-or-IPv6-derived-id to a roster agent id.

        `/recv`'s X-From-Peer-Id is derived from the sender's Yggdrasil IPv6,
        not the full Ed25519 key — only the first ~14 bytes match the
        canonical pubkey (the rest is 0x7f-then-0xff padding). We compare on
        a 13-byte (26 hex char) prefix for a safe match.
        """
        prefix = pubkey[:26].lower()
        for a in self.roster:
            if a.axl_pubkey[:26].lower() == prefix:
                return a.id
        return None
