"""Klaxon CLI — `klaxon <subcommand>`.

Designed for operators (and for the demo video camera). Every subcommand
should produce output that reads well at 1080p with a screen recorder
running.
"""

from __future__ import annotations

import typer
from rich.console import Console

from klaxon import __version__
from klaxon.commands import doctor as doctor_cmd
from klaxon.commands import agents as agents_cmd
from klaxon.commands import findings as findings_cmd
from klaxon.commands import receipts as receipts_cmd
from klaxon.commands import attack as attack_cmd

console = Console()

app = typer.Typer(
    name="klaxon",
    help="Decentralized 24/7 exploit-protection swarm. Three bonded agents, one whistle.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

agents_app = typer.Typer(name="agents", help="Manage the 3-agent swarm (boot, stop, status).", no_args_is_help=True)
attack_app = typer.Typer(name="attack", help="Drive the demo exploit (oracle bump + drain) for recordings.", no_args_is_help=True)
app.add_typer(agents_app, name="agents")
app.add_typer(attack_app, name="attack")


@app.command()
def version() -> None:
    """Print Klaxon version."""
    console.print(f"klaxon [bold]{__version__}[/bold]")


@app.command()
def doctor() -> None:
    """Check the local environment is ready to run a rescue.

    Verifies: .env keys, AXL binary, deployer + agent + relayer balances,
    KeeperHub workflow reachability, 0G Compute provider acknowledgement,
    deployments file present, AXL nodes peering.
    """
    doctor_cmd.run()


@agents_app.command("up")
def agents_up(
    enable_tee: bool = typer.Option(True, "--tee/--no-tee", help="Use 0G Compute attestation."),
    enable_keeperhub: bool = typer.Option(True, "--keeperhub/--no-keeperhub", help="Submit pause via KeeperHub."),
) -> None:
    """Boot 3 AXL daemons + 3 Klaxon agent processes in the background.

    Writes PID files to .klaxon/run/. Logs land in the same directory.
    Use `klaxon agents status` to see what's running.
    """
    agents_cmd.up(enable_tee=enable_tee, enable_keeperhub=enable_keeperhub)


@agents_app.command("down")
def agents_down() -> None:
    """Stop everything `agents up` started."""
    agents_cmd.down()


@agents_app.command("status")
def agents_status() -> None:
    """Tabular status of the running swarm."""
    agents_cmd.status()


@app.command()
def findings(
    follow: bool = typer.Option(True, "--follow/--no-follow", "-f", help="Tail in real time."),
    lines: int = typer.Option(40, "--lines", "-n", help="Initial backlog to show."),
) -> None:
    """Pretty-print the live finding feed across all agents.

    Color codes DETECTED / ATTESTED / QUORUM / PAUSED beats so the camera
    sees the rescue happen in the same terminal as the agents are running.
    """
    findings_cmd.run(follow=follow, lines=lines)


@app.command()
def receipts(
    chain: str = typer.Option("base-sepolia", "--chain", help="base-sepolia or 0g-galileo."),
    blocks: int = typer.Option(2000, "--blocks", help="How many recent blocks to scan for events."),
) -> None:
    """Show recent rescues — every Guardian.FindingAttested + Paused event."""
    receipts_cmd.run(chain=chain, blocks=blocks)


@attack_app.command("bump")
def attack_bump(
    price: str = typer.Option("10000000000000000000", "--price", help="newPrice in wei. 1e19 = 10x at default oracle 1e18."),
) -> None:
    """Trigger the oracle manipulation tx (block N of the demo)."""
    attack_cmd.bump(price=price)


@attack_app.command("drain")
def attack_drain() -> None:
    """Trigger the borrow-against-revalued-collateral drain (block N+1)."""
    attack_cmd.drain()


@attack_app.command("reset")
def attack_reset() -> None:
    """Redeploy the protected pool so the rescue can be demoed again."""
    attack_cmd.reset()


if __name__ == "__main__":
    app()
