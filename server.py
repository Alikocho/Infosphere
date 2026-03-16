"""
server.py — Infosphere Game Server
====================================
Flask server for browser-based human play.

Usage:
    python server.py --human red --scenario election
    python server.py --human blue --scenario health
    python server.py --human both --scenario alliance
    python server.py --human red --opponent claude   # needs ANTHROPIC_API_KEY
    python server.py --human red --port 5001
"""

import argparse
import json
import os
import random
import sys
import threading
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, send_from_directory

from infosphere.env.world import Team
from infosphere.env.actions import Action, ActionType, ACTION_COSTS
from infosphere.env.observation import ObservationBuilder
from infosphere.engine.engine import InfosphereEngine, WinCondition
from infosphere.agents.agents import (
    HeuristicRedAgent, HeuristicBlueAgent,
    RandomRedAgent, RandomBlueAgent, BaseAgent,
)
from infosphere.scenarios.scenarios import SCENARIOS

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "infosphere", "static")
app = Flask(__name__, static_folder=STATIC_DIR)


# ── Game state ────────────────────────────────────────────────────────────────

class GameState:
    def __init__(self):
        self.engine:  Optional[InfosphereEngine] = None
        self.world    = None
        self.config:  dict = {}
        self.pending_red_actions:  list = []
        self.pending_blue_actions: list = []
        self.red_submitted  = False
        self.blue_submitted = False
        self.last_record    = None
        self.lock = threading.Lock()
        self.status = "waiting"

G = GameState()


class HumanAgent(BaseAgent):
    def __init__(self, team: Team, game_state: GameState, **kwargs):
        super().__init__(team=team, **kwargs)
        self.gs = game_state

    def act(self, obs):
        if self.team == Team.RED:
            actions = list(self.gs.pending_red_actions)
            self.gs.pending_red_actions = []
            self.gs.red_submitted = False
        else:
            actions = list(self.gs.pending_blue_actions)
            self.gs.pending_blue_actions = []
            self.gs.blue_submitted = False
        return actions if actions else [Action(ActionType.PASS, self.agent_id)]


# ── Game initialisation ───────────────────────────────────────────────────────

def build_ai_agent(team, opponent_type, primary_narrative, rng):
    if opponent_type == "claude":
        try:
            from infosphere.agents.claude_agent import ClaudeAgent
            return ClaudeAgent(agent_id=f"{team.value}-claude", team=team,
                               primary_narrative=primary_narrative if team == Team.RED else None,
                               verbose=False, rng=rng)
        except Exception as e:
            print(f"Warning: Claude agent unavailable ({e}), falling back to heuristic")

    if team == Team.RED:
        cls = HeuristicRedAgent if opponent_type == "heuristic" else RandomRedAgent
        return cls(agent_id=f"red-{opponent_type}", team=Team.RED,
                   primary_narrative=primary_narrative, rng=rng)
    else:
        cls = HeuristicBlueAgent if opponent_type == "heuristic" else RandomBlueAgent
        return cls(agent_id=f"blue-{opponent_type}", team=Team.BLUE, rng=rng)


def init_game(scenario, human_team_str, opponent, seed):
    with G.lock:
        rng = random.Random(seed)
        world, primary_narrative = SCENARIOS[scenario]()

        if human_team_str == "red":
            red_agent  = HumanAgent(team=Team.RED,  agent_id="red-human",  game_state=G, rng=rng)
            blue_agent = build_ai_agent(Team.BLUE, opponent, primary_narrative, rng)
        elif human_team_str == "blue":
            red_agent  = build_ai_agent(Team.RED, opponent, primary_narrative, rng)
            blue_agent = HumanAgent(team=Team.BLUE, agent_id="blue-human", game_state=G, rng=rng)
        else:
            red_agent  = HumanAgent(team=Team.RED,  agent_id="red-human",  game_state=G, rng=rng)
            blue_agent = HumanAgent(team=Team.BLUE, agent_id="blue-human", game_state=G, rng=rng)

        G.engine = InfosphereEngine(
            world=world, red_agent=red_agent, blue_agent=blue_agent,
            win_condition=WinCondition(deadline=world.deadline),
            primary_narrative=primary_narrative,
            rng=rng, verbose=False,
        )
        G.world  = world
        G.config = {
            "scenario": scenario, "human_team": human_team_str,
            "opponent": opponent, "seed": seed,
            "primary_narrative": primary_narrative, "deadline": world.deadline,
        }
        G.pending_red_actions  = []
        G.pending_blue_actions = []
        G.red_submitted  = False
        G.blue_submitted = False
        G.last_record    = None
        G.status = _current_status()


