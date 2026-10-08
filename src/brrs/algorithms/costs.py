from __future__ import annotations
import math
from typing import Callable
from brrs.environment.city_map import CityMap
from brrs.environment.traffic import TrafficModel


def make_travel_time_cost(traffic_model: TrafficModel) -> Callable[[int, int], float]:
    """Returns a cost function based on dynamic edge travel times in seconds."""
    def cost(u: int, v: int) -> float:
        return traffic_model.get_travel_time(u, v)
    return cost


def make_euclidean_time_heuristic(city_map: CityMap) -> Callable[[int, int], float]:
    """
    Admissible heuristic: h(n) = euclidean_distance(n, goal) / max_speed_limit.
    Underestimates travel time since speed limit is the absolute maximum achievable.
    """
    # Max speed limit across all edges in the city graph
    max_speed = max(d["speed_limit"] for _, _, d in city_map.graph.edges(data=True))

    def heuristic(u: int, goal: int) -> float:
        dist = city_map.euclidean_distance(u, goal)
        return dist / max_speed

    return heuristic


def make_robber_danger_cost(
    traffic_model: TrafficModel,
    city_map: CityMap,
    visible_police_coords: list[tuple[float, float]],
    danger_lambda: float = 3.0,
    sigma: float = 120.0,
    roadblock_nodes: set[int] | None = None,
) -> Callable[[int, int], float]:
    """
    Cost function for the Robber Agent:
    travel_time * (1 + lambda * sum(exp(-dist(police, edge_midpoint)^2 / (2 * sigma^2))))
    Penalizes paths that traverse close to known police positions or active roadblocks.
    """
    def cost(u: int, v: int) -> float:
        base_time = traffic_model.get_travel_time(u, v)
        
        # Heavy penalty if transitioning into an active roadblock node
        roadblock_multiplier = 1.0
        if roadblock_nodes and v in roadblock_nodes:
            roadblock_multiplier = 50.0

        if not visible_police_coords or danger_lambda <= 0.0:
            return base_time * roadblock_multiplier

        # Midpoint of edge
        ux, uy = city_map.node_coords(u)
        vx, vy = city_map.node_coords(v)
        mx, my = (ux + vx) / 2.0, (uy + vy) / 2.0

        danger_penalty = 0.0
        for px, py in visible_police_coords:
            d = math.hypot(px - mx, py - my)
            # Gaussian danger decay
            danger_penalty += math.exp(-(d ** 2) / (2.0 * (sigma ** 2)))

        return (base_time * (1.0 + danger_lambda * danger_penalty)) * roadblock_multiplier

    return cost

