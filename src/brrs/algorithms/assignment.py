from __future__ import annotations
import numpy as np
from scipy.optimize import linear_sum_assignment
from brrs.environment.city_map import CityMap
from brrs.environment.traffic import TrafficModel
from brrs.algorithms.astar import astar
from brrs.algorithms.costs import make_travel_time_cost, make_euclidean_time_heuristic
from brrs.algorithms.interception import InterceptionCandidate


def assign_police_units(
    city_map: CityMap,
    traffic_model: TrafficModel,
    available_units: list[str],
    unit_positions: dict[str, int],
    interception_points: list[InterceptionCandidate],
) -> dict[str, int]:
    """
    Optimally assigns available police units to selected interception points
    using the Hungarian algorithm (linear sum assignment).
    
    Returns:
        mapping: unit_id -> assigned_destination_node
    """
    if not available_units or not interception_points:
        return {}

    cost_fn = make_travel_time_cost(traffic_model)
    heuristic_fn = make_euclidean_time_heuristic(city_map)

    n_units = len(available_units)
    n_points = len(interception_points)

    cost_matrix = np.full((n_units, n_points), fill_value=1e6)

    for i, u_id in enumerate(available_units):
        u_node = unit_positions[u_id]
        for j, cand in enumerate(interception_points):
            dest_node = cand.point
            res = astar(city_map, u_node, dest_node, cost_fn, heuristic_fn)
            if res.path:
                eta = res.total_cost
                # If ETA exceeds robber ETA, apply severe penalty
                deadline_penalty = 500.0 if eta > cand.robber_eta_s else 0.0
                # Higher priority points (lower index) get cost discount
                priority_discount = j * 10.0
                cost_matrix[i, j] = eta + deadline_penalty + priority_discount

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    assignments: dict[str, int] = {}
    for r, c in zip(row_ind, col_ind):
        # Ensure cost is finite
        if cost_matrix[r, c] < 5e5:
            unit_id = available_units[r]
            target_node = interception_points[c].point
            assignments[unit_id] = target_node

    return assignments
