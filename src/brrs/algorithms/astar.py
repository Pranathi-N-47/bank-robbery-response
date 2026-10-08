from __future__ import annotations
import heapq
import math
from dataclasses import dataclass
from typing import Callable
from brrs.environment.city_map import CityMap


@dataclass
class SearchResult:
    path: list[int]
    total_cost: float
    nodes_expanded: int
    explored_nodes: list[int]


def astar(
    city_map: CityMap,
    start: int,
    goal: int,
    cost_fn: Callable[[int, int], float],
    heuristic_fn: Callable[[int, int], float],
) -> SearchResult:
    """
    Custom A* search implementation operating on the road network graph.
    
    f(n) = g(n) + h(n)
    
    Returns SearchResult containing the optimal route, total cost,
    number of node expansions, and list of explored nodes for visualization.
    """
    if start == goal:
        return SearchResult(path=[start], total_cost=0.0, nodes_expanded=0, explored_nodes=[start])

    # Priority queue entry: (f_score, h_score, tie_breaker, current_node)
    counter = 0
    open_set: list[tuple[float, float, int, int]] = []
    h_start = heuristic_fn(start, goal)
    heapq.heappush(open_set, (h_start, h_start, counter, start))

    came_from: dict[int, int] = {}
    g_score: dict[int, float] = {start: 0.0}
    closed_set: set[int] = set()
    explored_nodes: list[int] = []

    while open_set:
        f, h, _, current = heapq.heappop(open_set)

        if current in closed_set:
            continue
        closed_set.add(current)
        explored_nodes.append(current)

        if current == goal:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return SearchResult(
                path=path,
                total_cost=g_score[goal],
                nodes_expanded=len(closed_set),
                explored_nodes=explored_nodes,
            )

        for neighbor in city_map.neighbors(current):
            if neighbor in closed_set:
                continue

            tentative_g = g_score[current] + cost_fn(current, neighbor)
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h_val = heuristic_fn(neighbor, goal)
                f_val = tentative_g + h_val
                counter += 1
                heapq.heappush(open_set, (f_val, h_val, counter, neighbor))

    # No path found
    return SearchResult(path=[], total_cost=float("inf"), nodes_expanded=len(closed_set), explored_nodes=explored_nodes)
