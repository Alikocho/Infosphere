"""
scenarios/scenarios.py
======================
Three pre-built Infosphere scenarios.

  democratic_election()  — swing demographics, media, social platforms
  alliance_cohesion()    — coalition states, opposition groups, deadline crisis
  public_health()        — regions, health authorities, skeptic communities
"""

from __future__ import annotations
from infosphere.env.world import World, PopulationNode, InfluenceEdge, NodeType, Narrative


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1: Democratic Election
# ─────────────────────────────────────────────────────────────────────────────

def democratic_election() -> tuple[World, str]:
    """
    Red tries to suppress swing-voter turnout or shift belief before election day.
    Blue defends institutional credibility.

    Nodes: 11 — swing demographics, legacy media, social platforms,
                 partisan blocs, election authority
    Primary narrative: 'stolen_election' (election fraud disinformation)
    Deadline: 20 turns (election day)
    """
    narratives = [
        Narrative("stolen_election",
                  label="The election is rigged",
                  plausibility=0.55, virality=0.70,
                  stickiness=0.65, divisiveness=0.80),
        Narrative("vote_suppression",
                  label="Your vote won't count",
                  plausibility=0.45, virality=0.55,
                  stickiness=0.50, divisiveness=0.60),
    ]

    world = World("Democratic Election", narratives, deadline=20)

    nodes = [
        PopulationNode("swing_rural",    "Rural Swing Voters",
                       NodeType.DEMOGRAPHIC, size=3, reach=0.4, base_resilience=0.35),
        PopulationNode("swing_suburban", "Suburban Swing Voters",
                       NodeType.DEMOGRAPHIC, size=4, reach=0.5, base_resilience=0.45),
        PopulationNode("youth_vote",     "Youth Voters",
                       NodeType.DEMOGRAPHIC, size=2, reach=0.6, base_resilience=0.40),
        PopulationNode("legacy_tv",      "Legacy Television",
                       NodeType.MEDIA,       size=1, reach=0.85, base_resilience=0.60),
        PopulationNode("online_news",    "Online News Aggregators",
                       NodeType.MEDIA,       size=1, reach=0.70, base_resilience=0.45),
        PopulationNode("social_alpha",   "Social Platform Alpha",
                       NodeType.PLATFORM,    size=1, reach=0.90, base_resilience=0.30),
        PopulationNode("social_beta",    "Social Platform Beta",
                       NodeType.PLATFORM,    size=1, reach=0.75, base_resilience=0.35),
        PopulationNode("partisan_right", "Right Partisan Bloc",
                       NodeType.DEMOGRAPHIC, size=2, reach=0.55, base_resilience=0.25),
        PopulationNode("partisan_left",  "Left Partisan Bloc",
                       NodeType.DEMOGRAPHIC, size=2, reach=0.55, base_resilience=0.30),
        PopulationNode("election_auth",  "Election Authority",
                       NodeType.INSTITUTION, size=1, reach=0.65, base_resilience=0.80),
        PopulationNode("foreign_amp",    "Foreign Amplifier",
                       NodeType.FOREIGN,     size=1, reach=0.50, base_resilience=0.20),
    ]
    for n in nodes:
        world.add_node(n)

    edges = [
        # Foreign → social platforms (high bandwidth, low trust)
        InfluenceEdge("foreign_amp",    "social_alpha",   bandwidth=0.8, trust=0.3),
        InfluenceEdge("foreign_amp",    "social_beta",    bandwidth=0.7, trust=0.3),
        # Social → demographics (high bandwidth)
        InfluenceEdge("social_alpha",   "swing_rural",    bandwidth=0.9, trust=0.5),
        InfluenceEdge("social_alpha",   "swing_suburban", bandwidth=0.8, trust=0.5),
        InfluenceEdge("social_alpha",   "youth_vote",     bandwidth=0.9, trust=0.6),
        InfluenceEdge("social_beta",    "swing_suburban", bandwidth=0.7, trust=0.5),
        InfluenceEdge("social_beta",    "partisan_right", bandwidth=0.8, trust=0.6),
        InfluenceEdge("social_beta",    "partisan_left",  bandwidth=0.7, trust=0.6),
        # Legacy TV → demographics (moderate bandwidth, higher trust)
        InfluenceEdge("legacy_tv",      "swing_rural",    bandwidth=0.7, trust=0.75),
        InfluenceEdge("legacy_tv",      "swing_suburban", bandwidth=0.6, trust=0.70),
        InfluenceEdge("online_news",    "youth_vote",     bandwidth=0.7, trust=0.55),
        InfluenceEdge("online_news",    "swing_suburban", bandwidth=0.6, trust=0.55),
        # Partisan blocs → swing (peer influence)
        InfluenceEdge("partisan_right", "swing_rural",    bandwidth=0.5, trust=0.50),
        InfluenceEdge("partisan_left",  "swing_suburban", bandwidth=0.4, trust=0.45),
        # Election authority → all (counter-narrative source)
        InfluenceEdge("election_auth",  "legacy_tv",      bandwidth=0.6, trust=0.80),
        InfluenceEdge("election_auth",  "online_news",    bandwidth=0.5, trust=0.75),
    ]
    for e in edges:
        world.add_edge(e)

    return world, "stolen_election"


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2: Alliance Cohesion
# ─────────────────────────────────────────────────────────────────────────────

