"""
main.py — Infosphere CLI entrypoint
=====================================
Run AI vs AI simulations from the command line.

Usage:
    python main.py --scenario election
    python main.py --scenario alliance --red heuristic --blue random --seed 42
    python main.py --scenario health --quiet
    python main.py --list-scenarios
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infosphere.env.world import Team
from infosphere.engine.engine import InfosphereEngine, WinCondition
from infosphere.agents.agents import (
    HeuristicRedAgent, HeuristicBlueAgent,
    RandomRedAgent, RandomBlueAgent,
)
from infosphere.scenarios.scenarios import SCENARIOS

# Enable ANSI colors on Windows
if sys.platform == "win32":
    os.system("")

RED   = "\033[91m"; BLUE = "\033[94m"; GREEN = "\033[92m"
AMBER = "\033[93m"; DIM  = "\033[2m";  BOLD  = "\033[1m"; RESET = "\033[0m"

ICONS = {
    "inject_narrative":"💉","amplify":"📢","elite_capture":"👑","wedge":"⚔",
    "spoof_source":"🎭","astroturf":"🌱","flood":"🌊","prebunk":"🛡",
    "debunk":"❌","boost_resilience":"💪","strategic_comms":"📡",
    "platform_action":"🔇","alliance_signal":"🤝","authenticate":"🔍",
    "monitor_edge":"👁","pass":"—",
}


def build_agents(red_type, blue_type, primary_narrative, rng):
    red  = (HeuristicRedAgent if red_type  == "heuristic" else RandomRedAgent)(
        agent_id=f"red-{red_type}",   team=Team.RED,
        primary_narrative=primary_narrative, rng=rng)
    blue = (HeuristicBlueAgent if blue_type == "heuristic" else RandomBlueAgent)(
        agent_id=f"blue-{blue_type}", team=Team.BLUE, rng=rng)
    return red, blue


def print_turn(rec):
    print(f"\n{DIM}{'─'*64}{RESET}")
    print(f"{BOLD}Turn {rec.turn:02d}{RESET}  "
          f"Red={RED}{rec.red_score:.2f}{RESET}  "
          f"Blue={BLUE}{rec.blue_score:.2f}{RESET}  "
          f"Pol={AMBER}{rec.polarization:.2f}{RESET}")
    for a, o in zip(rec.red_actions, rec.red_outcomes):
        sc  = GREEN if o.status.value == "success" else (AMBER if o.status.value == "detected" else DIM)
        tgt = f" → {a.target_node}" if a.target_node else ""
        nar = f"/{a.narrative_id}" if a.narrative_id else ""
        print(f"  {RED}🔴{RESET} {ICONS.get(a.action_type.value,'?')} "
              f"{a.action_type.value.upper().replace('_',' ')}{tgt}{nar}  "
              f"{sc}{o.status.value}{RESET}")
    for a, o in zip(rec.blue_actions, rec.blue_outcomes):
        sc  = GREEN if o.status.value == "success" else (AMBER if o.status.value == "detected" else DIM)
        tgt = f" → {a.target_node}" if a.target_node else ""
        nar = f"/{a.narrative_id}" if a.narrative_id else ""
        print(f"  {BLUE}🔵{RESET} {ICONS.get(a.action_type.value,'?')} "
              f"{a.action_type.value.upper().replace('_',' ')}{tgt}{nar}  "
              f"{sc}{o.status.value}{RESET}")
    for alert in rec.alerts:
        print(f"  {AMBER}⚠  {alert}{RESET}")


def run_game(args):
    rng = random.Random(args.seed)
    world, primary_narrative = SCENARIOS[args.scenario]()
    red, blue = build_agents(args.red, args.blue, primary_narrative, rng)
    deadline  = args.turns or world.deadline

    engine = InfosphereEngine(
        world=world, red_agent=red, blue_agent=blue,
        win_condition=WinCondition(deadline=deadline),
        primary_narrative=primary_narrative,
        rng=rng, verbose=False,
    )

    print(f"\n{BOLD}{'═'*64}{RESET}")
    print(f"  {BOLD}{RED}INFO{RESET}{BOLD}{BLUE}SPHERE{RESET}")
    print(f"  Scenario  : {BOLD}{args.scenario.upper()}{RESET}  ({world})")
    print(f"  Red       : {RED}{args.red}{RESET}  (10 res/turn)")
    print(f"  Blue      : {BLUE}{args.blue}{RESET}  (5 res/turn)")
    print(f"  Narrative : {primary_narrative}")
    print(f"  Deadline  : {deadline} turns")
    print(f"  Seed      : {args.seed}")
    print(f"{BOLD}{'═'*64}{RESET}\n")

    while engine.winner is None and engine.turn < deadline:
        rec = engine.step()
        if rec and not args.quiet:
            print_turn(rec)

    winner = engine.winner or Team.BLUE
    color  = RED if winner == Team.RED else BLUE
    print(f"\n{BOLD}{'═'*64}{RESET}")
    print(f"  {BOLD}{color}🏆 {winner.value.upper()} WINS{RESET}  at turn {engine.turn}")
    print(f"{BOLD}{'═'*64}{RESET}")
    print(engine.final_report())
    return engine


def main():
    p = argparse.ArgumentParser(
        description="Infosphere — Influence Operations Wargame",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --scenario election
  python main.py --scenario alliance --seed 99
  python main.py --scenario health --red random --blue heuristic --quiet
        """,
    )
    p.add_argument("--scenario", default="election", choices=list(SCENARIOS.keys()))
    p.add_argument("--red",      default="heuristic", choices=["heuristic","random"])
    p.add_argument("--blue",     default="heuristic", choices=["heuristic","random"])
    p.add_argument("--turns",    type=int, default=None)
    p.add_argument("--seed",     type=int, default=42)
    p.add_argument("--quiet",    action="store_true")
    p.add_argument("--list-scenarios", action="store_true")
    args = p.parse_args()

    if args.list_scenarios:
        for name, fn in SCENARIOS.items():
            w, nar = fn()
            print(f"  {name:<12} — {w}  primary={nar}")
        return

    run_game(args)


if __name__ == "__main__":
    main()
