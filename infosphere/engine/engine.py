"""
engine/engine.py
================
Orchestrates the Infosphere wargame:
  - Manages resources per turn (Red: 10/turn, Blue: 5/turn)
  - Calls agents for actions, resolves them, applies effects
  - Runs bounded-confidence belief propagation each turn
  - Checks win conditions
  - Records full history for replay
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from infosphere.env.world import World, Team
from infosphere.env.actions import Action, ActionType, ActionResolver, Outcome, ACTION_COSTS
from infosphere.agents.agents import BaseAgent


# ─────────────────────────────────────────────────────────────────────────────
# Resources
# ─────────────────────────────────────────────────────────────────────────────

RED_RESOURCES_PER_TURN  = 10
BLUE_RESOURCES_PER_TURN = 5


# ─────────────────────────────────────────────────────────────────────────────
# Win conditions
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WinCondition:
    """
    Checked after each turn.

    Red wins if:
      - narrative_capture_threshold % of nodes believe the target narrative
        at ≥ belief_threshold, OR
      - mean polarization index across graph ≥ polarization_win (destabilisation)

    Blue wins if:
      - Deadline passes without red winning
    """
    deadline:                  int   = 20
    belief_threshold:          float = 0.6    # node "captured" at this belief level
    narrative_capture_fraction:float = 0.5    # red needs this fraction of nodes
    polarization_win:          float = 0.75   # destabilisation win condition

    def check(self, world: World, turn: int) -> Optional[Team]:
        # Red: narrative capture across any active narrative
        total_nodes = len(list(world.all_nodes()))
        if total_nodes == 0:
            return None

        for nar_id in world.narratives:
            captured = world.capture_count(nar_id, self.belief_threshold)
            if captured / total_nodes >= self.narrative_capture_fraction:
                return Team.RED

        # Red: polarisation win
        if world.polarization_index() >= self.polarization_win:
            return Team.RED

        # Deadline: blue holds on
        if turn >= self.deadline:
            return Team.BLUE

        return None


# ─────────────────────────────────────────────────────────────────────────────
# Turn record
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TurnRecord:
    turn:          int
    red_actions:   list[Action]
    red_outcomes:  list[Outcome]
    blue_actions:  list[Action]
    blue_outcomes: list[Outcome]
    red_score:     float
    blue_score:    float
    polarization:  float
    alerts:        list[str]         = field(default_factory=list)
    world_snapshot: dict             = field(default_factory=dict)

    def summary(self) -> str:
        lines = [f"━━━ Turn {self.turn} ━━━"]
        for a, o in zip(self.red_actions, self.red_outcomes):
            lines.append(f"  🔴 {a} → {o}")
        for a, o in zip(self.blue_actions, self.blue_outcomes):
            lines.append(f"  🔵 {a} → {o}")
        lines.append(f"  Score  Red={self.red_score:.2f}  "
                     f"Blue={self.blue_score:.2f}  "
                     f"Polarization={self.polarization:.2f}")
        for alert in self.alerts:
            lines.append(f"  ⚠ {alert}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────

class InfosphereEngine:
    """
    Main game loop for the Infosphere wargame.

    Each turn:
      1. Replenish resources
      2. Red agent(s) act (may spend multiple actions up to resource budget)
      3. Blue agent(s) act (may spend multiple actions up to resource budget)
      4. Apply all effects
      5. Run belief propagation
      6. Clear per-turn flags (silenced nodes)
      7. Check win condition
      8. Record history
    """

    def __init__(
        self,
        world:         World,
        red_agent:     BaseAgent,
        blue_agent:    BaseAgent,
        win_condition: WinCondition = None,
        primary_narrative: str      = None,   # narrative id red is trying to spread
        rng:           random.Random = None,
        verbose:       bool = True,
    ):
        self.world         = world
        self.red_agent     = red_agent
        self.blue_agent    = blue_agent
        self.win_condition = win_condition or WinCondition(deadline=world.deadline)
        self.primary_narrative = primary_narrative or (
            list(world.narratives.keys())[0] if world.narratives else None
        )
        self.rng      = rng or random.Random()
        self.verbose  = verbose
        self.resolver = ActionResolver(rng=self.rng)

        self.turn:    int            = 0
        self.winner:  Optional[Team] = None
        self.history: list[TurnRecord] = []

        # Resources accumulate across turns (unused resources carry over, up to cap)
        self.red_resources:  int = RED_RESOURCES_PER_TURN
        self.blue_resources: int = BLUE_RESOURCES_PER_TURN
        self.resource_cap:   int = 20   # max banked resources

    # ── Core step ─────────────────────────────────────────────────────────────

    def step(self) -> Optional[TurnRecord]:
        if self.winner is not None:
            return None

        self.turn += 1

        # Replenish resources
        self.red_resources  = min(self.resource_cap,
                                  self.red_resources  + RED_RESOURCES_PER_TURN)
        self.blue_resources = min(self.resource_cap,
                                  self.blue_resources + BLUE_RESOURCES_PER_TURN)

        # Build observations
        from infosphere.env.observation import ObservationBuilder
        red_obs  = ObservationBuilder.build_red_obs(self.world, self.turn,
                                                     self.red_resources)
        blue_obs = ObservationBuilder.build_blue_obs(self.world, self.turn,
                                                      self.blue_resources)

        # Collect actions (agents may return a list for multi-action turns)
        red_actions  = self._collect_actions(self.red_agent,  red_obs,
                                              self.red_resources,  Team.RED)
        blue_actions = self._collect_actions(self.blue_agent, blue_obs,
                                              self.blue_resources, Team.BLUE)

        # Resolve red actions
        red_outcomes = []
        red_spent    = 0
        all_alerts   = []
        for action in red_actions:
            cost = ACTION_COSTS.get(action.action_type, 0)
            if red_spent + cost > self.red_resources:
                break
            outcome = self.resolver.resolve(action, self.world, Team.RED,
                                            self.red_resources - red_spent)
            self._apply_effects(outcome)
            red_outcomes.append(outcome)
            red_spent += cost
            all_alerts.extend(outcome.alerts)
        self.red_resources -= red_spent

        # Resolve blue actions
        blue_outcomes = []
        blue_spent    = 0
        for action in blue_actions:
            cost = ACTION_COSTS.get(action.action_type, 0)
            if blue_spent + cost > self.blue_resources:
                break
            outcome = self.resolver.resolve(action, self.world, Team.BLUE,
                                            self.blue_resources - blue_spent)
            self._apply_effects(outcome)
            blue_outcomes.append(outcome)
            blue_spent += cost
            all_alerts.extend(outcome.alerts)
        self.blue_resources -= blue_spent

        # Belief propagation
        self.world.propagate()

        # Clear per-turn flags
        for node in self.world.all_nodes():
            node.state.silenced = False

        # Scores
        nar_id    = self.primary_narrative
        red_score = self.world.red_score(nar_id) if nar_id else 0.0
        blue_score= self.world.blue_score()
        pol       = self.world.polarization_index()

        # Win check
        self.winner = self.win_condition.check(self.world, self.turn)

        # Record
        record = TurnRecord(
            turn          = self.turn,
            red_actions   = red_actions,
            red_outcomes  = red_outcomes,
            blue_actions  = blue_actions,
            blue_outcomes = blue_outcomes,
            red_score     = red_score,
            blue_score    = blue_score,
            polarization  = pol,
            alerts        = all_alerts,
            world_snapshot= self.world.snapshot(),
        )
        self.history.append(record)

        if self.verbose:
            print(record.summary())

        return record

    def run(self) -> Optional[Team]:
        while self.winner is None and self.turn < self.win_condition.deadline:
            self.step()
        return self.winner

    # ── Effect application ────────────────────────────────────────────────────

    def _apply_effects(self, outcome: Outcome):
        fx  = outcome.effects
        w   = self.world

        if "capture_node" in fx:
            node = w.node(fx["capture_node"])
            if node:
                node.state.captured = True

        if "flood_node" in fx:
            node = w.node(fx["flood_node"])
            if node:
                node.state.silenced = True

        if "silence_node" in fx:
            node = w.node(fx["silence_node"])
            if node:
                node.state.silenced = True

        if "monitor_node" in fx:
            node = w.node(fx["monitor_node"])
            if node:
                node.state.monitored = True

        if "monitor_edge" in fx:
            src, dst = fx["monitor_edge"]
            edge = w.edge(src, dst)
            if edge:
                edge.monitored = True

        if "trust_delta" in fx:
            src, dst, delta = fx["trust_delta"]
            edge = w.edge(src, dst)
            if edge:
                edge.trust = max(0.0, min(1.0, edge.trust + delta))

        if "bandwidth_delta" in fx:
            src, dst, delta = fx["bandwidth_delta"]
            edge = w.edge(src, dst)
            if edge:
                edge.bandwidth = max(0.0, min(1.0, edge.bandwidth + delta))

        if "polarization_delta" in fx:
            node_id, delta = fx["polarization_delta"]
            node = w.node(node_id)
            if node:
                node.state.polarization = min(1.0,
                    max(0.0, node.state.polarization + delta))

        if "resilience_delta" in fx:
            node_id, delta = fx["resilience_delta"]
            node = w.node(node_id)
            if node:
                node.state.resilience = min(1.0,
                    max(0.0, node.state.resilience + delta))

        if "prebunk" in fx:
            node_id, nar_id = fx["prebunk"]
            node = w.node(node_id)
            if node:
                node.state.prebunked.add(nar_id)

    # ── Multi-action collection ───────────────────────────────────────────────

    def _collect_actions(self, agent: BaseAgent, obs, resources: int,
                         team: Team) -> list[Action]:
        """
        Ask the agent for actions until it passes or runs out of resources.
        Agents return either a single Action or a list.
        Budget is enforced here.
        """
        raw = agent.act(obs)
        if isinstance(raw, list):
            return raw
        if isinstance(raw, Action):
            return [raw]
        return []

    # ── Final report ──────────────────────────────────────────────────────────

    def final_report(self) -> str:
        nar_id = self.primary_narrative
        lines  = [
            "=" * 60,
            f"FINAL REPORT — {self.world.name}",
            "=" * 60,
            f"Turns played    : {self.turn}",
            f"Winner          : {(self.winner or Team.BLUE).value.upper()}",
            f"Red final score : {self.world.red_score(nar_id) if nar_id else 0:.2f}",
            f"Blue final score: {self.world.blue_score():.2f}",
            f"Polarization    : {self.world.polarization_index():.2f}",
            "",
            "Node Beliefs:",
        ]
        for node in self.world.all_nodes():
            bel_str = "  ".join(
                f"{k}={v:.2f}" for k, v in sorted(node.state.beliefs.items())
                if v > 0.05
            ) or "neutral"
            lines.append(f"  {node.id:<20} pol={node.state.polarization:.2f}  "
                         f"res={node.state.resilience:.2f}  {bel_str}")
        lines.append("")
        lines.append("Action Breakdown:")
        red_counts:  dict[str, int] = {}
        blue_counts: dict[str, int] = {}
        for rec in self.history:
            for a in rec.red_actions:
                red_counts[a.action_type.value] = \
                    red_counts.get(a.action_type.value, 0) + 1
            for a in rec.blue_actions:
                blue_counts[a.action_type.value] = \
                    blue_counts.get(a.action_type.value, 0) + 1
        lines.append(f"  Red:  {red_counts}")
        lines.append(f"  Blue: {blue_counts}")
        return "\n".join(lines)