def alliance_cohesion() -> tuple[World, str]:
    """
    Red tries to fracture a coalition before a crisis deadline
    by driving wedges between member states and amplifying opposition groups.

    Nodes: 10 — coalition states, domestic opposition, external adversary media
    Primary narrative: 'alliance_betrayal' (member states secretly defecting)
    Deadline: 15 turns (crisis summit)
    """
    narratives = [
        Narrative("alliance_betrayal",
                  label="Allies are secretly defecting",
                  plausibility=0.50, virality=0.60,
                  stickiness=0.55, divisiveness=0.85),
        Narrative("war_fatigue",
                  label="The cost of solidarity is too high",
                  plausibility=0.60, virality=0.65,
                  stickiness=0.60, divisiveness=0.70),
    ]

    world = World("Alliance Cohesion", narratives, deadline=15)

    nodes = [
        PopulationNode("state_anchor",  "Anchor State",
                       NodeType.ELITE,       size=3, reach=0.80, base_resilience=0.65),
        PopulationNode("state_waverer", "Wavering State",
                       NodeType.ELITE,       size=2, reach=0.60, base_resilience=0.35),
        PopulationNode("state_small",   "Small State",
                       NodeType.ELITE,       size=1, reach=0.40, base_resilience=0.30),
        PopulationNode("opposition_a",  "Opposition Movement A",
                       NodeType.DEMOGRAPHIC, size=2, reach=0.55, base_resilience=0.25),
        PopulationNode("opposition_b",  "Opposition Movement B",
                       NodeType.DEMOGRAPHIC, size=2, reach=0.50, base_resilience=0.20),
        PopulationNode("state_media_1", "State-Aligned Media 1",
                       NodeType.MEDIA,       size=1, reach=0.70, base_resilience=0.50),
        PopulationNode("state_media_2", "State-Aligned Media 2",
                       NodeType.MEDIA,       size=1, reach=0.65, base_resilience=0.45),
        PopulationNode("adversary_rt",  "Adversary Broadcaster",
                       NodeType.FOREIGN,     size=1, reach=0.75, base_resilience=0.15),
        PopulationNode("intl_press",    "International Press",
                       NodeType.MEDIA,       size=1, reach=0.80, base_resilience=0.55),
        PopulationNode("alliance_hq",   "Alliance Secretariat",
                       NodeType.INSTITUTION, size=1, reach=0.70, base_resilience=0.75),
    ]
    for n in nodes:
        world.add_node(n)

    edges = [
        InfluenceEdge("adversary_rt",  "opposition_a",   bandwidth=0.85, trust=0.35),
        InfluenceEdge("adversary_rt",  "opposition_b",   bandwidth=0.80, trust=0.30),
        InfluenceEdge("adversary_rt",  "state_media_2",  bandwidth=0.70, trust=0.25),
        InfluenceEdge("opposition_a",  "state_waverer",  bandwidth=0.60, trust=0.40),
        InfluenceEdge("opposition_b",  "state_small",    bandwidth=0.55, trust=0.35),
        InfluenceEdge("state_media_1", "state_anchor",   bandwidth=0.65, trust=0.70),
        InfluenceEdge("state_media_1", "state_waverer",  bandwidth=0.60, trust=0.65),
        InfluenceEdge("state_media_2", "state_waverer",  bandwidth=0.55, trust=0.40),
        InfluenceEdge("state_media_2", "state_small",    bandwidth=0.60, trust=0.35),
        InfluenceEdge("intl_press",    "state_anchor",   bandwidth=0.50, trust=0.65),
        InfluenceEdge("intl_press",    "state_waverer",  bandwidth=0.55, trust=0.60),
        InfluenceEdge("alliance_hq",   "state_anchor",   bandwidth=0.60, trust=0.80),
        InfluenceEdge("alliance_hq",   "state_waverer",  bandwidth=0.55, trust=0.75),
        InfluenceEdge("alliance_hq",   "state_small",    bandwidth=0.50, trust=0.70),
        InfluenceEdge("state_anchor",  "state_waverer",  bandwidth=0.45, trust=0.70,
                      confidence_radius=0.5),
        InfluenceEdge("state_anchor",  "state_small",    bandwidth=0.40, trust=0.65,
                      confidence_radius=0.5),
    ]
    for e in edges:
        world.add_edge(e)

    return world, "alliance_betrayal"


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3: Public Health Emergency
# ─────────────────────────────────────────────────────────────────────────────

