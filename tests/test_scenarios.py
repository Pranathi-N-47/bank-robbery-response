from pathlib import Path
import pytest
from brrs.scenario_loader import load_scenario
from brrs.core.model import BankRobberyModel

@pytest.mark.parametrize("scenario_file", [
    "baseline.yaml",
    "rush_hour.yaml",
    "blind_spots.yaml",
    "outnumbered.yaml",
    "fast_getaway.yaml",
    "large_city.yaml",
])
def test_scenario_execution_to_completion(scenario_file):
    path = Path("scenarios") / scenario_file
    config = load_scenario(path)
    model = BankRobberyModel(config, seed=123)

    # Run for up to max ticks
    for _ in range(config.sim.max_ticks):
        model.step()
        if model.is_finished:
            break

    assert model.is_finished is True
    assert model.metrics.outcome in ("INTERCEPTED", "ESCAPED", "TIMEOUT")
