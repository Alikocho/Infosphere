"""
server.py
=========
Flask game server for Infosphere human play.

Keeps full game state in memory. Exposes a REST API that the browser
calls to read state and submit actions. Serves the single-page game UI.

Usage:
    # Human plays Red vs heuristic Blue
    python server.py --human red --scenario election

    # Human plays Blue vs heuristic Red
    python server.py --human blue --scenario election

    # Human vs Human (two browser windows / tabs)
    python server.py --human both --scenario alliance

    # Human vs Claude LLM (requires ANTHROPIC_API_KEY)
    python server.py --human red --opponent claude --scenario health

    # Choose port
    python server.py --human red --port 5001
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request, send_from_directory

from env.world import Team, World
from env.actions import Action, ActionType, ACTION_COSTS
from env.observation import ObservationBuilder
from engine.engine import InfosphereEngine, WinCondition
from agents.agents import (
    HeuristicRedAgent, HeuristicBlueAgent,
    RandomRedAgent, RandomBlueAgent, BaseAgent,
)
from scenarios.scenarios import SCENARIOS

app = Flask(__name__, static_folder="static")

# ─────────────────────────────────────────────────────────────────────────────
# Global game state (one game per server instance)
# ─────────────────────────────────────────────────────────────────────────────

class GameState:
    def __init__(self):
        self.engine:   Optional[InfosphereEngine] = None
        self.world:    Optional[World]            = None
        self.config:   dict                       = {}
        self.human_team: Optional[Team]           = None   # None = both human
        self.pending_red_actions:  list[Action]   = []
        self.pending_blue_actions: list[Action]   = []
        self.red_submitted:  bool = False
        self.blue_submitted: bool = False
        self.last_record:    Optional[dict] = None
        self.lock = threading.Lock()
        self.status: str = "waiting"   # waiting | red_turn | blue_turn | both_turn | animating | finished

G = GameState()


# ─────────────────────────────────────────────────────────────────────────────
# Human agent (collects actions submitted via API)
# ─────────────────────────────────────────────────────────────────────────────

class HumanAgent(BaseAgent):
    """Blocks until the browser submits actions via POST /action."""

    def __init__(self, team: Team, game_state: GameState, **kwargs):
        super().__init__(team=team, **kwargs)
        self.gs = game_state

    def act(self, obs):
        # The engine will call this; we return whatever was submitted
        if self.team == Team.RED:
            actions = list(self.gs.pending_red_actions)
            self.gs.pending_red_actions = []
            self.gs.red_submitted = False
        else:
            actions = list(self.gs.pending_blue_actions)
            self.gs.pending_blue_actions = []
            self.gs.blue_submitted = False
        return actions if actions else [Action(ActionType.PASS, self.agent_id)]


# ─────────────────────────────────────────────────────────────────────────────
# Game initialisation
# ─────────────────────────────────────────────────────────────────────────────

def build_ai_agent(team: Team, opponent_type: str, primary_narrative: str, rng: random.Random):
    if opponent_type == "claude":
        try:
            from agents.claude_agent import ClaudeAgent
            return ClaudeAgent(
                agent_id=f"{team.value}-claude", team=team,
                primary_narrative=primary_narrative if team == Team.RED else None,
                verbose=False, rng=rng,
            )
        except Exception as e:
            print(f"Warning: Claude agent failed ({e}), falling back to heuristic")

    if team == Team.RED:
        if opponent_type == "random":
            return RandomRedAgent(agent_id="red-random", team=Team.RED,
                                  primary_narrative=primary_narrative, rng=rng)
        return HeuristicRedAgent(agent_id="red-heuristic", team=Team.RED,
                                 primary_narrative=primary_narrative, rng=rng)
    else:
        if opponent_type == "random":
            return RandomBlueAgent(agent_id="blue-random", team=Team.BLUE, rng=rng)
        return HeuristicBlueAgent(agent_id="blue-heuristic", team=Team.BLUE, rng=rng)


def init_game_explicit(scenario: str, red_type: str, blue_type: str, seed: int):
    """
    Initialise a game with full per-side agent control.
    red_type / blue_type: 'human' | 'heuristic' | 'random' | 'claude'
    """
    with G.lock:
        rng = random.Random(seed)
        world, primary_narrative = SCENARIOS[scenario]()

        # Build red
        if red_type == "human":
            red_agent = HumanAgent(team=Team.RED, agent_id="red-human",
                                   game_state=G, rng=rng)
        else:
            red_agent = build_ai_agent(Team.RED, red_type, primary_narrative, rng)

        # Build blue
        if blue_type == "human":
            blue_agent = HumanAgent(team=Team.BLUE, agent_id="blue-human",
                                    game_state=G, rng=rng)
        else:
            blue_agent = build_ai_agent(Team.BLUE, blue_type, primary_narrative, rng)

        # Set human_team for status tracking
        both_human = (red_type == "human" and blue_type == "human")
        if both_human:
            G.human_team = None   # None = both human
        elif red_type == "human":
            G.human_team = Team.RED
        elif blue_type == "human":
            G.human_team = Team.BLUE
        else:
            G.human_team = "ai_vs_ai"  # special flag

        G.engine = InfosphereEngine(
            world=world, red_agent=red_agent, blue_agent=blue_agent,
            win_condition=WinCondition(deadline=world.deadline),
            primary_narrative=primary_narrative,
            rng=rng, verbose=False,
        )
        G.world  = world
        G.config = {
            "scenario":          scenario,
            "human_team":        "both" if both_human
                                  else "red"  if red_type  == "human"
                                  else "blue" if blue_type == "human"
                                  else "none",
            "red_type":          red_type,
            "blue_type":         blue_type,
            "opponent":          blue_type if red_type == "human" else red_type,
            "seed":              seed,
            "primary_narrative": primary_narrative,
            "deadline":          world.deadline,
        }
        G.pending_red_actions  = []
        G.pending_blue_actions = []
        G.red_submitted  = False
        G.blue_submitted = False
        G.last_record    = None
        G.status = _current_status()

    # AI vs AI: kick off the first step automatically
    if G.config.get("human_team") == "none":
        threading.Timer(0.5, _run_step).start()


def init_game(scenario: str, human_team_str: str, opponent: str, seed: int):
    with G.lock:
        rng = random.Random(seed)
        world, primary_narrative = SCENARIOS[scenario]()

        # Determine which sides are human
        # red_is_human / blue_is_human determined by human_team_str AND opponent choice
        # The UI can send human_team_str='red' but with START_RED='heuristic' in AI vs AI mode
        # In that case we use the opponent arg for both sides
        red_is_human  = (human_team_str in ("red",  "both"))
        blue_is_human = (human_team_str in ("blue", "both"))

        if red_is_human:
            red_agent = HumanAgent(team=Team.RED, agent_id="red-human", game_state=G, rng=rng)
            G.human_team = Team.RED
        else:
            red_agent = build_ai_agent(Team.RED, opponent, primary_narrative, rng)
            G.human_team = None

        if blue_is_human:
            blue_agent = HumanAgent(team=Team.BLUE, agent_id="blue-human", game_state=G, rng=rng)
            if G.human_team == Team.RED:
                G.human_team = None  # both human → None means "both"
            else:
                G.human_team = Team.BLUE
        else:
            blue_agent = build_ai_agent(Team.BLUE, opponent, primary_narrative, rng)

        G.engine = InfosphereEngine(
            world=world, red_agent=red_agent, blue_agent=blue_agent,
            win_condition=WinCondition(deadline=world.deadline),
            primary_narrative=primary_narrative,
            rng=rng, verbose=False,
        )
        G.world   = world
        G.config  = {
            "scenario":          scenario,
            "human_team":        human_team_str,
            "opponent":          opponent,
            "seed":              seed,
            "primary_narrative": primary_narrative,
            "deadline":          world.deadline,
        }
        G.pending_red_actions  = []
        G.pending_blue_actions = []
        G.red_submitted  = False
        G.blue_submitted = False
        G.last_record    = None
        G.status = _current_status()


def _current_status() -> str:
    if G.engine is None:
        return "waiting"
    if G.engine.winner is not None:
        return "finished"
    ht = G.config.get("human_team", "both")
    if ht == "both":  return "both_turn"
    if ht == "red":   return "red_turn"
    if ht == "blue":  return "blue_turn"
    if ht == "none":  return "ai_turn"   # AI vs AI watch mode
    return "waiting"


# ─────────────────────────────────────────────────────────────────────────────
# State serialisation
# ─────────────────────────────────────────────────────────────────────────────

def serialise_world(world: World, engine: InfosphereEngine) -> dict:
    snap = world.snapshot()

    nodes = []
    for n in world.all_nodes():
        s = snap[n.id]
        nodes.append({
            "id":           n.id,
            "label":        n.label,
            "type":         n.node_type.value,
            "size":         n.size,
            "reach":        round(n.reach, 2),
            "beliefs":      {k: round(v, 3) for k, v in s["beliefs"].items()},
            "resilience":   round(s["resilience"], 3),
            "polarization": round(s["polarization"], 3),
            "neutrality":   round(s["neutrality"], 3),
            "captured":     s["captured"],
            "silenced":     s["silenced"],
            "monitored":    s["monitored"],
            "alert_level":  round(s["alert_level"], 1),
            "prebunked":    list(world.node(n.id).state.prebunked),
        })

    edges = []
    for e in world.all_edges():
        edges.append({
            "source":    e.source,
            "target":    e.target,
            "bandwidth": round(e.bandwidth, 2),
            "trust":     round(e.trust, 2),
            "monitored": e.monitored,
            "blocked":   e.blocked,
        })

    narratives = {
        nid: {
            "label":        n.label,
            "plausibility": n.plausibility,
            "virality":     n.virality,
            "stickiness":   n.stickiness,
            "divisiveness": n.divisiveness,
        }
        for nid, n in world.narratives.items()
    }

    nar_id = engine.primary_narrative
    return {
        "nodes":       nodes,
        "edges":       edges,
        "narratives":  narratives,
        "red_score":   round(world.red_score(nar_id) if nar_id else 0, 2),
        "blue_score":  round(world.blue_score(), 2),
        "polarization":round(world.polarization_index(), 3),
        "turn":        engine.turn,
        "deadline":    world.deadline,
        "winner":      engine.winner.value if engine.winner else None,
        "primary_narrative": nar_id,
    }


def serialise_record(rec) -> dict:
    def sa(a): return {"type": a.action_type.value, "target_node": a.target_node,
                       "target_edge": list(a.target_edge) if a.target_edge else None,
                       "narrative_id": a.narrative_id}
    def so(o): return {"status": o.status.value, "message": o.message,
                       "reward": round(o.reward, 2)}
    return {
        "turn":         rec.turn,
        "red_actions":  [sa(a) for a in rec.red_actions],
        "red_outcomes": [so(o) for o in rec.red_outcomes],
        "blue_actions": [sa(a) for a in rec.blue_actions],
        "blue_outcomes":[so(o) for o in rec.blue_outcomes],
        "red_score":    round(rec.red_score, 2),
        "blue_score":   round(rec.blue_score, 2),
        "polarization": round(rec.polarization, 3),
        "alerts":       rec.alerts,
    }


# ─────────────────────────────────────────────────────────────────────────────
# API routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "game.html")


@app.route("/api/config")
def api_config():
    return jsonify(G.config)


@app.route("/api/state")
def api_state():
    with G.lock:
        if G.engine is None:
            return jsonify({"status": "waiting"})
        state = serialise_world(G.world, G.engine)
        state["status"]        = G.status
        state["config"]        = G.config
        state["red_resources"] = G.engine.red_resources
        state["blue_resources"]= G.engine.blue_resources
        state["last_record"]   = G.last_record
        state["history_len"]   = len(G.engine.history)
        return jsonify(state)


@app.route("/api/action", methods=["POST"])
def api_action():
    """
    Submit one or more actions for a team.
    Body: { "team": "red"|"blue", "actions": [...], "end_turn": true }
    Each action: { "type": "...", "target_node": "...", "narrative_id": "...",
                   "target_edge": [...], "params": {...} }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    team_str = data.get("team")
    actions_raw = data.get("actions", [])
    end_turn = data.get("end_turn", True)

    with G.lock:
        if G.engine is None or G.engine.winner is not None:
            return jsonify({"error": "Game not active"}), 400

        # Validate and parse actions
        parsed = []
        budget = G.engine.red_resources if team_str == "red" else G.engine.blue_resources
        spent  = 0
        for ar in actions_raw:
            try:
                at = ActionType(ar["type"])
            except ValueError:
                return jsonify({"error": f"Unknown action type: {ar['type']}"}), 400
            cost = ACTION_COSTS.get(at, 0)
            if spent + cost > budget:
                break
            te = ar.get("target_edge")
            parsed.append(Action(
                action_type  = at,
                actor_id     = f"{team_str}-human",
                target_node  = ar.get("target_node"),
                target_edge  = tuple(te) if te else None,
                narrative_id = ar.get("narrative_id"),
                params       = ar.get("params", {}),
            ))
            spent += cost

        if team_str == "red":
            G.pending_red_actions = parsed
            if end_turn:
                G.red_submitted = True
        else:
            G.pending_blue_actions = parsed
            if end_turn:
                G.blue_submitted = True

    # If it's time to run the engine step, do it
    if _should_step():
        _run_step()

    return jsonify({"ok": True, "actions_queued": len(parsed)})


