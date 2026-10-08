from __future__ import annotations
import math
from dataclasses import dataclass
from brrs.environment.city_map import CityMap
from brrs.environment.traffic import TrafficModel
from brrs.algorithms.astar import astar
from brrs.algorithms.costs import make_travel_time_cost, make_euclidean_time_heuristic
from brrs.algorithms.escape_prediction import EscapeRoute


@dataclass
class InterceptionCandidate:
    point: int
    route_path: list[int]
    route_prob: float
    robber_eta_s: float
    best_police_id: str | None
    best_police_eta_s: float
    margin_s: float
    score: float
    suitable: bool


class InterceptionPlanner:
    """Evaluates candidate road intersections along predicted robber escape routes to select interception points."""

    def __init__(self, city_map: CityMap, traffic_model: TrafficModel):
        self.city_map = city_map
        self.traffic_model = traffic_model
        self.cost_fn = make_travel_time_cost(traffic_model)
        self.heuristic_fn = make_euclidean_time_heuristic(city_map)

    def evaluate_candidates(
        self,
        routes: list[EscapeRoute],
        police_positions: dict[str, int],  # unit_id -> current_node
        safety_buffer_s: float = 3.0,
        horizon_s: float = 120.0,
        alpha: float = 0.05,
        kappa: float = 20.0,
    ) -> list[InterceptionCandidate]:
        """
        Finds suitable interception candidates across all predicted routes.
        
        A candidate node is suitable if:
        min_police_eta + safety_buffer_s <= robber_eta (i.e., margin > 0)
        """
        candidates: list[InterceptionCandidate] = []

        # Precompute ETAs from police positions
        police_eta_cache: dict[tuple[str, int], float] = {}

        for route in routes:
            path = route.path
            cumulative_robber_time = 0.0

            # Evaluate each node on the predicted route
            for idx in range(len(path)):
                node = path[idx]
                if idx > 0:
                    prev_node = path[idx - 1]
                    cumulative_robber_time += self.traffic_model.get_travel_time(prev_node, node)

                if cumulative_robber_time > horizon_s:
                    break

                # Ignore the first node if it's the exact origin and time is 0
                if idx == 0 and cumulative_robber_time < 0.1:
                    continue

                best_police_id = None
                best_police_eta = float("inf")

                for p_id, p_node in police_positions.items():
                    cache_key = (p_id, node)
                    if cache_key not in police_eta_cache:
                        res = astar(self.city_map, p_node, node, self.cost_fn, self.heuristic_fn)
                        police_eta_cache[cache_key] = res.total_cost if res.path else float("inf")

                    p_eta = police_eta_cache[cache_key]
                    if p_eta < best_police_eta:
                        best_police_eta = p_eta
                        best_police_id = p_id

                margin = cumulative_robber_time - best_police_eta - safety_buffer_s
                suitable = (margin > 0.0) and (best_police_id is not None)

                # Score candidate: combines route probability, safety margin, and minimizes police travel time
                # score = P(route) * (1 - exp(-margin / kappa)) - alpha * best_police_eta
                if suitable:
                    safety_factor = 1.0 - math.exp(-max(0.0, margin) / kappa)
                    score = route.probability * safety_factor - (alpha * best_police_eta)
                else:
                    score = -100.0 + margin

                candidates.append(
                    InterceptionCandidate(
                        point=node,
                        route_path=path,
                        route_prob=route.probability,
                        robber_eta_s=cumulative_robber_time,
                        best_police_id=best_police_id,
                        best_police_eta_s=best_police_eta,
                        margin_s=margin,
                        score=score,
                        suitable=suitable,
                    )
                )

        # Sort by best score descending
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def select_best_points_per_route(
        self,
        candidates: list[InterceptionCandidate],
        max_points: int = 3,
    ) -> list[InterceptionCandidate]:
        """Selects the top suitable candidate per distinct route, avoiding redundant choke-points."""
        selected: list[InterceptionCandidate] = []
        covered_points: set[int] = set()
        covered_route_exits: set[int] = set()

        # Pass 1: Prioritize 1 interception point per distinct exit route to flank and intercept from multiple sides
        for cand in candidates:
            exit_node = cand.route_path[-1] if cand.route_path else cand.point
            if exit_node in covered_route_exits:
                continue
            if cand.point in covered_points:
                continue

            selected.append(cand)
            covered_points.add(cand.point)
            covered_route_exits.add(exit_node)
            if len(selected) >= max_points:
                break

        # Pass 2: If available units exceed distinct routes, add remaining best candidates
        if len(selected) < max_points:
            for cand in candidates:
                if cand.point in covered_points:
                    continue
                selected.append(cand)
                covered_points.add(cand.point)
                if len(selected) >= max_points:
                    break

        return selected
