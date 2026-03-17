# INFOSPHERE
### A Multi-Agent Influence Operations Wargame

> *"The battlefield is everywhere."*

Infosphere is an asymmetric wargame that models information operations as a strategic contest between a **Red operator** spreading narratives through a population graph and a **Blue defender** maintaining epistemic stability. It is designed as a research platform for studying influence operation dynamics, testing competing theories of IO effectiveness, and training both human analysts and AI agents.

---

## What It Is

Infosphere treats influence operations as a partially observable, sequential two-player game. The environment is a **population graph** — nodes are demographic groups, media outlets, elite networks, social platforms, and institutions. Edges are trust-weighted influence channels. Each node carries a **belief vector** — a set of continuous values representing how strongly it holds each active narrative, constrained to sum to at most 1.0 (zero-sum competition between narratives).

Each turn, Red spends resources to inject, amplify, and spread narratives. Blue spends fewer resources to inoculate, debunk, and fortify the population. After both teams act, **bounded-confidence belief propagation** runs — nodes update their beliefs toward their neighbors, but only if those neighbors' beliefs are close enough to their own. This produces **echo chambers and filter bubbles emergently**, without special-casing them in the model.

Red has two paths to victory: capture a majority of nodes above a belief threshold (narrative dominance), or push overall polarization past a critical value (societal fracture). Blue wins by holding the line until the deadline passes.

---

## Design Choices

| Decision | Choice | Rationale |
|---|---|---|
| Belief propagation | Bounded confidence | Produces echo chambers emergently; maps to empirical network science |
| Narrative competition | Zero-sum within node | Belief share is finite — gains for one narrative come at cost to others |
| Semantic properties | Plausibility, virality, stickiness, divisiveness | Captures the mechanistic difference between narratives (a sticky narrative resists debunking; a divisive one powers wedge attacks) |
| Resource asymmetry | Red 10/turn, Blue 5/turn | Reflects empirical offense-defense asymmetry in IO; creates genuine strategic tension |
| Deadline | Fixed (per scenario) | Grounds the game in real-world IO timing — elections, summits, campaign windows |

---

## Downloads

The easiest way to play — no Python or terminal required.

| Platform | Download | Notes |
|---|---|---|
| **Mac** | `Infosphere-mac.zip` from [Releases](../../releases/latest) | Unzip and double-click `Infosphere.app`. On first launch, right-click → Open to bypass Gatekeeper. |
| **Windows** | `Infosphere.exe` from [Releases](../../releases/latest) | Double-click to run. Windows may show a SmartScreen warning — click "More info → Run anyway". |

Both open the game automatically in your default browser. No install, no setup.

---

## Installation (Python / Developer)

Infosphere requires Python 3.8+. The core simulation has no external dependencies. Human play requires Flask; RL training requires NumPy.

```bash
# Clone or download the infosphere/ folder
cd infosphere

# Core simulation — no dependencies needed
python3 main.py

# Human play via web UI — just run the server, configure in browser
pip3 install flask
python3 server.py

# RL training
pip3 install numpy
python3 train.py --team red --episodes 500
```

---

## Quick Start

```bash
# Run the Democratic Election scenario, heuristic vs heuristic
python3 main.py --scenario election

# All three scenarios
python3 main.py --scenario election
python3 main.py --scenario alliance
python3 main.py --scenario health

# Random red vs heuristic blue
python3 main.py --scenario election --red random --blue heuristic

# Quiet mode (final report only)
python3 main.py --scenario health --quiet

# List available scenarios
python3 main.py --list-scenarios
```

### Human Play (Web UI)

Start the server — no flags needed. Everything is configured in the browser:

```bash
pip3 install flask
python3 server.py
# Open http://localhost:5000
```

The start screen lets you pick a scenario and assign each team (Human, Heuristic AI, or Random AI) independently. To skip the start screen and jump straight into a specific configuration, CLI flags still work:

```bash
# Skip start screen: straight into election, you play Red
python3 server.py --human red --scenario election

# Choose a different port
python3 server.py --port 5001

# Play against Claude LLM (requires ANTHROPIC_API_KEY)
python3 server.py --human red --opponent claude --scenario election
```

### Generating a Battle Replay

