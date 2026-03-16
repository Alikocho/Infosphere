"""
env/actions.py
==============
Action space for the Infosphere wargame.

Red  actions: inject, amplify, spoof_source, wedge, elite_capture, flood, astroturf
Blue actions: prebunk, debunk, boost_resilience, authenticate, monitor_edge,
              platform_action, alliance_signal, strategic_comms, pass

Each action is resolved by the ActionResolver against the World,
returning an Outcome with effects, reward, and status.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from infosphere.env.world import World, Team, Narrative


# ─────────────────────────────────────────────────────────────────────────────
# Action types
# ─────────────────────────────────────────────────────────────────────────────

class ActionType(Enum):
    # ── RED ──────────────────────────────────────────────────────────────────
    INJECT_NARRATIVE  = "inject_narrative"   # seed narrative into a node
    AMPLIFY           = "amplify"            # accelerate spread of narrative in node
    SPOOF_SOURCE      = "spoof_source"       # make messaging appear from trusted node
    WEDGE             = "wedge"              # degrade trust on an edge
    ELITE_CAPTURE     = "elite_capture"      # compromise high-reach node's output
    FLOOD             = "flood"              # saturate node with noise
    ASTROTURF         = "astroturf"          # manufacture grassroots belief signal

    # ── BLUE ─────────────────────────────────────────────────────────────────
    PREBUNK           = "prebunk"            # inoculate node against a narrative
    DEBUNK            = "debunk"             # counter active narrative in a node
    BOOST_RESILIENCE  = "boost_resilience"   # strengthen node's resistance
    AUTHENTICATE      = "authenticate"       # expose spoof, restore source trust
    MONITOR_EDGE      = "monitor_edge"       # watch an edge for anomalous traffic
    PLATFORM_ACTION   = "platform_action"    # reduce edge bandwidth / silence node
    ALLIANCE_SIGNAL   = "alliance_signal"    # strengthen trust on an edge
    STRATEGIC_COMMS   = "strategic_comms"    # broadcast counter-narrative widely

    # ── SHARED ───────────────────────────────────────────────────────────────
    PASS              = "pass"


# ─────────────────────────────────────────────────────────────────────────────
# Action & Outcome
# ─────────────────────────────────────────────────────────────────────────────

class OutcomeStatus(Enum):
    SUCCESS  = "success"
    FAILURE  = "failure"
    PARTIAL  = "partial"
    DETECTED = "detected"   # blue notices red action (raises alert)


@dataclass
class Action:
    action_type:  ActionType
    actor_id:     str
    target_node:  Optional[str]   = None   # primary target node id
    target_edge:  Optional[tuple] = None   # (src, dst) for edge actions
    narrative_id: Optional[str]   = None   # which narrative this action concerns
    params:       dict            = field(default_factory=dict)

    def __repr__(self):
        t = self.target_node or self.target_edge or "—"
        n = f"/{self.narrative_id}" if self.narrative_id else ""
        return f"Action({self.actor_id}::{self.action_type.value}→{t}{n})"


@dataclass
class Outcome:
    action:   Action
    status:   OutcomeStatus
    message:  str
    reward:   float = 0.0
    effects:  dict  = field(default_factory=dict)
    alerts:   list  = field(default_factory=list)

    def __repr__(self):
        return f"Outcome({self.status.value} r={self.reward:.2f} '{self.message[:40]}')"


# ─────────────────────────────────────────────────────────────────────────────
# Action costs (resource points per action)
# ─────────────────────────────────────────────────────────────────────────────

ACTION_COSTS: dict[ActionType, int] = {
    # RED
    ActionType.INJECT_NARRATIVE:  2,
    ActionType.AMPLIFY:           1,
    ActionType.SPOOF_SOURCE:      3,
    ActionType.WEDGE:             2,
    ActionType.ELITE_CAPTURE:     4,
    ActionType.FLOOD:             2,
    ActionType.ASTROTURF:         3,
    # BLUE
    ActionType.PREBUNK:           2,
    ActionType.DEBUNK:            2,
    ActionType.BOOST_RESILIENCE:  2,
    ActionType.AUTHENTICATE:      2,
    ActionType.MONITOR_EDGE:      1,
    ActionType.PLATFORM_ACTION:   3,
    ActionType.ALLIANCE_SIGNAL:   2,
    ActionType.STRATEGIC_COMMS:   4,
    ActionType.PASS:              0,
}


# ─────────────────────────────────────────────────────────────────────────────
# Action Resolver
# ─────────────────────────────────────────────────────────────────────────────

class ActionResolver:
    """
    Resolves Actions against the World, applying effects and returning Outcomes.
    All probability rolls use the provided rng for reproducibility.
    """

    def __init__(self, rng: random.Random = None):
        self.rng = rng or random.Random()

    def resolve(self, action: Action, world: World,
                team: Team, resources: int) -> Outcome:
        """Main dispatch."""
        cost = ACTION_COSTS.get(action.action_type, 0)
        if cost > resources:
            return Outcome(
                action  = action,
                status  = OutcomeStatus.FAILURE,
                message = f"Insufficient resources ({resources} < {cost} needed).",
                reward  = -0.1,
            )

        handler = {
            # RED
            ActionType.INJECT_NARRATIVE: self._inject_narrative,
            ActionType.AMPLIFY:          self._amplify,
            ActionType.SPOOF_SOURCE:     self._spoof_source,
            ActionType.WEDGE:            self._wedge,
            ActionType.ELITE_CAPTURE:    self._elite_capture,
            ActionType.FLOOD:            self._flood,
            ActionType.ASTROTURF:        self._astroturf,
            # BLUE
            ActionType.PREBUNK:          self._prebunk,
            ActionType.DEBUNK:           self._debunk,
            ActionType.BOOST_RESILIENCE: self._boost_resilience,
            ActionType.AUTHENTICATE:     self._authenticate,
            ActionType.MONITOR_EDGE:     self._monitor_edge,
            ActionType.PLATFORM_ACTION:  self._platform_action,
            ActionType.ALLIANCE_SIGNAL:  self._alliance_signal,
            ActionType.STRATEGIC_COMMS:  self._strategic_comms,
            ActionType.PASS:             self._pass,
        }.get(action.action_type)

        if handler is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Unknown action.", reward=-0.1)

        outcome = handler(action, world)
        outcome.effects["cost"] = cost
        return outcome

    # ─── RED actions ──────────────────────────────────────────────────────────

    def _inject_narrative(self, action: Action, world: World) -> Outcome:
        node = world.node(action.target_node)
        nar  = world.narratives.get(action.narrative_id)
        if node is None or nar is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Invalid target or narrative.", reward=-0.1)

        # Prebunked nodes resist injection
        if nar.id in node.state.prebunked:
            detect_roll = self.rng.random()
            alert_gain  = 15.0
            node.state.alert_level = min(100, node.state.alert_level + alert_gain)
            return Outcome(
                action  = action,
                status  = OutcomeStatus.DETECTED,
                message = f"Injection of '{nar.label}' into {node.id} blocked by prebunk.",
                reward  = -0.5,
                effects = {"alert_delta": (action.target_node, alert_gain)},
                alerts  = [f"Blocked injection attempt on {node.id}"],
            )

        # Base injection amount scaled by plausibility and inverse resilience
        base   = nar.plausibility * (1.0 - node.state.resilience * 0.7)
        amount = max(0.05, min(0.35, base + self.rng.gauss(0, 0.05)))

        prev   = node.state.belief(nar.id)
        node.state.set_belief(nar.id, prev + amount)
        gained = node.state.belief(nar.id) - prev

        # Monitored node raises alert
        alerts = []
        if node.state.monitored:
            node.state.alert_level = min(100, node.state.alert_level + 20)
            alerts.append(f"Narrative injection detected on monitored node {node.id}")

        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Injected '{nar.label}' into {node.id} (+{gained:.2f} belief).",
            reward  = gained * 3.0,
            effects = {"belief_delta": (action.target_node, nar.id, gained)},
            alerts  = alerts,
        )

    def _amplify(self, action: Action, world: World) -> Outcome:
        node = world.node(action.target_node)
        nar  = world.narratives.get(action.narrative_id)
        if node is None or nar is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Invalid target or narrative.", reward=-0.1)

        current = node.state.belief(nar.id)
        if current < 0.05:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message=f"Narrative '{nar.label}' not present in {node.id}.",
                           reward=-0.1)

        # Amplify: temporarily boost node's reach for this narrative
        boost  = nar.virality * 0.3 * (1.0 - node.state.resilience * 0.5)
        amount = max(0.02, min(0.20, boost + self.rng.gauss(0, 0.03)))
        prev   = node.state.belief(nar.id)
        node.state.set_belief(nar.id, prev + amount)
        gained = node.state.belief(nar.id) - prev

        # Also boost outgoing edge bandwidth temporarily (effects applied by engine)
        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Amplified '{nar.label}' in {node.id} (+{gained:.2f}).",
            reward  = gained * 2.0,
            effects = {"amplify_node": (action.target_node, nar.id, 0.2)},
        )

    def _spoof_source(self, action: Action, world: World) -> Outcome:
        node   = world.node(action.target_node)
        spoof  = action.params.get("spoof_as")   # node id to impersonate
        nar    = world.narratives.get(action.narrative_id)
        if node is None or nar is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Invalid target or narrative.", reward=-0.1)

        spoof_node = world.node(spoof) if spoof else None
        trust_bonus = 0.2 if spoof_node else 0.0

        # Spoof injects with trust bonus but risks detection
        base   = nar.plausibility * (1.0 - node.state.resilience * 0.5) + trust_bonus
        amount = max(0.05, min(0.40, base + self.rng.gauss(0, 0.05)))
        prev   = node.state.belief(nar.id)
        node.state.set_belief(nar.id, prev + amount)
        gained = node.state.belief(nar.id) - prev

        # Higher detection chance
        alerts = []
        if node.state.monitored or self.rng.random() < 0.25:
            node.state.alert_level = min(100, node.state.alert_level + 30)
            alerts.append(f"Suspicious source activity detected at {node.id}")
            effects_extra = {"alert_delta": (action.target_node, 30)}
        else:
            effects_extra = {}

        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS if not alerts else OutcomeStatus.DETECTED,
            message = f"Spoofed '{nar.label}' into {node.id} as {spoof or 'unknown'} "
                      f"(+{gained:.2f}).",
            reward  = gained * 3.5 - (1.0 if alerts else 0.0),
            effects = {"belief_delta": (action.target_node, nar.id, gained),
                       **effects_extra},
            alerts  = alerts,
        )

    def _wedge(self, action: Action, world: World) -> Outcome:
        """Degrade trust on a specific edge, increasing inter-group polarization."""
        if action.target_edge is None:
            # Fall back to target_node: wedge all edges into/from it
            node = world.node(action.target_node)
            if node is None:
                return Outcome(action=action, status=OutcomeStatus.FAILURE,
                               message="No edge or node specified.", reward=-0.1)
            edges = [world.edge(src, action.target_node)
                     for src in world.graph.predecessors(action.target_node)
                     if world.edge(src, action.target_node)]
            if not edges:
                return Outcome(action=action, status=OutcomeStatus.FAILURE,
                               message=f"No incoming edges to {action.target_node}.",
                               reward=-0.1)
            edge = self.rng.choice(edges)
        else:
            edge = world.edge(*action.target_edge)
            if edge is None:
                return Outcome(action=action, status=OutcomeStatus.FAILURE,
                               message="Edge not found.", reward=-0.1)

        nar = world.narratives.get(action.narrative_id)
        div_bonus = nar.divisiveness * 0.3 if nar else 0.0
        trust_loss = 0.1 + div_bonus + self.rng.gauss(0, 0.02)
        trust_loss = max(0.05, min(0.30, trust_loss))

        old_trust   = edge.trust
        edge.trust  = max(0.0, edge.trust - trust_loss)

        # Increase polarization in target node
        target = world.node(edge.target)
        if target:
            target.state.polarization = min(1.0,
                target.state.polarization + trust_loss * 0.5)

        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Wedge on {edge.source}→{edge.target}: "
                      f"trust {old_trust:.2f}→{edge.trust:.2f}.",
            reward  = trust_loss * 2.0 + (trust_loss * div_bonus * 3.0),
            effects = {"trust_delta": (edge.source, edge.target, -trust_loss),
                       "polarization_delta": (edge.target, trust_loss * 0.5)},
        )

    def _elite_capture(self, action: Action, world: World) -> Outcome:
        node = world.node(action.target_node)
        if node is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Node not found.", reward=-0.1)
        if node.state.captured:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message=f"{node.id} already captured.", reward=-0.1)

        # High-reach nodes harder to capture
        capture_prob = max(0.3, 0.85 - node.reach * 0.4 - node.state.resilience * 0.3)
        if self.rng.random() < capture_prob:
            node.state.captured = True
            alerts = []
            if node.state.monitored:
                node.state.alert_level = min(100, node.state.alert_level + 40)
                alerts.append(f"Elite capture detected at {node.id}")
            return Outcome(
                action  = action,
                status  = OutcomeStatus.SUCCESS,
                message = f"Elite capture of {node.id} (reach={node.reach:.2f}). "
                          f"Node now amplifies red narratives.",
                reward  = node.reach * 5.0,
                effects = {"capture_node": action.target_node},
                alerts  = alerts,
            )
        else:
            node.state.alert_level = min(100, node.state.alert_level + 25)
            return Outcome(
                action  = action,
                status  = OutcomeStatus.FAILURE,
                message = f"Elite capture of {node.id} failed (too resilient).",
                reward  = -0.5,
                alerts  = [f"Suspicious activity around {node.id}"],
            )

    def _flood(self, action: Action, world: World) -> Outcome:
        """Saturate a node with noise — reduces its ability to process counter-narratives."""
        node = world.node(action.target_node)
        if node is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Node not found.", reward=-0.1)

        # Flood temporarily increases polarization and silences outbound influence
        pol_gain = 0.1 + self.rng.gauss(0, 0.02)
        node.state.polarization = min(1.0, node.state.polarization + pol_gain)
        # Reduce outbound influence by marking silenced for 1 turn
        node.state.silenced = True

        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Flooded {node.id}: silenced 1 turn, "
                      f"polarization +{pol_gain:.2f}.",
            reward  = pol_gain * 2.0,
            effects = {"flood_node": action.target_node,
                       "polarization_delta": (action.target_node, pol_gain)},
        )

    def _astroturf(self, action: Action, world: World) -> Outcome:
        """Manufacture apparent grassroots belief — injects with plausibility boost."""
        node = world.node(action.target_node)
        nar  = world.narratives.get(action.narrative_id)
        if node is None or nar is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Invalid target or narrative.", reward=-0.1)

        # Acts like inject but bypasses bounded confidence (appears organic)
        amount = max(0.05, min(0.25,
            nar.plausibility * 0.6 + self.rng.gauss(0, 0.04)))
        prev   = node.state.belief(nar.id)
        node.state.set_belief(nar.id, prev + amount)
        gained = node.state.belief(nar.id) - prev

        # High detection risk if monitored
        alerts = []
        if node.state.monitored and self.rng.random() < 0.4:
            node.state.alert_level = min(100, node.state.alert_level + 20)
            alerts.append(f"Inauthentic coordinated activity detected at {node.id}")

        return Outcome(
            action  = action,
            status  = OutcomeStatus.DETECTED if alerts else OutcomeStatus.SUCCESS,
            message = f"Astroturfed '{nar.label}' in {node.id} (+{gained:.2f}).",
            reward  = gained * 2.5,
            effects = {"belief_delta": (action.target_node, nar.id, gained)},
            alerts  = alerts,
        )

    # ─── BLUE actions ─────────────────────────────────────────────────────────

    def _prebunk(self, action: Action, world: World) -> Outcome:
        node = world.node(action.target_node)
        nar  = world.narratives.get(action.narrative_id)
        if node is None or nar is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Invalid target or narrative.", reward=-0.1)

        if nar.id in node.state.prebunked:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message=f"{node.id} already prebunked against '{nar.label}'.",
                           reward=-0.1)

        node.state.prebunked.add(nar.id)
        # Also slightly raise resilience
        node.state.resilience = min(1.0, node.state.resilience + 0.05)

        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Prebunked '{nar.label}' in {node.id}. "
                      f"Future injections blocked.",
            reward  = 1.5,
            effects = {"prebunk": (action.target_node, nar.id)},
        )

    def _debunk(self, action: Action, world: World) -> Outcome:
        node = world.node(action.target_node)
        nar  = world.narratives.get(action.narrative_id)
        if node is None or nar is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Invalid target or narrative.", reward=-0.1)

        current = node.state.belief(nar.id)
        if current < 0.05:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message=f"'{nar.label}' not present in {node.id}.",
                           reward=-0.1)

        # Stickiness resists debunking
        reduction = max(0.05, min(0.25,
            0.20 * (1.0 - nar.stickiness * 0.7) + self.rng.gauss(0, 0.03)))
        prev = current
        node.state.set_belief(nar.id, max(0.0, current - reduction))
        removed = prev - node.state.belief(nar.id)

        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Debunked '{nar.label}' in {node.id} (-{removed:.2f} belief).",
            reward  = removed * 3.0,
            effects = {"belief_delta": (action.target_node, nar.id, -removed)},
        )

    def _boost_resilience(self, action: Action, world: World) -> Outcome:
        node = world.node(action.target_node)
        if node is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Node not found.", reward=-0.1)

        gain = 0.10 + self.rng.gauss(0, 0.02)
        gain = max(0.05, min(0.20, gain))
        node.state.resilience = min(1.0, node.state.resilience + gain)

        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Boosted resilience of {node.id} (+{gain:.2f}).",
            reward  = gain * 2.0,
            effects = {"resilience_delta": (action.target_node, gain)},
        )

    def _authenticate(self, action: Action, world: World) -> Outcome:
        """Expose a spoofed source on an edge, restoring trust penalties."""
        node = world.node(action.target_node)
        if node is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Node not found.", reward=-0.1)

        # Find the lowest-trust incoming edge (likely the spoofed one)
        preds = list(world.graph.predecessors(node.id))
        if not preds:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message=f"No incoming edges to {node.id}.", reward=-0.1)

        edges = [world.edge(p, node.id) for p in preds if world.edge(p, node.id)]
        if not edges:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="No resolvable edges.", reward=-0.1)

        target_edge = min(edges, key=lambda e: e.trust)
        restore     = min(0.25, 0.7 - target_edge.trust)
        restore     = max(0.05, restore)
        target_edge.trust = min(1.0, target_edge.trust + restore)

        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Authenticated edge {target_edge.source}→{node.id}: "
                      f"trust +{restore:.2f}.",
            reward  = restore * 2.5,
            effects = {"trust_delta": (target_edge.source, node.id, restore)},
        )

    def _monitor_edge(self, action: Action, world: World) -> Outcome:
        if action.target_edge:
            edge = world.edge(*action.target_edge)
        else:
            node = world.node(action.target_node)
            if node is None:
                return Outcome(action=action, status=OutcomeStatus.FAILURE,
                               message="Node not found.", reward=-0.1)
            # Monitor the node itself
            node.state.monitored = True
            return Outcome(
                action  = action,
                status  = OutcomeStatus.SUCCESS,
                message = f"Monitoring node {node.id}.",
                reward  = 0.5,
                effects = {"monitor_node": action.target_node},
            )

        if edge is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Edge not found.", reward=-0.1)
        edge.monitored = True
        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Monitoring edge {edge.source}→{edge.target}.",
            reward  = 0.5,
            effects = {"monitor_edge": (edge.source, edge.target)},
        )

    def _platform_action(self, action: Action, world: World) -> Outcome:
        """Reduce bandwidth on an edge or silence a node."""
        if action.target_edge:
            edge = world.edge(*action.target_edge)
            if edge is None:
                return Outcome(action=action, status=OutcomeStatus.FAILURE,
                               message="Edge not found.", reward=-0.1)
            reduction   = 0.3 + self.rng.gauss(0, 0.05)
            reduction   = max(0.1, min(0.5, reduction))
            edge.bandwidth = max(0.0, edge.bandwidth - reduction)
            return Outcome(
                action  = action,
                status  = OutcomeStatus.SUCCESS,
                message = f"Reduced bandwidth on {edge.source}→{edge.target} "
                          f"(-{reduction:.2f}).",
                reward  = reduction * 2.0,
                effects = {"bandwidth_delta": (edge.source, edge.target, -reduction)},
            )

        node = world.node(action.target_node)
        if node is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Node not found.", reward=-0.1)
        node.state.silenced = True
        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Platform action: {node.id} silenced for 1 turn.",
            reward  = 1.0,
            effects = {"silence_node": action.target_node},
        )

    def _alliance_signal(self, action: Action, world: World) -> Outcome:
        if action.target_edge is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Edge required for alliance_signal.", reward=-0.1)
        edge = world.edge(*action.target_edge)
        if edge is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Edge not found.", reward=-0.1)

        gain = 0.10 + self.rng.gauss(0, 0.02)
        gain = max(0.05, min(0.20, gain))
        edge.trust = min(1.0, edge.trust + gain)

        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Alliance signal on {edge.source}→{edge.target}: "
                      f"trust +{gain:.2f}.",
            reward  = gain * 2.0,
            effects = {"trust_delta": (edge.source, edge.target, gain)},
        )

    def _strategic_comms(self, action: Action, world: World) -> Outcome:
        """Broadcast counter-narrative to all neighbors of target node."""
        node = world.node(action.target_node)
        nar  = world.narratives.get(action.narrative_id)
        if node is None or nar is None:
            return Outcome(action=action, status=OutcomeStatus.FAILURE,
                           message="Invalid target or narrative.", reward=-0.1)

        # Debunk in target + all direct neighbors
        targets   = [node] + world.neighbors(action.target_node)
        total_rem = 0.0
        for t in targets:
            current = t.state.belief(nar.id)
            if current < 0.05:
                continue
            reduction = max(0.02, min(0.15,
                0.12 * (1.0 - nar.stickiness * 0.6) + self.rng.gauss(0, 0.02)))
            t.state.set_belief(nar.id, max(0.0, current - reduction))
            total_rem += current - t.state.belief(nar.id)

        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = f"Strategic comms against '{nar.label}' across "
                      f"{len(targets)} nodes (-{total_rem:.2f} total).",
            reward  = total_rem * 3.0,
            effects = {"strategic_comms": (action.target_node, nar.id, total_rem)},
        )

    def _pass(self, action: Action, world: World) -> Outcome:
        return Outcome(
            action  = action,
            status  = OutcomeStatus.SUCCESS,
            message = "Pass.",
            reward  = 0.0,
        )
