"""
env/world.py
============
The core information environment.

Models a population as a directed graph of PopulationNodes connected by
InfluenceEdges. Each node holds a belief vector — one float per active
narrative — that evolves each turn via bounded-confidence (Detroit) propagation.

Narratives compete zero-sum: belief shares within a node sum to ≤ 1.0,
with the remainder representing "no strong belief" (epistemic neutrality).

Semantic narrative properties
------------------------------
  plausibility  — initial adoption rate when injected (0–1)
  virality      — spread velocity across edges (0–1)
  stickiness    — resistance to debunking; high = hard to reduce (0–1)
  divisiveness  — effectiveness of wedge actions on adjacent edges (0–1)
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import networkx as nx


# ─────────────────────────────────────────────────────────────────────────────
# Team
# ─────────────────────────────────────────────────────────────────────────────

class Team(Enum):
    RED  = "red"    # influence operator (attacker)
    BLUE = "blue"   # defender


# ─────────────────────────────────────────────────────────────────────────────
# Node types
# ─────────────────────────────────────────────────────────────────────────────

class NodeType(Enum):
    DEMOGRAPHIC    = "demographic"    # population segment
    MEDIA          = "media"          # news outlet / platform
    ELITE          = "elite"          # political / military / clergy leadership
    INSTITUTION    = "institution"    # government body, health authority, etc.
    PLATFORM       = "platform"       # social media platform
    FOREIGN        = "foreign"        # external state or diaspora actor


# ─────────────────────────────────────────────────────────────────────────────
# Narrative
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Narrative:
    """
    A narrative is a discrete claim or frame that can spread through the graph.

    Semantic properties (all 0.0–1.0):
      plausibility  — how readily nodes adopt it on first contact
      virality      — base spread rate per turn across edges
      stickiness    — resistance to debunking (high = slow to decay)
      divisiveness  — bonus effectiveness for wedge actions involving this narrative
    """
    id:           str
    label:        str
    plausibility: float = 0.5   # 0=implausible, 1=highly credible
    virality:     float = 0.5   # 0=inert, 1=highly contagious
    stickiness:   float = 0.5   # 0=fragile, 1=persistent
    divisiveness: float = 0.5   # 0=unifying frame, 1=maximally divisive

    def __repr__(self):
        return (f"Narrative({self.id} | "
                f"plaus={self.plausibility:.2f} viral={self.virality:.2f} "
                f"stick={self.stickiness:.2f} div={self.divisiveness:.2f})")


# ─────────────────────────────────────────────────────────────────────────────
# Node state (mutable per-turn)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NodeState:
    """Runtime mutable state for a population node."""
    beliefs:       dict[str, float]  = field(default_factory=dict)
    # beliefs[narrative_id] = 0.0–1.0; must sum to ≤ 1.0
    # remainder = epistemic neutrality

    resilience:    float = 0.5   # resistance to all incoming messaging (0–1)
    polarization:  float = 0.0   # internal fragmentation (0–1); grows with wedge actions
    captured:      bool  = False # red elite_capture: node now amplifies red narratives
    silenced:      bool  = False # blue platform_action: outbound bandwidth reduced
    prebunked:     set   = field(default_factory=set)   # narrative IDs inoculated
    monitored:     bool  = False # blue is watching this node
    alert_level:   float = 0.0   # blue's suspicion 0–100

    def belief(self, narrative_id: str) -> float:
        return self.beliefs.get(narrative_id, 0.0)

    def total_belief(self) -> float:
        return sum(self.beliefs.values())

    def neutrality(self) -> float:
        return max(0.0, 1.0 - self.total_belief())

    def set_belief(self, narrative_id: str, value: float):
        """Set belief, then renormalise to keep sum ≤ 1.0 (zero-sum competition)."""
        self.beliefs[narrative_id] = max(0.0, min(1.0, value))
        self._renormalise()

    def _renormalise(self):
        total = sum(self.beliefs.values())
        if total > 1.0:
            scale = 1.0 / total
            for k in self.beliefs:
                self.beliefs[k] *= scale


# ─────────────────────────────────────────────────────────────────────────────
# Population node
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PopulationNode:
    id:          str
    label:       str
    node_type:   NodeType
    size:        int   = 1      # relative population size (affects score weight)
    reach:       float = 0.5    # amplification: how strongly it influences neighbors
    base_resilience: float = 0.5  # starting resilience (reset on restore)
    state:       NodeState = field(default_factory=NodeState)

    def __post_init__(self):
        self.state.resilience = self.base_resilience

    def dominant_narrative(self) -> Optional[str]:
        """Returns the narrative ID with highest belief, or None if neutral."""
        if not self.state.beliefs:
            return None
        best = max(self.state.beliefs, key=lambda k: self.state.beliefs[k])
        return best if self.state.beliefs[best] > 0.1 else None

    def is_captured_by(self, narrative_id: str, threshold: float = 0.6) -> bool:
        return self.state.belief(narrative_id) >= threshold

    def __repr__(self):
        dom = self.dominant_narrative()
        return f"Node({self.id} [{self.node_type.value}] dominant={dom})"


# ─────────────────────────────────────────────────────────────────────────────
# Influence edge
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class InfluenceEdge:
    """Directed edge: source influences target."""
    source:      str
    target:      str
    bandwidth:   float = 1.0    # 0–1: volume of influence flow
    trust:       float = 0.7    # 0–1: credibility of source as seen by target
    monitored:   bool  = False  # blue is watching this edge
    blocked:     bool  = False  # blue platform_action severed this edge
    # bounded confidence threshold: nodes only update from neighbors
    # whose dominant belief is within `confidence_radius` of their own
    confidence_radius: float = 0.4


# ─────────────────────────────────────────────────────────────────────────────
# World (the full information environment)
# ─────────────────────────────────────────────────────────────────────────────

class World:
    """
    The information environment.

    Contains:
      - A directed graph of PopulationNodes and InfluenceEdges
      - The set of active Narratives
      - Belief propagation logic (bounded confidence / DeGroot hybrid)
      - Scoring
    """

    def __init__(self, name: str, narratives: list[Narrative],
                 deadline: int = 20):
        self.name       = name
        self.narratives = {n.id: n for n in narratives}
        self.deadline   = deadline
        self.graph: nx.DiGraph = nx.DiGraph()
        self._nodes: dict[str, PopulationNode] = {}
        self._edges: dict[tuple, InfluenceEdge] = {}
        self.turn   = 0

    # ── Construction ──────────────────────────────────────────────────────────

    def add_node(self, node: PopulationNode):
        self._nodes[node.id] = node
        self.graph.add_node(node.id)

    def add_edge(self, edge: InfluenceEdge):
        self._edges[(edge.source, edge.target)] = edge
        self.graph.add_edge(edge.source, edge.target)

    # ── Accessors ─────────────────────────────────────────────────────────────

    def node(self, node_id: str) -> Optional[PopulationNode]:
        return self._nodes.get(node_id)

    def edge(self, src: str, dst: str) -> Optional[InfluenceEdge]:
        return self._edges.get((src, dst))

    def all_nodes(self) -> list[PopulationNode]:
        return list(self._nodes.values())

    def all_edges(self) -> list[InfluenceEdge]:
        return list(self._edges.values())

    def neighbors(self, node_id: str) -> list[PopulationNode]:
        return [self._nodes[n] for n in self.graph.successors(node_id)
                if n in self._nodes]

    def predecessors(self, node_id: str) -> list[PopulationNode]:
        return [self._nodes[n] for n in self.graph.predecessors(node_id)
                if n in self._nodes]

    # ── Belief propagation ───────────────────────────────────────────────────

    def propagate(self):
        """
        One turn of belief propagation across all edges.

        Algorithm: bounded-confidence DeGroot hybrid.
          For each target node t, for each source s with edge s→t:
            1. Skip if edge is blocked or bandwidth=0
            2. Compute belief distance between s and t
            3. If distance ≤ confidence_radius (bounded confidence gate):
               t updates toward s's beliefs, weighted by:
                 - edge bandwidth × edge trust
                 - source reach (amplification)
                 - narrative virality
                 - inverse of target resilience
            4. Polarization increases if beliefs diverge across in-edges
            5. Renormalise beliefs (zero-sum competition)
        """
        # Snapshot beliefs before propagation (synchronous update)
        snapshot: dict[str, dict[str, float]] = {
            nid: dict(n.state.beliefs)
            for nid, n in self._nodes.items()
        }

        for target_id, target in self._nodes.items():
            if target.state.silenced:
                continue

            incoming_updates: dict[str, float] = {}

            for source in self.predecessors(target_id):
                edge = self.edge(source.id, target_id)
                if edge is None or edge.blocked:
                    continue

                src_beliefs = snapshot.get(source.id, {})
                tgt_beliefs = snapshot.get(target_id, {})

                # Bounded confidence gate: compare dominant beliefs
                src_dom_val = max(src_beliefs.values()) if src_beliefs else 0.0
                tgt_dom_val = max(tgt_beliefs.values()) if tgt_beliefs else 0.0
                belief_distance = abs(src_dom_val - tgt_dom_val)

                if belief_distance > edge.confidence_radius:
                    # Too far apart — no update, but polarization may rise
                    if belief_distance > 0.6:
                        target.state.polarization = min(
                            1.0, target.state.polarization + 0.02
                        )
                    continue

                # Influence weight for this edge
                influence = (
                    edge.bandwidth
                    * edge.trust
                    * source.reach
                    * (1.0 - target.state.resilience)
                )

                for nar_id, nar in self.narratives.items():
                    src_bel = src_beliefs.get(nar_id, 0.0)
                    tgt_bel = tgt_beliefs.get(nar_id, 0.0)

                    # Narrative virality modulates propagation speed
                    delta = influence * nar.virality * (src_bel - tgt_bel)

                    # Captured nodes amplify red narratives
                    if source.state.captured and src_bel > 0.3:
                        delta *= 1.5

                    incoming_updates[nar_id] = (
                        incoming_updates.get(nar_id, 0.0) + delta
                    )

            # Apply updates and renormalise
            for nar_id, delta in incoming_updates.items():
                current = target.state.beliefs.get(nar_id, 0.0)
                target.state.beliefs[nar_id] = max(0.0, current + delta * 0.1)

            target.state._renormalise()

    # ── Scoring ───────────────────────────────────────────────────────────────

    def red_score(self, narrative_id: str, threshold: float = 0.4) -> float:
        """
        Red score: weighted sum of belief in the target narrative across nodes,
        with bonus for nodes exceeding the capture threshold.
        """
        total = 0.0
        for node in self._nodes.values():
            bel = node.state.belief(narrative_id)
            weight = node.size * (1.0 + node.reach)
            total += bel * weight
            if bel >= threshold:
                total += weight * 0.5   # capture bonus
        return round(total, 3)

    def blue_score(self) -> float:
        """
        Blue score: weighted epistemic stability across the graph.
        High neutrality + low polarization = high blue score.
        """
        total = 0.0
        for node in self._nodes.values():
            weight   = node.size * (1.0 + node.reach)
            neutral  = node.state.neutrality()
            stability = 1.0 - node.state.polarization
            total += weight * (neutral * 0.7 + stability * 0.3)
        return round(total, 3)

    def polarization_index(self) -> float:
        """Mean polarization across all nodes — key metric for destabilisation wins."""
        if not self._nodes:
            return 0.0
        return round(sum(n.state.polarization for n in self._nodes.values())
                     / len(self._nodes), 3)

    def capture_count(self, narrative_id: str, threshold: float = 0.6) -> int:
        """Number of nodes with belief ≥ threshold for this narrative."""
        return sum(1 for n in self._nodes.values()
                   if n.state.belief(narrative_id) >= threshold)

    # ── Serialisation for replay UI ───────────────────────────────────────────

    def snapshot(self) -> dict:
        """Capture full world state for replay."""
        return {
            nid: {
                "beliefs":      dict(n.state.beliefs),
                "resilience":   round(n.state.resilience, 3),
                "polarization": round(n.state.polarization, 3),
                "captured":     n.state.captured,
                "silenced":     n.state.silenced,
                "monitored":    n.state.monitored,
                "alert_level":  round(n.state.alert_level, 1),
                "neutrality":   round(n.state.neutrality(), 3),
            }
            for nid, n in self._nodes.items()
        }

    def __repr__(self):
        return (f"World('{self.name}' "
                f"nodes={len(self._nodes)} "
                f"narratives={len(self.narratives)} "
                f"deadline={self.deadline})")
