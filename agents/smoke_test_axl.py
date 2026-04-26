"""Smoke test: agent A broadcasts, agents B and C receive.

Prereq: nodes A, B, C running locally with `axl/bin/node -config node-{a,b,c}-config.json`
on ports 9002, 9012, 9022.

Run:  python agents/smoke_test_axl.py
"""

from __future__ import annotations

import sys
import threading
import time

from axl_client import AxlClient


def reader(client: AxlClient, results: dict, label: str, timeout: float):
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = client.recv_once()
        if msg is not None:
            from_pubkey, body = msg
            results[label] = (client.pubkey_to_agent_id(from_pubkey) or from_pubkey, body)
            return
        time.sleep(0.05)


def main() -> int:
    a = AxlClient(self_id="a")
    b = AxlClient(self_id="b")
    c = AxlClient(self_id="c")

    results: dict[str, tuple[str, bytes]] = {}
    rb = threading.Thread(target=reader, args=(b, results, "b", 5.0))
    rc = threading.Thread(target=reader, args=(c, results, "c", 5.0))
    rb.start()
    rc.start()
    time.sleep(0.2)  # let readers attach before send

    payload = b"klaxon-smoke-test-001"
    bcast = a.broadcast(payload)
    print(f"[a] broadcast result: {bcast}")

    rb.join()
    rc.join()

    fail = False
    for label in ("b", "c"):
        got = results.get(label)
        if got is None:
            print(f"[{label}] FAIL: no message received")
            fail = True
            continue
        from_id, body = got
        if from_id != "a" or body != payload:
            print(f"[{label}] FAIL: unexpected (from={from_id!r}, body={body!r})")
            fail = True
        else:
            print(f"[{label}] OK: received {body!r} from agent {from_id}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
