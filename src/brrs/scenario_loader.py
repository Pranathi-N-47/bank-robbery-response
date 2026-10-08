import yaml
from pathlib import Path
from brrs.config import ScenarioConfig

def load_scenario(path_or_name: str | Path) -> ScenarioConfig:
    """Load a scenario configuration from a YAML file path or scenario name."""
    p = Path(path_or_name)
    if not p.is_file():
        # Try checking in scenarios/ directory
        candidates = [
            Path("scenarios") / f"{path_or_name}.yaml",
            Path("scenarios") / f"{path_or_name}.yml",
            Path("scenarios") / path_or_name,
        ]
        found = False
        for c in candidates:
            if c.is_file():
                p = c
                found = True
                break
        if not found:
            raise FileNotFoundError(f"Scenario file not found: {path_or_name}")
    
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return ScenarioConfig.model_validate(data)