Run a game and embed the results in a self-contained HTML file:

```bash
python3 generate_replay.py --scenario election --out election_replay.html
open election_replay.html
```

The replay visualizer shows the population graph with belief levels heat-mapped onto nodes, edge trust encoded as stroke weight, turn-by-turn action annotations, score and polarization charts, and a scrubber for stepping through the battle.

---

## Scenarios

### Democratic Election
A foreign influence operator attempts to spread election fraud disinformation before election day. Nodes include swing demographics (rural, suburban, youth), legacy television, online news aggregators, social platforms, partisan blocs, an election authority, and a foreign amplifier node that seeds the initial injection.

**Primary narrative:** `stolen_election` — "The election is rigged"  
**Secondary narrative:** `vote_suppression` — "Your vote won't count"  
**Deadline:** 20 turns  
**Key dynamics:** Social platforms have the highest reach and lowest resilience. Red's optimal play is elite capture of platform nodes in early turns, then amplify. Blue must prebunk before Red injects or the inoculation arrives too late.

### Alliance Cohesion
An adversary attempts to fracture a military coalition before a crisis summit. Nodes include anchor, wavering, and small member states, domestic opposition movements, state-aligned and international media, an adversary broadcaster, and an alliance secretariat.

**Primary narrative:** `alliance_betrayal` — "Allies are secretly defecting"  
**Secondary narrative:** `war_fatigue` — "The cost of solidarity is too high"  
**Deadline:** 15 turns  
**Key dynamics:** The wavering state is the critical node. Red's wedge actions are especially effective here because `alliance_betrayal` has maximum divisiveness (0.85). Blue must protect the trust edges between the anchor state and the secretariat while containing the adversary broadcaster.

### Public Health Emergency
A disinformation network spreads vaccine hesitancy during a vaccination campaign window. Nodes include urban and rural populations, the elderly, a national health authority, medical professionals, a skeptic community network, social and mainstream media, alternative media, a foreign disinformation source, and local community leaders.

**Primary narrative:** `vaccine_danger` — "The vaccine is dangerous / experimental"  
**Secondary narrative:** `coverup` — "Authorities are hiding the truth"  
**Deadline:** 20 turns  
**Key dynamics:** `vaccine_danger` has the highest virality (0.75) and stickiness (0.70) of any default narrative — once embedded, it resists debunking. The skeptic network and alternative media ecosystem form a self-reinforcing sub-graph. Blue's best path runs through local community leaders, who have high trust into the rural population and elderly demographics that are hardest to reach via mainstream channels.

---

## Narratives and Semantic Properties

Every narrative in Infosphere has four semantic properties that directly affect gameplay mechanics:

**Plausibility** (0–1) controls how readily nodes adopt the narrative on first injection. A highly plausible narrative (0.8+) can achieve significant belief levels in a single turn even in resilient nodes. A low-plausibility narrative needs repeated amplification to take hold.

**Virality** (0–1) sets the base propagation speed across edges during belief propagation. High-virality narratives spread rapidly between connected nodes each turn even without red intervention. A virality of 0.75 with a captured high-reach node can cascade across an entire graph in three turns.

**Stickiness** (0–1) determines resistance to debunking. A sticky narrative (0.7+) loses only 5–8% belief per successful debunk action. A fragile narrative (0.2) can be halved in a single turn of sustained Blue counter-messaging. Stickiness is the most important property for Blue's resource allocation — it determines whether debunking is worth the cost.

**Divisiveness** (0–1) multiplies the effectiveness of Red's `wedge` action and the polarization gained from contested beliefs across edges. A divisive narrative makes inter-group distrust compound faster, pushing the population toward Red's second win condition (societal fracture) even when Blue successfully contains belief spread.

---

## Action Space

### Red Actions (10 resources/turn)

