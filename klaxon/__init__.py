"""Klaxon — decentralized exploit-protection swarm.

The CLI entry point lives in `klaxon.cli`. Implementation modules live one
directory up in `agents/` (kept there so the existing test suite, attacker
scripts, and direct `python agents/run_agent.py` invocations all keep
working). The CLI prepends `<repo>/agents` to sys.path before importing.
"""

__version__ = "0.1.0"