@app.route("/api/end_turn", methods=["POST"])
def api_end_turn():
    """Signal that the human is done with their turn (pass if no actions queued)."""
    data = request.get_json() or {}
    team_str = data.get("team", "red")
    with G.lock:
        if team_str == "red":
            G.red_submitted = True
            if not G.pending_red_actions:
                G.pending_red_actions = []
        else:
            G.blue_submitted = True
            if not G.pending_blue_actions:
                G.pending_blue_actions = []

    if _should_step():
        _run_step()

    return jsonify({"ok": True})


@app.route("/api/history")
def api_history():
    with G.lock:
        if G.engine is None:
            return jsonify([])
        return jsonify([serialise_record(r) for r in G.engine.history])


@app.route("/api/scenarios")
def api_scenarios():
    """Return metadata about all available scenarios."""
    from infosphere.scenarios.scenarios import SCENARIOS
    meta = {
        "election": {
            "label":       "Democratic Election",
            "description": "Spread election fraud disinformation before election day. High-reach social platforms are your entry points.",
            "deadline":    20,
            "nodes":       11,
            "primary_narrative": "stolen_election",
            "difficulty":  "Medium",
        },
        "alliance": {
            "label":       "Alliance Cohesion",
            "description": "Fracture a military coalition before a crisis summit. Drive wedges between wavering member states.",
            "deadline":    15,
            "nodes":       10,
            "primary_narrative": "alliance_betrayal",
            "difficulty":  "Hard",
        },
        "health": {
            "label":       "Public Health Emergency",
            "description": "Spread vaccine hesitancy during a vaccination campaign. Sticky narratives and a resilient health authority.",
            "deadline":    20,
            "nodes":       11,
            "primary_narrative": "vaccine_danger",
            "difficulty":  "Easy",
        },
    }
    return jsonify(meta)


