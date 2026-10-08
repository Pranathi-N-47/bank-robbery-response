from __future__ import annotations
import math
from dataclasses import dataclass
from brrs.environment.city_map import CityMap
from brrs.environment.traffic import TrafficModel
from brrs.algorithms.astar import astar
from brrs.algorithms.costs import make_travel_time_cost, make_euclidean_time_heuristic


@dataclass
class EscapeRoute:
    exit_node: int
    path: list[int]
    travel_time_s: float
    probability: float


class EscapePredictor:
    """Predicts robber escape trajectories and assigns probabilities using multinomial logit."""

    def __init__(self, city_map: CityMap, traffic_model: TrafficModel):
        self.city_map = city_map
        self.traffic_model = traffic_model
        self.cost_fn = make_travel_time_cost(traffic_model)
        self.heuristic_fn = make_euclidean_time_heuristic(city_map)

    def predict(
        self,
        current_node: int,
        estimated_heading: tuple[float, float] | None = None,
        top_k: int = 3,
        temperature: float = 15.0,
    ) -> list[EscapeRoute]:
        """
        Calculates optimal path from current estimated position to all exits,
        and scores each route with a probability distribution.
        """
        routes: list[tuple[int, list[int], float]] = []

        for ex in self.city_map.exit_nodes:
            res = astar(self.city_map, current_node, ex, self.cost_fn, self.heuristic_fn)
            if res.path:
                routes.append((ex, res.path, res.total_cost))

        if not routes:
            return []

        # Calculate logits based on path travel time + heading alignment
        logits: list[float] = []
        for ex, path, cost in routes:
            base_logit = -cost / max(1.0, temperature)

            # Bonus if path's immediate direction aligns with estimated velocity heading
            heading_bonus = 0.0
            if estimated_heading and len(path) > 1:
                x1, y1 = self.city_map.node_coords(path[0])
                x2, y2 = self.city_map.node_coords(path[1])
                dx, dy = x2 - x1, y2 - y1
                mag = math.hypot(dx, dy)
                if mag > 0:
                    dot = (dx * estimated_heading[0] + dy * estimated_heading[1]) / mag
                    if dot > 0:
                        heading_bonus = 1.0 * dot

            logits.append(base_logit + heading_bonus)

        # Softmax normalization
        max_logit = max(logits)
        exp_logits = [math.exp(l - max_logit) for l in logits]
        sum_exp = sum(exp_logits)
        probs = [e / sum_exp for e in exp_logits]

        result = [
            EscapeRoute(exit_node=routes[i][0], path=routes[i][1], travel_time_s=routes[i][2], probability=probs[i])
            for i in range(len(routes))
        ]

        # Sort by highest probability first and select top_k
        result.sort(key=lambda r: r.probability, reverse=True)
        return result[:top_k]