def _current_status():
    if G.engine is None: return "waiting"
    if G.engine.winner is not None: return "finished"
    ht = G.config.get("human_team", "both")
    return {"red": "red_turn", "blue": "blue_turn", "both": "both_turn"}.get(ht, "waiting")


# ── Serialisation ─────────────────────────────────────────────────────────────

def serialise_world(world, engine):
    snap   = world.snapshot()
    nar_id = engine.primary_narrative
    nodes  = [{
        "id": n.id, "label": n.label, "type": n.node_type.value,
        "size": n.size, "reach": round(n.reach, 2),
        **{k: snap[n.id].get(k) for k in
           ["beliefs","resilience","polarization","neutrality",
            "captured","silenced","monitored","alert_level"]},
        "prebunked": list(world.node(n.id).state.prebunked),
    } for n in world.all_nodes()]

    edges = [{"source": e.source, "target": e.target,
               "bandwidth": round(e.bandwidth, 2), "trust": round(e.trust, 2),
               "monitored": e.monitored, "blocked": e.blocked}
             for e in world.all_edges()]

    return {
        "nodes": nodes, "edges": edges,
        "narratives": {nid: {"label": n.label, "plausibility": n.plausibility,
                             "virality": n.virality, "stickiness": n.stickiness,
                             "divisiveness": n.divisiveness}
                       for nid, n in world.narratives.items()},
        "red_score":    round(world.red_score(nar_id) if nar_id else 0, 2),
        "blue_score":   round(world.blue_score(), 2),
        "polarization": round(world.polarization_index(), 3),
        "turn":         engine.turn,
        "deadline":     world.deadline,
        "winner":       engine.winner.value if engine.winner else None,
        "primary_narrative": nar_id,
    }


def serialise_record(rec):
    sa = lambda a: {"type": a.action_type.value, "target_node": a.target_node,
                    "target_edge": list(a.target_edge) if a.target_edge else None,
                    "narrative_id": a.narrative_id}
    so = lambda o: {"status": o.status.value, "message": o.message,
                    "reward": round(o.reward, 2)}
    return {
        "turn": rec.turn,
        "red_actions":   [sa(a) for a in rec.red_actions],
        "red_outcomes":  [so(o) for o in rec.red_outcomes],
        "blue_actions":  [sa(a) for a in rec.blue_actions],
        "blue_outcomes": [so(o) for o in rec.blue_outcomes],
        "red_score":     round(rec.red_score, 2),
        "blue_score":    round(rec.blue_score, 2),
        "polarization":  round(rec.polarization, 3),
        "alerts":        rec.alerts,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "game.html")

@app.route("/api/config")
def api_config():
    return jsonify(G.config)

@app.route("/api/state")
def api_state():
    with G.lock:
        if G.engine is None:
            return jsonify({"status": "waiting"})
        state = serialise_world(G.world, G.engine)
        state.update({"status": G.status, "config": G.config,
                      "red_resources": G.engine.red_resources,
                      "blue_resources": G.engine.blue_resources,
                      "last_record": G.last_record,
                      "history_len": len(G.engine.history)})
        return jsonify(state)

