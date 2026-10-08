from __future__ import annotations
import random
from typing import Any
import mesa
from brrs.agents.base import CommAgent
from brrs.environment.movement import EdgePosition, move_along_route, get_coordinates


class CivilianAgent(CommAgent):
    """
    Civilian Agent:
    - Performs random walk movements across the road network
    - Induces localized traffic congestion on road edges
    - Does not participate in multi-agent tactical messaging
    """

    def __init__(self, model: mesa.Model, civilian_id: int, start_node: int, speed: float = 7.0):
        super().__init__(model, name=f"civilian_{civilian_id}", role="civilian")
        self.civilian_id = civilian_id
        self.speed = speed
        self.pos = EdgePosition(u=start_node, v=start_node, offset_m=0.0)
        self.route: list[int] = []
        self._pick_random_goal()

    def _pick_random_goal(self) -> None:
        curr_node = self.pos.u if self.pos.is_at_node() else self.pos.v
        candidates = list(self.model.city_map.graph.nodes())
        candidates.remove(curr_node)
        if candidates:
            goal = self.model.random.choice(candidates)
            # Use simple shortest path for civilian navigation
            import networkx as nx
            try:
                path = nx.shortest_path(self.model.city_map.graph, curr_node, goal)
                self.route = path[1:] if path else []
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                self.route = []

    def perceive(self) -> None:
        pass

    def decide(self) -> None:
        if not self.route:
            self._pick_random_goal()

    def act(self) -> None:
        if not self.route:
            return

        cong = self.model.traffic_model.get_congestion(self.pos.u, self.pos.v)
        dist_budget = (self.speed / cong) * self.model.config.sim.tick_seconds

        new_pos, updated_route, _, _ = move_along_route(
            self.model.city_map,
            self.pos,
            self.route,
            dist_budget,
        )
        self.pos = new_pos
        self.route = updated_route

    def state_dict(self) -> dict[str, Any]:
        x, y = get_coordinates(self.model.city_map, self.pos)
        return {
            "name": self.agent_name,
            "role": self.role,
            "x": round(x, 1),
            "y": round(y, 1),
        }
