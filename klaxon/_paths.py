"""Path + env helpers shared across CLI subcommands."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
AXL_DIR = REPO_ROOT / "axl"
CONTRACTS_DIR = REPO_ROOT / "contracts"
DEPLOYMENTS_DIR = CONTRACTS_DIR / "deployments"
KEEPERHUB_DIR = REPO_ROOT / "keeperhub"
OG_COMPUTE_DIR = REPO_ROOT / "og-compute"
MANIFESTS_DIR = REPO_ROOT / "manifests"
RUNTIME_DIR = REPO_ROOT / ".klaxon" / "run"  # PID files, log dest


def ensure_runtime_dir() -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR


def add_agents_to_path() -> None:
    """Make `from finding import Finding` style imports inside agents/ work."""
    p = str(AGENTS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def load_dotenv() -> dict[str, str]:
    """Best-effort .env reader. No 3rd-party dotenv dep so the CLI installs
    cleanly without dragging in another package."""
    env: dict[str, str] = {}
    path = REPO_ROOT / ".env"
    if not path.exists():
        return env
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def env_value(key: str) -> str | None:
    return os.environ.get(key) or load_dotenv().get(key)