@app.route("/api/action", methods=["POST"])
def api_action():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    team_str    = data.get("team")
    actions_raw = data.get("actions", [])
    end_turn    = data.get("end_turn", True)

    with G.lock:
        if G.engine is None or G.engine.winner is not None:
            return jsonify({"error": "Game not active"}), 400

        budget = G.engine.red_resources if team_str == "red" else G.engine.blue_resources
        parsed, spent = [], 0
        for ar in actions_raw:
            try:    at = ActionType(ar["type"])
            except ValueError: return jsonify({"error": f"Unknown action: {ar['type']}"}), 400
            cost = ACTION_COSTS.get(at, 0)
            if spent + cost > budget: break
            te = ar.get("target_edge")
            parsed.append(Action(action_type=at, actor_id=f"{team_str}-human",
                                 target_node=ar.get("target_node"),
                                 target_edge=tuple(te) if te else None,
                                 narrative_id=ar.get("narrative_id"),
                                 params=ar.get("params", {})))
            spent += cost

        if team_str == "red":
            G.pending_red_actions = parsed
            if end_turn: G.red_submitted = True
        else:
            G.pending_blue_actions = parsed
            if end_turn: G.blue_submitted = True

    if _should_step(): _run_step()
    return jsonify({"ok": True, "actions_queued": len(parsed)})

@app.route("/api/end_turn", methods=["POST"])
def api_end_turn():
    data     = request.get_json() or {}
    team_str = data.get("team", "red")
    with G.lock:
        if team_str == "red":
            G.red_submitted = True
        else:
            G.blue_submitted = True
    if _should_step(): _run_step()
    return jsonify({"ok": True})

@app.route("/api/history")
def api_history():
    with G.lock:
        if G.engine is None: return jsonify([])
        return jsonify([serialise_record(r) for r in G.engine.history])

@app.route("/api/new_game", methods=["POST"])
def api_new_game():
    data = request.get_json() or {}
    seed = data.get("seed", random.randint(0, 9999))
    init_game(
        data.get("scenario", G.config.get("scenario", "election")),
        data.get("human",    G.config.get("human_team", "red")),
        data.get("opponent", G.config.get("opponent",   "heuristic")),
        seed,
    )
    return jsonify({"ok": True, "seed": seed})


# ── Engine stepping ───────────────────────────────────────────────────────────

def _should_step():
    with G.lock:
        if G.engine is None or G.engine.winner is not None: return False
        ht = G.config.get("human_team", "both")
        if ht == "both":  return G.red_submitted and G.blue_submitted
        if ht == "red":   return G.red_submitted
        if ht == "blue":  return G.blue_submitted
    return False

def _run_step():
    with G.lock:
        if G.engine is None or G.engine.winner is not None: return
        G.status = "animating"
    rec = G.engine.step()
    with G.lock:
        if rec: G.last_record = serialise_record(rec)
        G.status = _current_status()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Infosphere Game Server")
    p.add_argument("--scenario", default="election", choices=list(SCENARIOS.keys()))
    p.add_argument("--human",    default="red",      choices=["red","blue","both"])
    p.add_argument("--opponent", default="heuristic",choices=["heuristic","random","claude"])
    p.add_argument("--seed",     type=int, default=random.randint(0, 9999))
    p.add_argument("--port",     type=int, default=5000)
    p.add_argument("--host",     default="127.0.0.1")
    args = p.parse_args()

    print(f"\n{'═'*56}")
    print(f"  INFOSPHERE GAME SERVER")
    print(f"  Scenario : {args.scenario.upper()}")
    print(f"  Human    : {args.human}")
    print(f"  Opponent : {args.opponent}")
    print(f"  Seed     : {args.seed}")
    print(f"  URL      : http://{args.host}:{args.port}")
    print(f"{'═'*56}\n")

    init_game(args.scenario, args.human, args.opponent, args.seed)
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
