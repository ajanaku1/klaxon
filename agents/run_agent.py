"""CLI entry: `python agents/run_agent.py --agent a` starts agent A bound to
its local AXL node. Run three of these in three terminals (or three tmux
panes) with --agent a/b/c — each one tails the chain, broadcasts, listens,
and races to submit Guardian.pause when quorum forms.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import Agent, AgentConfig

DEFAULT_RPC = os.environ.get("ZEROG_TESTNET_RPC", "https://evmrpc-testnet.0g.ai")


def main():
    p = argparse.ArgumentParser(description="Run one Klaxon agent.")
    p.add_argument("--agent", required=True, choices=["a", "b", "c"], help="roster id")
    p.add_argument("--rpc", default=DEFAULT_RPC, help="0G Chain RPC URL")
    p.add_argument("--poll", type=float, default=1.5, help="oracle poll interval (s)")
    p.add_argument("--no-tee", action="store_true", help="skip 0G Compute attestation (faster e2e tests)")
    p.add_argument(
        "--expected-tee-signer",
        action="append",
        default=[],
        help="lowercase 0x-hex of an accepted TEE signing address; pass multiple for redundancy",
    )
    args = p.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)-5s %(name)-12s %(message)s",
        datefmt="%H:%M:%S",
        level=logging.INFO,
    )

    Agent(AgentConfig(
        agent_id=args.agent,
        rpc_url=args.rpc,
        poll_interval_s=args.poll,
        enable_tee=not args.no_tee,
        expected_tee_signing_addresses=frozenset(args.expected_tee_signer),
    )).start()


if __name__ == "__main__":
    main()
