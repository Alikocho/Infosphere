"""
tests/test_infosphere.py
========================
Core test suite. Covers world mechanics, action resolution,
belief propagation, win conditions, and all three scenarios.
"""

import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from infosphere.env.world import (
    World, PopulationNode, InfluenceEdge, Narrative, NodeType, Team
)
from infosphere.env.actions import Action, ActionType, ActionResolver, ACTION_COSTS
from infosphere.env.observation import ObservationBuilder
from infosphere.engine.engine import InfosphereEngine, WinCondition
from infosphere.agents.agents import (
    HeuristicRedAgent, HeuristicBlueAgent,
    RandomRedAgent, RandomBlueAgent,
)
from infosphere.scenarios.scenarios import (
    democratic_election, alliance_cohesion, public_health, SCENARIOS
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_world():
    """Two-node world for unit testing."""
    nar = Narrative("test_nar", label="Test Narrative",
                    plausibility=0.7, virality=0.6,
                    stickiness=0.4, divisiveness=0.5)
    w = World("Test", [nar], deadline=10)
    w.add_node(PopulationNode("source", "Source", NodeType.MEDIA,
                              size=1, reach=0.8, base_resilience=0.3))
    w.add_node(PopulationNode("target", "Target", NodeType.DEMOGRAPHIC,
                              size=2, reach=0.4, base_resilience=0.4))
    w.add_edge(InfluenceEdge("source", "target", bandwidth=0.9, trust=0.7))
    return w


@pytest.fixture
def rng():
    return random.Random(42)


# ── World ─────────────────────────────────────────────────────────────────────

class TestWorld:

    def test_node_belief_zero_sum(self, simple_world):
        """Beliefs must sum to ≤ 1.0 after setting multiple narratives."""
        nar2 = Narrative("nar2", label="Nar 2", plausibility=0.5,
                         virality=0.5, stickiness=0.5, divisiveness=0.3)
        simple_world.narratives["nar2"] = nar2
        node = simple_world.node("target")
        node.state.set_belief("test_nar", 0.7)
        node.state.set_belief("nar2", 0.7)
        assert node.state.total_belief() <= 1.001, "Beliefs must not exceed 1.0"

    def test_belief_propagation(self, simple_world):
        """Belief should spread from source to target after propagation.
        Both nodes need non-zero belief so the bounded-confidence gate passes
        (gap must be ≤ confidence_radius=0.4).
        """
        source = simple_world.node("source")
        target = simple_world.node("target")
        source.state.set_belief("test_nar", 0.6)
        target.state.set_belief("test_nar", 0.3)   # within 0.4 of source

        target_before = target.state.belief("test_nar")
        simple_world.propagate()
        target_after = target.state.belief("test_nar")

        assert target_after > target_before, "Belief should spread to connected node"

    def test_bounded_confidence_blocks_propagation(self, simple_world):
        """Nodes with very different beliefs should not update each other."""
        source = simple_world.node("source")
        target = simple_world.node("target")
        edge   = simple_world.edge("source", "target")

        # Source believes strongly, target believes something very different
        source.state.set_belief("test_nar", 0.9)
        target.state.set_belief("test_nar", 0.05)
        edge.confidence_radius = 0.2  # tight confidence window

        before = target.state.belief("test_nar")
        simple_world.propagate()
        after  = target.state.belief("test_nar")

        # With tight confidence radius and large belief gap, update should be minimal
        assert after - before < 0.05, "Bounded confidence should limit spread across large gap"

    def test_neutrality(self, simple_world):
        node = simple_world.node("target")
        node.state.set_belief("test_nar", 0.3)
        assert abs(node.state.neutrality() - 0.7) < 0.001

    def test_red_score_increases_with_belief(self, simple_world):
        score_before = simple_world.red_score("test_nar")
        simple_world.node("source").state.set_belief("test_nar", 0.9)
        score_after = simple_world.red_score("test_nar")
        assert score_after > score_before

    def test_blue_score_decreases_with_belief(self, simple_world):
        score_before = simple_world.blue_score()
        simple_world.node("source").state.set_belief("test_nar", 0.9)
        score_after = simple_world.blue_score()
        assert score_after < score_before

    def test_polarization_index(self, simple_world):
        simple_world.node("target").state.polarization = 0.5
        idx = simple_world.polarization_index()
        assert 0 <= idx <= 1

    def test_snapshot_roundtrip(self, simple_world):
        snap = simple_world.snapshot()
        assert "source" in snap
        assert "target" in snap
        assert "beliefs" in snap["source"]


# ── Actions ───────────────────────────────────────────────────────────────────

class TestActions:

    def test_inject_narrative_increases_belief(self, simple_world, rng):
        resolver = ActionResolver(rng=rng)
        node     = simple_world.node("target")
        before   = node.state.belief("test_nar")

        action = Action(ActionType.INJECT_NARRATIVE, "red",
                        target_node="target", narrative_id="test_nar")
        outcome = resolver.resolve(action, simple_world, Team.RED, resources=10)

        after = node.state.belief("test_nar")
        assert outcome.status.value in ("success", "detected")
        assert after >= before

    def test_prebunk_blocks_subsequent_injection(self, simple_world, rng):
        resolver = ActionResolver(rng=rng)
        # Prebunk first
        prebunk = Action(ActionType.PREBUNK, "blue",
                         target_node="target", narrative_id="test_nar")
        resolver.resolve(prebunk, simple_world, Team.BLUE, resources=10)

        # Now inject should be blocked
        inject = Action(ActionType.INJECT_NARRATIVE, "red",
                        target_node="target", narrative_id="test_nar")
        outcome = resolver.resolve(inject, simple_world, Team.RED, resources=10)
        assert outcome.status.value == "detected"

    def test_debunk_reduces_belief(self, simple_world, rng):
        resolver = ActionResolver(rng=rng)
        simple_world.node("target").state.set_belief("test_nar", 0.6)
        before = simple_world.node("target").state.belief("test_nar")

        debunk = Action(ActionType.DEBUNK, "blue",
                        target_node="target", narrative_id="test_nar")
        outcome = resolver.resolve(debunk, simple_world, Team.BLUE, resources=10)
        after = simple_world.node("target").state.belief("test_nar")

        assert after < before

    def test_elite_capture_marks_node(self, simple_world, rng):
        resolver = ActionResolver(rng=random.Random(1))  # seed for success
        # Try multiple times since it's probabilistic
        for seed in range(20):
            r = ActionResolver(rng=random.Random(seed))
            simple_world.node("source").state.captured = False
            action = Action(ActionType.ELITE_CAPTURE, "red", target_node="source")
            outcome = r.resolve(action, simple_world, Team.RED, resources=10)
            if outcome.status.value == "success":
                assert simple_world.node("source").state.captured
                return
        # At least one seed should succeed for a 0.9 reach node
        pytest.fail("Elite capture never succeeded in 20 attempts")

    def test_wedge_reduces_edge_trust(self, simple_world, rng):
        resolver = ActionResolver(rng=rng)
        edge     = simple_world.edge("source", "target")
        before   = edge.trust

        wedge = Action(ActionType.WEDGE, "red",
                       target_edge=("source", "target"), narrative_id="test_nar")
        outcome = resolver.resolve(wedge, simple_world, Team.RED, resources=10)
        assert edge.trust < before

    def test_insufficient_resources_fails(self, simple_world, rng):
        resolver = ActionResolver(rng=rng)
        action   = Action(ActionType.ELITE_CAPTURE, "red", target_node="source")
        outcome  = resolver.resolve(action, simple_world, Team.RED, resources=1)
        assert outcome.status.value == "failure"
        assert "Insufficient" in outcome.message

    def test_action_costs_are_positive(self):
        for at, cost in ACTION_COSTS.items():
            assert cost >= 0, f"Action {at} has negative cost"


# ── Engine ────────────────────────────────────────────────────────────────────

class TestEngine:

    def _make_engine(self, world, primary_narrative, rng, deadline=10):
        red  = HeuristicRedAgent(agent_id="red", team=Team.RED,
                                 primary_narrative=primary_narrative, rng=rng)
        blue = HeuristicBlueAgent(agent_id="blue", team=Team.BLUE, rng=rng)
        return InfosphereEngine(
            world=world, red_agent=red, blue_agent=blue,
            win_condition=WinCondition(deadline=deadline),
            primary_narrative=primary_narrative,
            rng=rng, verbose=False,
        )

    def test_turn_advances(self, simple_world, rng):
        eng = self._make_engine(simple_world, "test_nar", rng)
        assert eng.turn == 0
        eng.step()
        assert eng.turn == 1

    def test_engine_terminates_by_deadline(self, simple_world, rng):
        eng = self._make_engine(simple_world, "test_nar", rng, deadline=5)
        eng.run()
        assert eng.turn <= 5

    def test_history_recorded(self, simple_world, rng):
        eng = self._make_engine(simple_world, "test_nar", rng, deadline=3)
        eng.run()
        assert len(eng.history) == eng.turn
        for rec in eng.history:
            assert rec.red_actions is not None
            assert rec.blue_actions is not None

    def test_red_win_by_narrative_capture(self):
        """If red gets 60%+ belief in 50%+ of nodes, red wins."""
        nar = Narrative("nar", label="X", plausibility=0.9, virality=0.9,
                        stickiness=0.8, divisiveness=0.5)
        w = World("Capture Test", [nar], deadline=30)
        w.add_node(PopulationNode("a", "A", NodeType.DEMOGRAPHIC,
                                  size=1, reach=0.3, base_resilience=0.05))
        w.add_node(PopulationNode("b", "B", NodeType.DEMOGRAPHIC,
                                  size=1, reach=0.3, base_resilience=0.05))
        # Pre-seed near capture
        for nid in ["a", "b"]:
            w.node(nid).state.set_belief("nar", 0.58)

        rng  = random.Random(42)
        red  = HeuristicRedAgent(agent_id="r", team=Team.RED,
                                 primary_narrative="nar", rng=rng)
        blue = RandomBlueAgent(agent_id="b", team=Team.BLUE, rng=rng)
        eng  = InfosphereEngine(world=w, red_agent=red, blue_agent=blue,
                                win_condition=WinCondition(deadline=10),
                                primary_narrative="nar", rng=rng, verbose=False)
        eng.run()
        assert eng.winner == Team.RED

    def test_blue_wins_at_deadline(self, simple_world, rng):
        """If red fails to capture by deadline, blue wins."""
        # Make blue very strong: high resilience
        for node in simple_world.all_nodes():
            node.state.resilience = 0.99
        simple_world.node("source").state.prebunked.add("test_nar")
        simple_world.node("target").state.prebunked.add("test_nar")

        eng = self._make_engine(simple_world, "test_nar", rng, deadline=3)
        result = eng.run()
        assert result == Team.BLUE


# ── Scenarios ─────────────────────────────────────────────────────────────────

class TestScenarios:

    @pytest.mark.parametrize("scenario_fn,expected_nar", [
        (democratic_election, "stolen_election"),
        (alliance_cohesion,   "alliance_betrayal"),
        (public_health,       "vaccine_danger"),
    ])
    def test_scenario_loads(self, scenario_fn, expected_nar):
        world, primary_narrative = scenario_fn()
        assert primary_narrative == expected_nar
        assert len(list(world.all_nodes())) > 0
        assert len(world.all_edges()) > 0
        assert primary_narrative in world.narratives

    @pytest.mark.parametrize("name", list(SCENARIOS.keys()))
    def test_scenario_runs_to_completion(self, name):
        rng = random.Random(42)
        world, primary_narrative = SCENARIOS[name]()
        red  = HeuristicRedAgent(agent_id="r", team=Team.RED,
                                 primary_narrative=primary_narrative, rng=rng)
        blue = HeuristicBlueAgent(agent_id="b", team=Team.BLUE, rng=rng)
        eng  = InfosphereEngine(
            world=world, red_agent=red, blue_agent=blue,
            win_condition=WinCondition(deadline=world.deadline),
            primary_narrative=primary_narrative,
            rng=rng, verbose=False,
        )
        winner = eng.run()
        assert winner in (Team.RED, Team.BLUE)
        assert eng.turn > 0
        assert len(eng.history) == eng.turn

    @pytest.mark.parametrize("name", list(SCENARIOS.keys()))
    def test_scenario_deterministic(self, name):
        """Same seed should always produce same result."""
        results = []
        for _ in range(2):
            rng = random.Random(99)
            world, primary_narrative = SCENARIOS[name]()
            red  = HeuristicRedAgent(agent_id="r", team=Team.RED,
                                     primary_narrative=primary_narrative, rng=rng)
            blue = HeuristicBlueAgent(agent_id="b", team=Team.BLUE, rng=rng)
            eng  = InfosphereEngine(
                world=world, red_agent=red, blue_agent=blue,
                win_condition=WinCondition(deadline=world.deadline),
                primary_narrative=primary_narrative,
                rng=rng, verbose=False,
            )
            winner = eng.run()
            results.append((winner, eng.turn))
        assert results[0] == results[1], "Same seed should produce identical results"


# ── Observations ──────────────────────────────────────────────────────────────

class TestObservations:

    def test_red_cannot_see_prebunks(self, simple_world):
        simple_world.node("target").state.prebunked.add("test_nar")
        obs = ObservationBuilder.build_red_obs(simple_world, turn=1, resources=10)
        assert obs.nodes["target"].prebunked == []

    def test_blue_sees_all_nodes(self, simple_world):
        obs = ObservationBuilder.build_blue_obs(simple_world, turn=1, resources=5)
        assert set(obs.nodes.keys()) == {"source", "target"}

    def test_red_cannot_see_monitoring_status(self, simple_world):
        simple_world.node("target").state.monitored = True
        obs = ObservationBuilder.build_red_obs(simple_world, turn=1, resources=10)
        assert not obs.nodes["target"].monitored

    def test_blue_sees_alert_level(self, simple_world):
        simple_world.node("target").state.alert_level = 75
        obs = ObservationBuilder.build_blue_obs(simple_world, turn=1, resources=5)
        assert obs.nodes["target"].alert_level == 75

    def test_observation_resources_match(self, simple_world):
        obs = ObservationBuilder.build_red_obs(simple_world, turn=1, resources=7)
        assert obs.resources == 7
