from __future__ import annotations
import math
from typing import Any
import mesa
from brrs.agents.base import CommAgent
from brrs.core.messaging import MessageType, Message
from brrs.environment.movement import EdgePosition, move_along_route, get_coordinates
from brrs.algorithms.astar import astar
from brrs.algorithms.costs import make_travel_time_cost, make_euclidean_time_heuristic


class PatrolAgent(CommAgent):
    """
    Patrol Agent:
    - Status: IDLE, EN_ROUTE, HOLDING, PURSUING, RETURNING
    - Executes A* route planning on the city road graph
    - Re-evaluates path when traffic spikes exceed replan_threshold
    - Continuously emits POSITION_UPDATE to C&I and Dispatch
    """

    def __init__(
        self,
        model: mesa.Model,
        unit_id: int,
        station_node: int,
        speed: float = 15.0,
        report_interval: int = 2,
        replan_threshold: float = 0.2,
    ):
        super().__init__(model, name=f"police_{unit_id}", role="patrol")
        self.unit_id = unit_id
        self.station_node = station_node
        self.speed = speed
        self.report_interval = report_interval
        self.replan_threshold = replan_threshold

        self.subscribe("unit.orders")

        self.status: str = "IDLE"  # IDLE, EN_ROUTE, HOLDING, PURSUING, RETURNING
        self.pos: EdgePosition = EdgePosition(u=station_node, v=station_node, offset_m=0.0)
        self.destination: int | None = None
        self.route: list[int] = []
        self.last_planned_cost: float = 0.0
        self.distance_travelled_m: float = 0.0
        self.route_replans: int = 0
        self.traversed_edges: list[tuple[int, int]] = []
        self.active_mode: str = "IDLE"
        self.current_plan_version: int = 0

    def perceive(self) -> None:
        messages = self.fetch_messages()
        for msg in messages:
            if msg.type == MessageType.ASSIGNMENT:
                new_dest = msg.payload["destination"]
                mode = msg.payload["mode"]
                version = msg.payload["plan_version"]

                # If destination changed or mode switched, replan route
                if new_dest != self.destination or mode != self.active_mode:
                    self.destination = new_dest
                    self.active_mode = mode
                    self.current_plan_version = version
                    self.status = "PURSUING" if mode == "PURSUE" else "EN_ROUTE"
                    self._plan_route(reason="destination")

            elif msg.type == MessageType.RECALL:
                if self.status != "IDLE":
                    self.status = "RETURNING"
                    self.destination = self.station_node
                    self.active_mode = "RETURN"
                    self._plan_route(reason="recall")

    def decide(self) -> None:
        if self.status != "PURSUING":
            return

        # Continuous pursuit tracking: if suspect moves, update destination if far
        robber = self.model.robber_agent
        if robber.phase == "FLEEING":
            r_node = robber.pos.u if robber.pos.is_at_node() else robber.pos.v
            if self.destination != r_node and (not self.route or len(self.route) <= 2):
                self.destination = r_node
                self._plan_route(reason="dynamic_pursuit_tracking")

        # Check traffic-induced replanning trigger
        if self.route and len(self.route) > 1:
            cost_fn = make_travel_time_cost(self.model.traffic_model)
            current_route_cost = 0.0
            prev = self.pos.u if self.pos.is_at_node() else self.pos.v
            for nxt in self.route:
                if prev != nxt and self.model.city_map.graph.has_edge(prev, nxt):
                    current_route_cost += cost_fn(prev, nxt)
                prev = nxt

            if self.last_planned_cost > 0.1:
                cost_ratio = (current_route_cost - self.last_planned_cost) / self.last_planned_cost
                if cost_ratio > self.replan_threshold:
                    # Traffic congestion spiked along our path, replan alternative route
                    self._plan_route(reason="traffic")


    def _plan_route(self, reason: str = "destination") -> None:
        if self.destination is None:
            return

        start_node = self.pos.u if self.pos.is_at_node() else self.pos.v
        cost_fn = make_travel_time_cost(self.model.traffic_model)
        heuristic = make_euclidean_time_heuristic(self.model.city_map)

        res = astar(self.model.city_map, start_node, self.destination, cost_fn, heuristic)
        self.model.metrics.astar_nodes_expanded_total += res.nodes_expanded

        if res.path:
            self.route = res.path
            # Trim current node if we are already sitting on it
            if self.pos.is_at_node() and self.route and self.route[0] == self.pos.u:
                self.route = self.route[1:]
            self.last_planned_cost = res.total_cost
            self.route_replans += 1
            self.model.metrics.record_replan(reason=reason)

            # Announce planned route
            self.send(
                recipient="role:command",
                topic="unit.routes",
                type=MessageType.ROUTE_PLANNED,
                payload={
                    "route": res.path,
                    "eta_s": res.total_cost,
                    "reason": reason,
                    "nodes_expanded": res.nodes_expanded,
                },
                priority=3,
            )

    def act(self) -> None:
        self.traversed_edges = []
        current_tick = self.model.steps

        if self.status in ("EN_ROUTE", "PURSUING", "RETURNING") and self.route:
            cong = self.model.traffic_model.get_congestion(self.pos.u, self.pos.v)
            effective_speed = self.speed / cong
            dist_budget = effective_speed * self.model.config.sim.tick_seconds

            new_pos, updated_route, traversed, moved = move_along_route(
                self.model.city_map,
                self.pos,
                self.route,
                dist_budget,
            )
            self.pos = new_pos
            self.route = updated_route
            self.traversed_edges = traversed
            self.distance_travelled_m += moved
            self.model.metrics.total_police_travel_distance_m += moved

            # Check if arrived at destination
            if not self.route and self.pos.is_at_node() and self.pos.u == self.destination:
                if self.status in ("EN_ROUTE", "PURSUING"):
                    self.status = "PURSUING"
                    self.model.metrics.record_first_response(current_tick)
                    robber = self.model.robber_agent
                    if robber.phase == "FLEEING":
                        r_node = robber.pos.u if robber.pos.is_at_node() else robber.pos.v
                        if r_node != self.destination:
                            self.destination = r_node
                            self._plan_route(reason="pursuit_continuation")
                elif self.status == "RETURNING":
                    self.status = "IDLE"


        # Emit periodic position update
        if (current_tick % self.report_interval) == 0:
            curr_node = self.pos.u if self.pos.is_at_node() else self.pos.v
            x, y = get_coordinates(self.model.city_map, self.pos)
            self.send(
                recipient=None,
                topic="unit.status",
                type=MessageType.POSITION_UPDATE,
                payload={
                    "node": curr_node,
                    "x": x,
                    "y": y,
                    "status": self.status,
                    "destination": self.destination,
                },
                priority=1,
            )

    def state_dict(self) -> dict[str, Any]:
        x, y = get_coordinates(self.model.city_map, self.pos)
        return {
            "name": self.agent_name,
            "role": self.role,
            "status": self.status,
            "x": round(x, 1),
            "y": round(y, 1),
            "destination": self.destination,
            "route_len": len(self.route),
            "replans": self.route_replans,
            "distance_m": round(self.distance_travelled_m, 1),
        }