| Action | Cost | Effect |
|---|---|---|
| `inject_narrative` | 2 | Seeds a narrative into a target node. Success scaled by plausibility × inverse resilience. Blocked by prebunk. |
| `amplify` | 1 | Boosts an existing narrative in a node. Requires belief > 5% already present. |
| `spoof_source` | 3 | Injects with trust bonus by impersonating a credible node. Higher detection risk. |
| `wedge` | 2 | Degrades trust on an edge. Effectiveness multiplied by narrative divisiveness. Increases polarization in target node. |
| `elite_capture` | 4 | Converts a high-reach node to amplify Red narratives. Probability penalised by reach and resilience. Game-changing if successful. |
| `flood` | 2 | Silences a node's outbound influence for 1 turn and increases polarization. Counters Blue's strategic comms. |
| `astroturf` | 3 | Manufactures organic-looking belief injection that bypasses bounded confidence filtering. |

### Blue Actions (5 resources/turn)

| Action | Cost | Effect |
|---|---|---|
| `prebunk` | 2 | Permanently inoculates a node against a specific narrative. Future injections fail and raise an alert. |
| `debunk` | 2 | Reduces belief in an active narrative. Effectiveness penalised by stickiness. |
| `boost_resilience` | 2 | Strengthens a node's resistance to all future messaging. |
| `authenticate` | 2 | Exposes a spoofed source, restoring trust on the lowest-trust incoming edge. |
| `monitor_edge` | 1 | Marks a node or edge as monitored. Red actions on monitored nodes trigger alerts and raise alert levels. |
| `platform_action` | 3 | Reduces edge bandwidth or silences a node for 1 turn. |
| `alliance_signal` | 2 | Increases trust on an edge. Counters Red's wedge. |
| `strategic_comms` | 4 | Debunks a narrative across a target node and all its immediate neighbors simultaneously. |

---

## Agent Types

### Heuristic Agents

**HeuristicRedAgent** follows IO doctrine: elite capture first (prioritising highest-reach nodes), then mass injection, then amplification, then wedges on high-resilience edges, then astroturfing in the final turns. It approximates the Internet Research Agency's known operational sequence.

**HeuristicBlueAgent** follows triage doctrine: prebunk high-reach nodes before Red reaches them, debunk actively spreading narratives, platform-action any captured nodes, boost resilience on vulnerable nodes, then monitor and strategic comms in the final turns.

### Random Agents

`RandomRedAgent` and `RandomBlueAgent` serve as statistical baselines. They spend their budgets on random legal actions. Useful for establishing lower-bound win rates and stress-testing the environment.

### RL Agents (coming)

PPO-trained agents using the same architecture as CyberWar. Feature vector encodes node belief states, resilience, polarization, and capture status. Action mask enforces legality. Trains against a frozen heuristic opponent.

### LLM Agent (coming)

Claude-backed agent using native tool calling, with a system prompt establishing IO doctrine and a structured observation delivered as markdown. Maintains conversation history across turns for cross-turn strategic memory.

---

## Human Play

Infosphere includes a browser-based game interface powered by a Flask server. When you open the game, a start screen lets you configure everything before play begins — no command-line flags required.

### Starting a Game

```bash
pip3 install flask
python3 server.py
```

Then open `http://localhost:5000`. The start screen appears automatically.

### Start Screen

The start screen has two sections. The top section shows three scenario cards — click one to select it. Each card shows the scenario name, deadline, difficulty rating, and a one-line description of the strategic situation.

The bottom section assigns each team independently. Red and Blue each have three options:

| Option | Description |
|---|---|
| **Human** | You control this side |
| **Heuristic AI** | Doctrine-driven rule-based agent |
| **Random AI** | Random legal actions — useful as a baseline opponent |

A status line below the team panel confirms your configuration and warns you if you select Human vs Human (hot-seat mode) or AI vs AI (watch mode). Click **Begin Operation** to start.

### Play Modes

**Human vs AI** — you control one side, the AI resolves its turn immediately after you submit yours. The game moves at your pace.

**Human vs Human** — both sides are human. After Red submits their turn the action panel switches to Blue's action set. Works best passing a single device, or with two browser windows open to the same URL.

**AI vs AI (watch mode)** — both sides are AI agents. The game plays itself automatically at roughly one turn per second while you watch the population graph update in real time. Good for observing heuristic agent strategies before playing yourself.

### Gameplay Loop

Each turn: select a narrative from the selector at the top of the action panel, click an action button, then click a target node on the map (the cursor changes and nodes glow gold when a target is needed). The action is queued with its resource cost deducted. Repeat until your budget is exhausted or you're done, then click **End Turn**. The engine resolves your actions, runs the AI turn if applicable, propagates beliefs across the graph, and returns the updated world state.