@app.route("/api/new_game", methods=["POST"])
def api_new_game():
    data      = request.get_json() or {}
    scenario  = data.get("scenario",   "election")
    human     = data.get("human",      "red")
    seed      = data.get("seed",       random.randint(0, 9999))

    # red_agent / blue_agent let the UI specify each side independently
    red_agent_type  = data.get("red_agent",  None)
    blue_agent_type = data.get("blue_agent", None)
    opponent        = data.get("opponent",   "heuristic")

    # If explicit per-side types sent, override human/opponent logic
    if red_agent_type and blue_agent_type:
        init_game_explicit(scenario, red_agent_type, blue_agent_type, seed)
    else:
        init_game(scenario, human, opponent, seed)

    return jsonify({"ok": True, "seed": seed})


# ─────────────────────────────────────────────────────────────────────────────
# Engine step logic
# ─────────────────────────────────────────────────────────────────────────────

def _should_step() -> bool:
    """Check if we have everything needed to advance the engine."""
    with G.lock:
        if G.engine is None or G.engine.winner is not None:
            return False
        ht = G.config.get("human_team", "both")
        if ht == "none":   return True   # AI vs AI — always ready to step
        if ht == "both":   return G.red_submitted and G.blue_submitted
        if ht == "red":    return G.red_submitted
        if ht == "blue":   return G.blue_submitted
    return False


