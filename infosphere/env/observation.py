"""
env/observation.py  +  agents/agents.py  (combined for brevity)
================================================================
Observation: what each team sees each turn.
Agents: BaseAgent, HeuristicRedAgent, HeuristicBlueAgent, RandomRedAgent, RandomBlueAgent.
"""

# ── env/observation.py ────────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from infosphere.env.world import World, Team, PopulationNode


@dataclass
class NodeView:
    """What an agent can observe about a single population node."""
    node_id:      str
    node_type:    str
    label:        str
    size:         int
    reach:        float
    beliefs:      dict[str, float]    # narrative_id → belief level
    resilience:   float
    polarization: float
    neutrality:   float
    captured:     bool
    monitored:    bool
    silenced:     bool
    alert_level:  float
    prebunked:    list[str]           # narrative ids (blue sees all; red sees none)


@dataclass
class Observation:
    team:           Team
    turn:           int
    resources:      int
    nodes:          dict[str, NodeView]
    edges:          list[dict]                # {source, target, bandwidth, trust, monitored}
    narratives:     dict[str, dict]           # id → {label, plausibility, virality, ...}
    red_score:      float = 0.0
    blue_score:     float = 0.0
    polarization:   float = 0.0
    alerts:         list[str] = field(default_factory=list)
    deadline:       int = 20
    turns_remaining:int = 20

    def node(self, node_id: str) -> Optional[NodeView]:
        return self.nodes.get(node_id)

    def captured_nodes(self) -> list[str]:
        return [nid for nid, n in self.nodes.items() if n.captured]

    def high_belief_nodes(self, narrative_id: str,
                          threshold: float = 0.3) -> list[str]:
        return [nid for nid, n in self.nodes.items()
                if n.beliefs.get(narrative_id, 0.0) >= threshold]

    def vulnerable_nodes(self, narrative_id: str) -> list[str]:
        """Nodes with low belief (not yet captured) and high reach."""
        return sorted(
            [nid for nid, n in self.nodes.items()
             if n.beliefs.get(narrative_id, 0.0) < 0.3 and not n.captured],
            key=lambda nid: -self.nodes[nid].reach
        )


class ObservationBuilder:

    @staticmethod
    def build_red_obs(world: World, turn: int, resources: int) -> Observation:
        """
        Red sees: all node beliefs and types, but NOT blue's prebunk list,
        NOT blue's monitoring status (unless alert level is high).
        """
        nodes = {}
        for node in world.all_nodes():
            nodes[node.id] = NodeView(
                node_id      = node.id,
                node_type    = node.node_type.value,
                label        = node.label,
                size         = node.size,
                reach        = node.reach,
                beliefs      = dict(node.state.beliefs),
                resilience   = node.state.resilience,
                polarization = node.state.polarization,
                neutrality   = node.state.neutrality(),
                captured     = node.state.captured,
                monitored    = False,   # red can't see blue's monitoring
                silenced     = node.state.silenced,
                alert_level  = node.state.alert_level if node.state.alert_level > 50 else 0,
                prebunked    = [],      # red can't see prebunks
            )

        edges = [
            {"source": e.source, "target": e.target,
             "bandwidth": e.bandwidth, "trust": e.trust, "monitored": False}
            for e in world.all_edges() if not e.blocked
        ]

        nar_id = list(world.narratives.keys())[0] if world.narratives else None

        return Observation(
            team            = Team.RED,
            turn            = turn,
            resources       = resources,
            nodes           = nodes,
            edges           = edges,
            narratives      = {nid: {
                "label": n.label, "plausibility": n.plausibility,
                "virality": n.virality, "stickiness": n.stickiness,
                "divisiveness": n.divisiveness,
            } for nid, n in world.narratives.items()},
            red_score       = world.red_score(nar_id) if nar_id else 0.0,
            blue_score      = world.blue_score(),
            polarization    = world.polarization_index(),
            deadline        = world.deadline,
            turns_remaining = max(0, world.deadline - turn),
        )

    @staticmethod
    def build_blue_obs(world: World, turn: int, resources: int) -> Observation:
        """Blue sees everything including alerts, monitoring status, prebunks."""
        nodes = {}
        for node in world.all_nodes():
            nodes[node.id] = NodeView(
                node_id      = node.id,
                node_type    = node.node_type.value,
                label        = node.label,
                size         = node.size,
                reach        = node.reach,
                beliefs      = dict(node.state.beliefs),
                resilience   = node.state.resilience,
                polarization = node.state.polarization,
                neutrality   = node.state.neutrality(),
                captured     = node.state.captured,
                monitored    = node.state.monitored,
                silenced     = node.state.silenced,
                alert_level  = node.state.alert_level,
                prebunked    = list(node.state.prebunked),
            )

        edges = [
            {"source": e.source, "target": e.target,
             "bandwidth": e.bandwidth, "trust": e.trust, "monitored": e.monitored}
            for e in world.all_edges()
        ]

        nar_id = list(world.narratives.keys())[0] if world.narratives else None

        return Observation(
            team            = Team.BLUE,
            turn            = turn,
            resources       = resources,
            nodes           = nodes,
            edges           = edges,
            narratives      = {nid: {
                "label": n.label, "plausibility": n.plausibility,
                "virality": n.virality, "stickiness": n.stickiness,
                "divisiveness": n.divisiveness,
            } for nid, n in world.narratives.items()},
            red_score       = world.red_score(nar_id) if nar_id else 0.0,
            blue_score      = world.blue_score(),
            polarization    = world.polarization_index(),
            deadline        = world.deadline,
            turns_remaining = max(0, world.deadline - turn),
        )
