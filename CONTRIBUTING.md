# Contributing to Infosphere

Thank you for your interest in contributing. Infosphere is a research platform — contributions that improve simulation fidelity, add scenarios, or extend the agent architecture are especially welcome.

## Getting Started

```bash
# Fork and clone
git clone https://github.com/yourusername/infosphere.git
cd infosphere

# Install in editable mode with dev dependencies
pip install -e ".[all]"
pip install -r requirements-dev.txt

# Verify everything works
python -m pytest tests/
python main.py --scenario election --quiet
```

## Project Structure

```
infosphere/          # Main package
  env/               # World model, actions, observations
  agents/            # Agent implementations
  engine/            # Game loop and win conditions
  scenarios/         # Built-in scenarios
  static/            # Browser UI for human play
main.py              # CLI entrypoint
server.py            # Flask game server
tests/               # Test suite
```

## Ways to Contribute

### New Scenarios

A scenario is a function that returns `(World, primary_narrative_id)`. See `infosphere/scenarios/scenarios.py` for examples. Good scenarios are grounded in a real-world IO context, have a meaningful offense-defense tension, and include at least one foreign amplifier node and one high-resilience institution node.

Add your scenario to the `SCENARIOS` dict in `scenarios.py` and add a parametrized test case in `tests/test_infosphere.py`.

### New Actions

Add to `ActionType` in `env/actions.py`, set a cost in `ACTION_COSTS`, and implement a resolver method in `ActionResolver`. Follow the existing pattern: validate inputs, roll probability, apply effects via the `effects` dict, return an `Outcome`.

### New Agent Strategies

Subclass `BaseAgent` in `agents/agents.py`. The `act(obs: Observation) -> list[Action]` method receives a partial observation and must return a list of actions within the resource budget. See `HeuristicRedAgent` for a well-commented example.

### Bug Fixes

Please include a test that reproduces the bug before your fix and passes after it.

## Code Style

- Black-compatible formatting (max line length 100)
- Type hints on all public functions
- Docstrings on all public classes
- No external dependencies in `infosphere/env/`, `infosphere/engine/`, or `infosphere/scenarios/`

## Running Tests

```bash
# All tests
python -m pytest

# Specific class
python -m pytest tests/ -k "TestEngine"

# With coverage
python -m pytest --cov=infosphere --cov-report=term-missing
```

## Pull Request Checklist

- [ ] All existing tests pass (`python -m pytest`)
- [ ] New functionality has test coverage
- [ ] All three scenarios still run to completion
- [ ] No new external dependencies added to the core package
- [ ] README updated if behaviour or CLI changes

## Research Use

If you use Infosphere in published research, please cite the project (see README) and consider contributing your scenario back to the main repository so others can reproduce your experiments.
