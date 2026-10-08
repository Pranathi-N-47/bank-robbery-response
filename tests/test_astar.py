import pytest
import networkx as nx
from brrs.config import MapConfig, TrafficConfig
from brrs.environment.city_map import CityMap
from brrs.environment.traffic import TrafficModel
from brrs.algorithms.astar import astar
from brrs.algorithms.costs import make_travel_time_cost, make_euclidean_time_heuristic

def test_astar_finds_optimal_path_matches_dijkstra():
    config = MapConfig(rows=6, cols=6, block_m=100.0, jitter=0.0, removal_prob=0.0)
    city_map = CityMap(config, seed=42)
    traffic = TrafficModel(city_map, config=TrafficConfig(), seed=42)

    cost_fn = make_travel_time_cost(traffic)
    heuristic = make_euclidean_time_heuristic(city_map)

    start = 0
    goal = 35

    # Run custom A*
    res = astar(city_map, start, goal, cost_fn, heuristic)
    assert res.path[0] == start
    assert res.path[-1] == goal
    assert res.nodes_expanded > 0

    # Validate against NetworkX Dijkstra reference
    def weight_func(u, v, _):
        return cost_fn(u, v)

    ref_cost = nx.dijkstra_path_length(city_map.graph, start, goal, weight=weight_func)
    assert pytest.approx(res.total_cost, rel=1e-4) == ref_cost

def test_astar_same_start_and_goal():
    config = MapConfig(rows=4, cols=4)
    city_map = CityMap(config, seed=42)
    traffic = TrafficModel(city_map, config=TrafficConfig(), seed=42)

    cost_fn = make_travel_time_cost(traffic)
    heuristic = make_euclidean_time_heuristic(city_map)

    res = astar(city_map, 5, 5, cost_fn, heuristic)
    assert res.path == [5]
    assert res.total_cost == 0.0
    assert res.nodes_expanded == 0