def public_health() -> tuple[World, str]:
    """
    Red spreads health disinformation across a population during an emergency.
    Blue defends public health messaging.

    Nodes: 11 — geographic regions, health authorities, skeptic communities,
                 social platforms, medical professionals
    Primary narrative: 'vaccine_danger' (anti-vaccination disinformation)
    Deadline: 20 turns (vaccination campaign window)
    """
    narratives = [
        Narrative("vaccine_danger",
                  label="The vaccine is dangerous / experimental",
                  plausibility=0.50, virality=0.75,
                  stickiness=0.70, divisiveness=0.55),
        Narrative("coverup",
                  label="Authorities are hiding the truth",
                  plausibility=0.45, virality=0.65,
                  stickiness=0.65, divisiveness=0.70),
    ]

    world = World("Public Health Emergency", narratives, deadline=20)

    nodes = [
        PopulationNode("urban_pop",     "Urban Population",
                       NodeType.DEMOGRAPHIC, size=4, reach=0.55, base_resilience=0.50),
        PopulationNode("rural_pop",     "Rural Population",
                       NodeType.DEMOGRAPHIC, size=3, reach=0.40, base_resilience=0.35),
        PopulationNode("elderly",       "Elderly Demographic",
                       NodeType.DEMOGRAPHIC, size=2, reach=0.30, base_resilience=0.45),
        PopulationNode("health_auth",   "National Health Authority",
                       NodeType.INSTITUTION, size=1, reach=0.75, base_resilience=0.80),
        PopulationNode("med_community", "Medical Professionals",
                       NodeType.ELITE,       size=1, reach=0.70, base_resilience=0.75),
        PopulationNode("skeptic_network","Skeptic Community Network",
                       NodeType.DEMOGRAPHIC, size=2, reach=0.65, base_resilience=0.15),
        PopulationNode("social_health", "Health-Focused Social Media",
                       NodeType.PLATFORM,    size=1, reach=0.80, base_resilience=0.30),
        PopulationNode("mainstream_media","Mainstream Media",
                       NodeType.MEDIA,       size=1, reach=0.75, base_resilience=0.55),
        PopulationNode("alt_media",     "Alternative Media Ecosystem",
                       NodeType.MEDIA,       size=1, reach=0.60, base_resilience=0.20),
        PopulationNode("foreign_disinfo","Foreign Disinformation Network",
                       NodeType.FOREIGN,     size=1, reach=0.55, base_resilience=0.10),
        PopulationNode("local_leaders", "Local Community Leaders",
                       NodeType.ELITE,       size=2, reach=0.60, base_resilience=0.50),
    ]
    for n in nodes:
        world.add_node(n)

    edges = [
        InfluenceEdge("foreign_disinfo",  "alt_media",       bandwidth=0.85, trust=0.30),
        InfluenceEdge("foreign_disinfo",  "skeptic_network", bandwidth=0.80, trust=0.35),
        InfluenceEdge("alt_media",        "skeptic_network", bandwidth=0.80, trust=0.60),
        InfluenceEdge("alt_media",        "rural_pop",       bandwidth=0.70, trust=0.45),
        InfluenceEdge("skeptic_network",  "rural_pop",       bandwidth=0.75, trust=0.55),
        InfluenceEdge("skeptic_network",  "urban_pop",       bandwidth=0.50, trust=0.35),
        InfluenceEdge("social_health",    "urban_pop",       bandwidth=0.85, trust=0.50),
        InfluenceEdge("social_health",    "elderly",         bandwidth=0.60, trust=0.40),
        InfluenceEdge("social_health",    "skeptic_network", bandwidth=0.70, trust=0.40),
        InfluenceEdge("mainstream_media", "urban_pop",       bandwidth=0.70, trust=0.65),
        InfluenceEdge("mainstream_media", "elderly",         bandwidth=0.75, trust=0.70),
        InfluenceEdge("mainstream_media", "rural_pop",       bandwidth=0.55, trust=0.60),
        InfluenceEdge("health_auth",      "mainstream_media",bandwidth=0.65, trust=0.80),
        InfluenceEdge("health_auth",      "med_community",   bandwidth=0.70, trust=0.90),
        InfluenceEdge("med_community",    "local_leaders",   bandwidth=0.60, trust=0.80),
        InfluenceEdge("local_leaders",    "rural_pop",       bandwidth=0.65, trust=0.75),
        InfluenceEdge("local_leaders",    "elderly",         bandwidth=0.60, trust=0.80),
    ]
    for e in edges:
        world.add_edge(e)

    return world, "vaccine_danger"


SCENARIOS = {
    "election": democratic_election,
    "alliance": alliance_cohesion,
    "health":   public_health,
}