The map encodes state visually: node fill color shifts from cream to red as belief in the primary narrative grows, with the percentage printed inside nodes above 8%. Captured nodes show a dashed red halo. Edge thickness represents bandwidth; edge lightness represents trust. Your queued targets are outlined in gold so you can preview moves before committing.

When the game ends, the win overlay shows the result and a **New Game** button that returns you to the start screen.

### Server CLI Reference

```
python3 server.py [options]

  --port INT    Port to serve on (default: 5000)
  --host STR    Host to bind (default: 127.0.0.1)

  # Optional: skip the start screen and go straight into a game
  --scenario {election,alliance,health}
  --human {red,blue,both}
  --opponent {heuristic,random,claude}
```

---

## Architecture

```
infosphere/
├── main.py                  # CLI entrypoint (AI vs AI simulation)
├── server.py                # Flask game server for human play
├── generate_replay.py       # Self-contained HTML battle replay generator
│
├── env/
│   ├── world.py             # Population graph, nodes, edges, belief propagation
│   ├── actions.py           # Action space, resolver, outcome system
│   └── observation.py       # Partial observability: what each team sees
│
├── agents/
│   └── agents.py            # BaseAgent, HeuristicRed/Blue, RandomRed/Blue
│
├── engine/
│   └── engine.py            # Turn loop, resource management, win conditions
│
├── scenarios/
│   └── scenarios.py         # Democratic Election, Alliance Cohesion, Public Health
│
└── static/
    └── game.html            # Single-page game UI (served by Flask)
```

### Belief Propagation

Each turn, after both teams have acted, the world runs one step of bounded-confidence belief propagation. For each directed edge `s → t`:

1. If the edge is blocked or bandwidth is zero, skip.
2. Compute belief distance between `s` and `t` (distance between their dominant belief values).
3. If distance exceeds the edge's `confidence_radius` (default 0.4), no update occurs. If distance is large (>0.6), polarization increases in `t`.
4. Otherwise, `t` updates toward `s`'s beliefs, weighted by `bandwidth × trust × source_reach × (1 − target_resilience) × narrative_virality`.
5. Captured nodes amplify their outgoing influence by 1.5×.
6. After all edges are processed, each node's belief vector is renormalised (zero-sum constraint).

This is a synchronous (snapshot-based) update — all nodes read from the previous turn's state before any writes are applied.

### Resource System

Resources accumulate across turns (unused resources carry over) up to a cap of 20. This rewards strategic patience — banking resources to execute a multi-action burst in a critical turn. Red starts with 10/turn, Blue with 5/turn, reflecting the empirical offense-defense asymmetry in information operations.

### Win Conditions

Red wins if:
- The primary narrative exceeds 60% belief in 50%+ of nodes (narrative capture), or
- Mean polarization across the graph reaches 0.75 (societal fracture as a standalone win)

Blue wins if the deadline passes without either red condition being met.

---

## Research Questions

Infosphere is designed to be a platform for answering empirical questions about influence operation dynamics that are difficult or impossible to study in the real world:

**On offense-defense balance:**
- Under what resource ratios can Blue achieve a stable equilibrium?
- Does the answer change with graph topology (dense vs. sparse, high vs. low modularity)?

**On narrative design:**
- Which property — plausibility, virality, stickiness, or divisiveness — most determines Red's win rate?
- Is it better to run one high-quality narrative or two lower-quality ones?

**On defensive strategy:**
- Does prebunking beat debunking at the population level, or only in specific topologies?
- What is the optimal allocation of Blue's 5 resources across prebunk, debunk, resilience, and monitoring?

**On network structure:**
- What graph properties make a population structurally resilient versus structurally vulnerable?
- Do elite capture attacks (targeting high-reach nodes) outperform mass injection strategies?

**On AI agent behavior:**
- Do RL agents rediscover known IO doctrine (IRA tactics, Gerasimov-adjacent approaches), or find novel strategies?
- Does the LLM agent reason about bounded confidence dynamics and adjust its targeting accordingly?

---

## Extending Infosphere

