"""
agents/agents.py
================
BaseAgent and heuristic agents for the Infosphere wargame.

HeuristicRedAgent  — doctrine-driven attacker
HeuristicBlueAgent — triage-driven defender
RandomRedAgent     — baseline random attacker
RandomBlueAgent    — baseline random defender
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Optional

from infosphere.env.world import Team
from infosphere.env.actions import Action, ActionType, ACTION_COSTS
from infosphere.env.observation import Observation


# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    def __init__(self, agent_id: str, team: Team, rng: random.Random = None):
        self.agent_id = agent_id
        self.team     = team
        self.rng      = rng or random.Random()

    @abstractmethod
    def act(self, obs: Observation) -> list[Action]:
        """Return a list of actions to take this turn (may be empty or multi-action)."""
        ...

    def _pass(self) -> list[Action]:
        return [Action(ActionType.PASS, self.agent_id)]

    def _affordable(self, action_type: ActionType, budget: int) -> bool:
        return ACTION_COSTS.get(action_type, 0) <= budget


# ─────────────────────────────────────────────────────────────────────────────
# RED agents
# ─────────────────────────────────────────────────────────────────────────────

class HeuristicRedAgent(BaseAgent):
    """
    Doctrine-driven attacker. Priority order:
    1. Elite capture on highest-reach uncaptured node
    2. Inject primary narrative into high-reach neutral nodes
    3. Amplify where belief is growing
    4. Wedge on edges between well-defended nodes
    5. Astroturf where belief is moderate
    6. Flood high-resilience blocking nodes
    """

    def __init__(self, primary_narrative: str, **kwargs):
        super().__init__(**kwargs)
        self.primary_narrative = primary_narrative
        self.turn = 0

    def act(self, obs: Observation) -> list[Action]:
        self.turn += 1
        actions = []
        budget  = obs.resources
        nar_id  = self.primary_narrative

        if not obs.nodes or nar_id not in obs.narratives:
            return self._pass()

        # Sort nodes by reach (highest first — most amplification value)
        nodes_by_reach = sorted(
            obs.nodes.values(), key=lambda n: -n.reach
        )

        # 1. Elite capture on highest-reach uncaptured node
        if self._affordable(ActionType.ELITE_CAPTURE, budget):
            for n in nodes_by_reach:
                if not n.captured and n.reach > 0.6:
                    actions.append(Action(
                        ActionType.ELITE_CAPTURE, self.agent_id,
                        target_node=n.node_id,
                    ))
                    budget -= ACTION_COSTS[ActionType.ELITE_CAPTURE]
                    break

        # 2. Inject into high-reach nodes with low belief
        for n in nodes_by_reach:
            if budget < ACTION_COSTS.get(ActionType.INJECT_NARRATIVE, 99):
                break
            bel = n.beliefs.get(nar_id, 0.0)
            if bel < 0.15 and not n.silenced:
                actions.append(Action(
                    ActionType.INJECT_NARRATIVE, self.agent_id,
                    target_node=n.node_id, narrative_id=nar_id,
                ))
                budget -= ACTION_COSTS[ActionType.INJECT_NARRATIVE]
                if budget <= 0:
                    break

        # 3. Amplify where belief is moderate and growing
        if budget >= ACTION_COSTS.get(ActionType.AMPLIFY, 99):
            for n in nodes_by_reach:
                bel = n.beliefs.get(nar_id, 0.0)
                if 0.2 <= bel < 0.6:
                    actions.append(Action(
                        ActionType.AMPLIFY, self.agent_id,
                        target_node=n.node_id, narrative_id=nar_id,
                    ))
                    budget -= ACTION_COSTS[ActionType.AMPLIFY]
                    if budget <= 0:
                        break

        # 4. Wedge on edges into high-resilience nodes
        if budget >= ACTION_COSTS.get(ActionType.WEDGE, 99):
            for edge in obs.edges:
                tgt = obs.node(edge["target"])
                if tgt and tgt.resilience > 0.6 and edge["trust"] > 0.5:
                    actions.append(Action(
                        ActionType.WEDGE, self.agent_id,
                        target_edge=(edge["source"], edge["target"]),
                        narrative_id=nar_id,
                    ))
                    budget -= ACTION_COSTS[ActionType.WEDGE]
                    break

        # 5. Astroturf mid-belief nodes late game
        if budget >= ACTION_COSTS.get(ActionType.ASTROTURF, 99) \
                and obs.turns_remaining <= 8:
            for n in nodes_by_reach:
                bel = n.beliefs.get(nar_id, 0.0)
                if 0.1 <= bel < 0.5:
                    actions.append(Action(
                        ActionType.ASTROTURF, self.agent_id,
                        target_node=n.node_id, narrative_id=nar_id,
                    ))
                    budget -= ACTION_COSTS[ActionType.ASTROTURF]
                    break

        # 6. Flood high-resilience obstacles
        if budget >= ACTION_COSTS.get(ActionType.FLOOD, 99):
            for n in nodes_by_reach:
                if n.resilience > 0.75 and n.beliefs.get(nar_id, 0.0) < 0.1:
                    actions.append(Action(
                        ActionType.FLOOD, self.agent_id,
                        target_node=n.node_id,
                    ))
                    budget -= ACTION_COSTS[ActionType.FLOOD]
                    break

        return actions if actions else self._pass()


class RandomRedAgent(BaseAgent):
    """Baseline: random actions up to budget."""

    def __init__(self, primary_narrative: str, **kwargs):
        super().__init__(**kwargs)
        self.primary_narrative = primary_narrative

    def act(self, obs: Observation) -> list[Action]:
        red_types = [
            ActionType.INJECT_NARRATIVE, ActionType.AMPLIFY,
            ActionType.WEDGE, ActionType.FLOOD, ActionType.ASTROTURF,
            ActionType.PASS,
        ]
        budget  = obs.resources
        actions = []
        nodes   = list(obs.nodes.keys())
        if not nodes:
            return self._pass()

        for _ in range(4):
            at = self.rng.choice(red_types)
            cost = ACTION_COSTS.get(at, 0)
            if cost > budget:
                continue
            node = self.rng.choice(nodes)
            nar  = self.rng.choice(list(obs.narratives.keys())) \
                   if obs.narratives else None
            actions.append(Action(at, self.agent_id,
                                  target_node=node, narrative_id=nar))
            budget -= cost
            if budget <= 0:
                break

        return actions if actions else self._pass()


# ─────────────────────────────────────────────────────────────────────────────
# BLUE agents
# ─────────────────────────────────────────────────────────────────────────────

class HeuristicBlueAgent(BaseAgent):
    """
    Triage-driven defender. Priority order:
    1. Prebunk high-reach nodes against highest-virality narrative
    2. Debunk nodes with dangerous belief levels
    3. Authenticate spoofed sources (high-alert nodes)
    4. Boost resilience on vulnerable high-reach nodes
    5. Monitor high-reach nodes not yet watched
    6. Strategic comms when red is spreading fast
    7. Platform action to silence captured nodes
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.turn = 0

    def act(self, obs: Observation) -> list[Action]:
        self.turn += 1
        actions = []
        budget  = obs.resources

        if not obs.nodes or not obs.narratives:
            return self._pass()

        # Find most dangerous narrative (highest total belief across graph)
        nar_id = max(
            obs.narratives.keys(),
            key=lambda nid: sum(n.beliefs.get(nid, 0.0)
                                for n in obs.nodes.values())
        )

        nodes_by_reach = sorted(
            obs.nodes.values(), key=lambda n: -n.reach
        )

        # 1. Prebunk high-reach nodes not yet inoculated
        if budget >= ACTION_COSTS.get(ActionType.PREBUNK, 99):
            for n in nodes_by_reach:
                if nar_id not in n.prebunked and n.beliefs.get(nar_id, 0.0) < 0.1:
                    actions.append(Action(
                        ActionType.PREBUNK, self.agent_id,
                        target_node=n.node_id, narrative_id=nar_id,
                    ))
                    budget -= ACTION_COSTS[ActionType.PREBUNK]
                    if budget <= 0:
                        break

        # 2. Debunk dangerous nodes (belief > 0.3)
        if budget >= ACTION_COSTS.get(ActionType.DEBUNK, 99):
            hot_nodes = sorted(
                [n for n in obs.nodes.values()
                 if n.beliefs.get(nar_id, 0.0) > 0.3],
                key=lambda n: -n.beliefs.get(nar_id, 0.0)
            )
            for n in hot_nodes[:2]:
                if budget < ACTION_COSTS[ActionType.DEBUNK]:
                    break
                actions.append(Action(
                    ActionType.DEBUNK, self.agent_id,
                    target_node=n.node_id, narrative_id=nar_id,
                ))
                budget -= ACTION_COSTS[ActionType.DEBUNK]

        # 3. Platform action on captured nodes
        if budget >= ACTION_COSTS.get(ActionType.PLATFORM_ACTION, 99):
            for n in nodes_by_reach:
                if n.captured:
                    actions.append(Action(
                        ActionType.PLATFORM_ACTION, self.agent_id,
                        target_node=n.node_id,
                    ))
                    budget -= ACTION_COSTS[ActionType.PLATFORM_ACTION]
                    break

        # 4. Boost resilience on high-reach vulnerable nodes
        if budget >= ACTION_COSTS.get(ActionType.BOOST_RESILIENCE, 99):
            for n in nodes_by_reach:
                if n.resilience < 0.5 and n.beliefs.get(nar_id, 0.0) < 0.2:
                    actions.append(Action(
                        ActionType.BOOST_RESILIENCE, self.agent_id,
                        target_node=n.node_id,
                    ))
                    budget -= ACTION_COSTS[ActionType.BOOST_RESILIENCE]
                    break

        # 5. Monitor unmonitored high-reach nodes
        if budget >= ACTION_COSTS.get(ActionType.MONITOR_EDGE, 99):
            for n in nodes_by_reach:
                if not n.monitored:
                    actions.append(Action(
                        ActionType.MONITOR_EDGE, self.agent_id,
                        target_node=n.node_id,
                    ))
                    budget -= ACTION_COSTS[ActionType.MONITOR_EDGE]
                    break

        # 6. Strategic comms if belief spreading fast (late game)
        if budget >= ACTION_COSTS.get(ActionType.STRATEGIC_COMMS, 99) \
                and obs.turns_remaining <= 6:
            top = max(obs.nodes.values(),
                      key=lambda n: n.beliefs.get(nar_id, 0.0), default=None)
            if top and top.beliefs.get(nar_id, 0.0) > 0.4:
                actions.append(Action(
                    ActionType.STRATEGIC_COMMS, self.agent_id,
                    target_node=top.node_id, narrative_id=nar_id,
                ))
                budget -= ACTION_COSTS[ActionType.STRATEGIC_COMMS]

        return actions if actions else self._pass()


class RandomBlueAgent(BaseAgent):
    """Baseline: random blue actions up to budget."""

    def act(self, obs: Observation) -> list[Action]:
        blue_types = [
            ActionType.PREBUNK, ActionType.DEBUNK,
            ActionType.BOOST_RESILIENCE, ActionType.MONITOR_EDGE,
            ActionType.PASS,
        ]
        budget  = obs.resources
        actions = []
        nodes   = list(obs.nodes.keys())
        if not nodes:
            return self._pass()

        for _ in range(3):
            at   = self.rng.choice(blue_types)
            cost = ACTION_COSTS.get(at, 0)
            if cost > budget:
                continue
            node = self.rng.choice(nodes)
            nar  = self.rng.choice(list(obs.narratives.keys())) \
                   if obs.narratives else None
            actions.append(Action(at, self.agent_id,
                                  target_node=node, narrative_id=nar))
            budget -= cost
            if budget <= 0:
                break

        return actions if actions else self._pass()
