from __future__ import annotations
import asyncio
from typing import Callable, Any
from brrs.config import ScenarioConfig
from brrs.core.model import BankRobberyModel
from brrs.scenario_loader import load_scenario


class SimulationRunner:
    """Manages the real-time simulation background loop, playback speeds, and client broadcasts."""

    def __init__(self, broadcast_callback: Callable[[dict[str, Any]], Any]):
        self.broadcast_callback = broadcast_callback
        self.model: BankRobberyModel | None = None
        self.scenario_name: str = "baseline"
        self.current_config: ScenarioConfig | None = None
        
        self.is_running: bool = False
        self.ticks_per_second: float = 4.0
        self._loop_task: asyncio.Task | None = None

    def load(self, scenario_name: str = "baseline", seed: int | None = None) -> dict[str, Any]:
        """Initialize or reset simulation with a scenario and optional seed."""
        self.pause()
        self.scenario_name = scenario_name
        config = load_scenario(scenario_name)
        if seed is not None:
            config.seed = seed
        else:
            import random
            config.seed = random.randint(100, 999999)
        self.current_config = config
        self.model = BankRobberyModel(config, seed=config.seed)
        
        # Build initial response package with map, static infrastructure, and initial state
        init_data = {
            "type": "init",
            "scenario": scenario_name,
            "seed": config.seed,
            "map": self.model.city_map.to_dict(),
            "cctv": self.model.cctv_network.to_dict(),
            "state": self.model.snapshot(),
        }
        return init_data

    def start(self) -> None:
        """Resume or begin asynchronous simulation stepping loop."""
        if self.model is None:
            self.load(self.scenario_name)
        
        if not self.is_running:
            self.is_running = True
            if self._loop_task is None or self._loop_task.done():
                self._loop_task = asyncio.create_task(self._run_loop())

    def pause(self) -> None:
        """Pause simulation loop."""
        self.is_running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            self._loop_task = None

    def set_speed(self, tps: float) -> None:
        """Set execution speed in ticks per real-world second."""
        self.ticks_per_second = max(0.5, min(30.0, float(tps)))

    def step(self) -> dict[str, Any] | None:
        """Perform exactly one manual tick."""
        if self.model is None:
            self.load(self.scenario_name)
        
        if not self.model.is_finished:
            self.model.step()
        
        snapshot = self.model.snapshot()
        return {"type": "tick", "state": snapshot}

    async def _run_loop(self) -> None:
        """Continuous execution loop."""
        try:
            while self.is_running and self.model and not self.model.is_finished:
                self.model.step()
                snapshot = self.model.snapshot()
                
                # Check for completion
                msg_type = "end" if self.model.is_finished else "tick"
                payload = {"type": msg_type, "state": snapshot}
                await self.broadcast_callback(payload)

                if self.model.is_finished:
                    self.is_running = False
                    break

                delay = 1.0 / self.ticks_per_second
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            pass