### Adding a Scenario

```python
from env.world import World, PopulationNode, InfluenceEdge, NodeType, Narrative

def my_scenario() -> tuple[World, str]:
    narratives = [
        Narrative("my_narrative", label="...",
                  plausibility=0.6, virality=0.7,
                  stickiness=0.5, divisiveness=0.8),
    ]
    world = World("My Scenario", narratives, deadline=20)
    
    world.add_node(PopulationNode("node_a", "Group A",
        NodeType.DEMOGRAPHIC, size=3, reach=0.6, base_resilience=0.4))
    # ... add more nodes
    
    world.add_edge(InfluenceEdge("node_a", "node_b", bandwidth=0.8, trust=0.6))
    # ... add more edges
    
    return world, "my_narrative"
```

### Adding a Custom Agent

```python
from agents.agents import BaseAgent
from env.actions import Action, ActionType
from env.observation import Observation

class MyRedAgent(BaseAgent):
    def act(self, obs: Observation) -> list[Action]:
        # obs.nodes: dict of NodeView (beliefs, resilience, reach, etc.)
        # obs.resources: current resource budget
        # obs.narratives: dict of narrative properties
        # obs.turns_remaining: turns until deadline
        
        actions = []
        budget  = obs.resources
        
        # Your strategy here
        best = max(obs.nodes.values(), key=lambda n: n.reach)
        actions.append(Action(
            ActionType.INJECT_NARRATIVE, self.agent_id,
            target_node=best.node_id,
            narrative_id=list(obs.narratives.keys())[0],
        ))
        
        return actions
```

### Adding a Narrative Property

Edit `env/world.py` to add a field to the `Narrative` dataclass, then reference it in `env/actions.py` in the relevant resolver methods.

---

## CLI Reference

### Simulation (`main.py`)

```
python3 main.py [options]

  --scenario {election,alliance,health}   Scenario to run (default: election)
  --red {heuristic,random}                Red agent type (default: heuristic)
  --blue {heuristic,random}               Blue agent type (default: heuristic)
  --turns INT                             Max turns / deadline override
  --seed INT                              RNG seed for reproducibility (default: 42)
  --quiet                                 Suppress turn-by-turn output
  --list-scenarios                        Print scenario descriptions and exit
```

### Game Server (`server.py`)

```
python3 server.py [options]

  --scenario {election,alliance,health}   Scenario (default: election)
  --human {red,blue,both}                 Which side the human plays (default: red)
  --opponent {heuristic,random,claude}    AI opponent type (default: heuristic)
  --seed INT                              RNG seed (default: random each game)
  --port INT                              Port to serve on (default: 5000)
  --host STR                              Host to bind (default: 127.0.0.1)
```

---

## Citation

If you use Infosphere in academic work, please cite:

```
@software{infosphere2026,
  title   = {Infosphere: A Multi-Agent Influence Operations Wargame},
  year    = {2026},
  note    = {Built on the CyberWar agentic simulation framework.
             Scenarios model democratic election interference,
             alliance cohesion attacks, and public health disinformation.}
}
```

---

## Related Work

Infosphere is part of a broader research programme on adversarial AI simulation. The companion project **CyberWar** applies the same multi-agent framework to network intrusion and defense, with PPO reinforcement learning achieving 70% win rates against heuristic defenders within 100 training episodes. Both projects share an agent architecture, training infrastructure, and battle replay visualizer.

---

## Roadmap

- [x] Battle replay HTML generator (narrative heatmap visualization)
- [x] Human play via browser-based web UI — start screen with scenario/team selection, Human vs AI, Human vs Human, and AI vs AI watch mode
- [x] Standalone Mac (.app) and Windows (.exe) builds via GitHub Actions
- [ ] PPO reinforcement learning agent (carries over from CyberWar)
- [ ] Claude LLM agent with tool-calling interface
- [ ] Human game logging (export decisions as supervised training data for RL)
- [ ] Multi-round tournament mode (track win rates across seeds)
- [ ] Scenario editor (define graphs via JSON/YAML)
- [ ] Extended narrative library with empirically-grounded properties
- [ ] Academic paper: *Asymmetric Advantage in Influence Operations: A Multi-Agent Simulation Study*