def _run_step():
    """Run one engine step. AI agent acts are called by engine internally."""
    with G.lock:
        if G.engine is None or G.engine.winner is not None:
            return
        G.status = "animating"

    # The engine calls agent.act() which for HumanAgent returns pending actions.
    # For AI agents it runs normally.
    rec = G.engine.step()

    with G.lock:
        if rec:
            G.last_record = serialise_record(rec)
        G.status = _current_status()
        # AI vs AI: auto-schedule next step with a brief delay
        if G.config.get("human_team") == "none" and G.engine and G.engine.winner is None:
            threading.Timer(0.7, _run_step).start()


# ─────────────────────────────────────────────────────────────────────────────
# Serve static files
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Infosphere Game Server")
    p.add_argument("--port",  type=int, default=5000)
    p.add_argument("--host",  default="127.0.0.1")
    # Legacy CLI args still work for scripted/headless use
    p.add_argument("--scenario",  default=None, choices=list(SCENARIOS.keys()))
    p.add_argument("--human",     default=None, choices=["red","blue","both"])
    p.add_argument("--opponent",  default=None, choices=["heuristic","random","claude"])
    p.add_argument("--seed",      type=int, default=None)
    args = p.parse_args()

    os.makedirs("static", exist_ok=True)

    print(f"\n{'═'*56}")
    print(f"  INFOSPHERE GAME SERVER")
    print(f"  URL : http://{args.host}:{args.port}")
    print(f"  Open your browser to start a game.")
    print(f"{'═'*56}\n")

    # If CLI args provided, skip the start screen and go straight in
    if args.scenario and args.human:
        seed = args.seed or random.randint(0, 9999)
        init_game(args.scenario, args.human, args.opponent or "heuristic", seed)
        print(f"  Auto-started: {args.scenario} | human={args.human} | seed={seed}\n")

    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
