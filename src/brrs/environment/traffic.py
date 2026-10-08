from __future__ import annotations
import random
from dataclasses import dataclass
from brrs.config import TrafficConfig
from brrs.environment.city_map import CityMap


@dataclass
class JamEvent:
    edge: tuple[int, int]
    remaining_ticks: int
    severity: float


class TrafficModel:
    """Simulates dynamic road congestion, civilian influence, and incident-induced bottlenecks."""

    def __init__(self, city_map: CityMap, config: TrafficConfig, seed: int | None = None):
        self.city_map = city_map
        self.config = config
        self.rng = random.Random(seed)
        # edge canonical key -> congestion multiplier >= 1.0
        self.congestion: dict[tuple[int, int], float] = {}
        self.civilian_counts: dict[tuple[int, int], int] = {}
        self.active_jams: list[JamEvent] = []
        self._init_edges()

    def _canonical(self, u: int, v: int) -> tuple[int, int]:
        return (u, v) if u < v else (v, u)

    def _init_edges(self) -> None:
        for u, v in self.city_map.graph.edges():
            key = self._canonical(u, v)
            self.congestion[key] = self.config.base
            self.civilian_counts[key] = 0

    def set_civilian_counts(self, counts: dict[tuple[int, int], int]) -> None:
        """Update count of civilians currently traversing edges."""
        self.civilian_counts = {self._canonical(k[0], k[1]): v for k, v in counts.items()}

    def trigger_jam(self, u: int, v: int, duration_ticks: int, severity: float) -> None:
        """Manually or dynamically trigger a traffic jam on an edge."""
        key = self._canonical(u, v)
        self.active_jams.append(JamEvent(edge=key, remaining_ticks=duration_ticks, severity=severity))

    def step(self) -> dict[tuple[int, int], float]:
        """Update traffic states for one simulation tick. Returns updated congestion map."""
        # 1. Update active jam events
        surviving_jams: list[JamEvent] = []
        jam_effects: dict[tuple[int, int], float] = {}
        for jam in self.active_jams:
            jam.remaining_ticks -= 1
            jam_effects[jam.edge] = jam_effects.get(jam.edge, 0.0) + jam.severity
            if jam.remaining_ticks > 0:
                surviving_jams.append(jam)
        self.active_jams = surviving_jams

        # 2. Stochastic new jam generation
        if self.rng.random() < self.config.jam_rate:
            edges = list(self.congestion.keys())
            if edges:
                chosen_edge = self.rng.choice(edges)
                duration = self.rng.randint(self.config.jam_min, self.config.jam_max)
                self.trigger_jam(chosen_edge[0], chosen_edge[1], duration, self.config.jam_severity)
                jam_effects[chosen_edge] = jam_effects.get(chosen_edge, 0.0) + self.config.jam_severity

        # 3. Compute final congestion multiplier for all edges
        for key in self.congestion:
            civs = self.civilian_counts.get(key, 0)
            civ_mult = civs * self.config.civilian_factor
            jam_mult = jam_effects.get(key, 0.0)
            self.congestion[key] = max(1.0, self.config.base + civ_mult + jam_mult)

        return self.congestion

    def get_congestion(self, u: int, v: int) -> float:
        """Get congestion multiplier on edge (u, v)."""
        return self.congestion.get(self._canonical(u, v), 1.0)

    def get_travel_time(self, u: int, v: int) -> float:
        """Calculates travel time in seconds: length / speed_limit * congestion."""
        length = self.city_map.edge_length(u, v)
        speed = self.city_map.edge_speed_limit(u, v)
        cong = self.get_congestion(u, v)
        return (length / speed) * cong

    def to_dict(self) -> dict[str, float]:
        """Serialize for frontend visualization, keyed as 'u-v'."""
        return {f"{k[0]}-{k[1]}": round(v, 2) for k, v in self.congestion.items()}
