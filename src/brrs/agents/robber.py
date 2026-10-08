from __future__ import annotations
import math
import random
from typing import Any
import mesa
from brrs.agents.base import CommAgent
from brrs.core.messaging import MessageType
from brrs.environment.movement import EdgePosition, move_along_route, get_coordinates
from brrs.algorithms.astar import astar
from brrs.algorithms.costs import make_robber_danger_cost, make_euclidean_time_heuristic


class RobberAgent(CommAgent):
    """
    Robber Agent:
    - Phase: ROBBING (inside bank for duration) -> FLEEING (seeking exit) -> CAUGHT/ESCAPED
    - Uses A* to target the safest exit using danger penalty from visible police
    - Replans route when police encroach or block path
    - Partial observability: Only perceives police within vision_radius_m
    """

    def __init__(
        self,
        model: mesa.Model,
        speed: float = 13.0,
        vision_radius_m: float = 200.0,
        temperature: float = 0.3,
        danger_lambda: float = 3.0,
        threat_radius_m: float = 150.0,
        cooldown_ticks: int = 5,
        memory_ticks: int = 10,
        robbery_duration: int = 20,
    ):
        super().__init__(model, name="robber", role="robber")
        self.speed = speed
        self.vision_radius_m = vision_radius_m
        self.temperature = temperature
        self.danger_lambda = danger_lambda
        self.threat_radius_m = threat_radius_m
        self.cooldown_ticks = cooldown_ticks
        self.memory_ticks = memory_ticks
        self.robbery_duration = robbery_duration

        self.phase: str = "ROBBING"  # "ROBBING", "FLEEING", "CAUGHT", "ESCAPED"
        self.pos: EdgePosition = EdgePosition(u=model.city_map.bank_node, v=model.city_map.bank_node, offset_m=0.0)
        self.route: list[int] = []
        self.target_exit: int | None = None
        self.last_replan_tick: int = -999
        self.route_changes: int = 0
        self.traversed_edges: list[tuple[int, int]] = []
        self.distance_travelled_m: float = 0.0

        # Memory of police: unit_id -> (x, y, tick_seen)
        self.police_memory: dict[str, tuple[float, float, int]] = {}

    def perceive(self) -> None:
        self.fetch_messages()  # Robber receives no official messages

        # Check robbery duration expiration
        if self.phase == "ROBBING" and self.model.steps >= self.robbery_duration:
            self.phase = "FLEEING"

        # Vision sensing: scan environment for police within vision radius
        current_x, current_y = get_coordinates(self.model.city_map, self.pos)
        current_tick = self.model.steps

        # Check true police coordinates from model (simulating local visual sensors)
        for patrol in self.model.patrol_agents:
            px, py = get_coordinates(self.model.city_map, patrol.pos)
            dist = math.hypot(current_x - px, current_y - py)
            if dist <= self.vision_radius_m:
                self.police_memory[patrol.agent_name] = (px, py, current_tick)

        # Prune stale police memory older than memory_ticks
        self.police_memory = {
            pid: data for pid, data in self.police_memory.items()
            if (current_tick - data[2]) <= self.memory_ticks
        }

    def decide(self) -> None:
        if self.phase != "FLEEING":
            return

        current_tick = self.model.steps
        needs_route = (not self.route) or (self.target_exit is None)

        # Check threat trigger if cooldown has elapsed
        threat_detected = False
        if not needs_route and (current_tick - self.last_replan_tick >= self.cooldown_ticks):
            # Check if any remembered police unit is within threat radius of next few route nodes
            lookahead_nodes = self.route[:3]
            for node in lookahead_nodes:
                nx, ny = self.model.city_map.node_coords(node)
                for px, py, _ in self.police_memory.values():
                    if math.hypot(nx - px, ny - py) <= self.threat_radius_m:
                        threat_detected = True
                        break
                if threat_detected:
                    break

        if needs_route or threat_detected:
            self._plan_escape_route()

    def _plan_escape_route(self) -> None:
        visible_coords = [(px, py) for px, py, _ in self.police_memory.values()]

        danger_cost = make_robber_danger_cost(
            self.model.traffic_model,
            self.model.city_map,
            visible_coords,
            danger_lambda=self.danger_lambda,
        )
        heuristic = make_euclidean_time_heuristic(self.model.city_map)

        start_node = self.pos.u if self.pos.is_at_node() else self.pos.v

        # Evaluate routes to all possible exits
        exit_options: list[tuple[int, list[int], float]] = []
        for ex in self.model.city_map.exit_nodes:
            res = astar(self.model.city_map, start_node, ex, danger_cost, heuristic)
            if res.path:
                exit_options.append((ex, res.path, res.total_cost))

        if not exit_options:
            return

        # Softmax choice with temperature
        costs = [cost for _, _, cost in exit_options]
        min_cost = min(costs)
        # Shift costs to prevent numerical overflow
        logits = [-((c - min_cost) / max(0.05, self.temperature)) for c in costs]
        exp_logits = [math.exp(l) for l in logits]
        sum_exp = sum(exp_logits)
        probs = [e / sum_exp for e in exp_logits]

        # Sample target exit
        r = self.model.random.random()
        cumulative = 0.0
        chosen_idx = 0
        for i, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                chosen_idx = i
                break

        old_target = self.target_exit
        self.target_exit, self.route, _ = exit_options[chosen_idx]
        
        # Strip start node if we are already sitting on it
        if self.route and self.route[0] == self.pos.u and self.pos.is_at_node():
            self.route = self.route[1:]

        if old_target is not None and old_target != self.target_exit:
            self.route_changes += 1
            self.model.metrics.robber_route_changes += 1

        self.last_replan_tick = self.model.steps

    def act(self) -> None:
        self.traversed_edges = []
        if self.phase != "FLEEING":
            return

        # Calculate movement distance budget for this tick
        curr_edge_cong = self.model.traffic_model.get_congestion(self.pos.u, self.pos.v)
        effective_speed = self.speed / curr_edge_cong
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
        self.model.metrics.total_robber_travel_distance_m += moved

        # Notify environment of movement state
        self.send(
            recipient=None,
            topic="robber.state",
            type=MessageType.ROBBER_STATE,
            payload={
                "pos": {"u": self.pos.u, "v": self.pos.v, "offset": self.pos.offset_m},
                "phase": self.phase,
                "target_exit": self.target_exit,
            },
        )

        # Check if robber reached destination exit
        if self.pos.is_at_node() and self.pos.u in self.model.city_map.exit_nodes:
            self.phase = "ESCAPED"



    def state_dict(self) -> dict[str, Any]:
        x, y = get_coordinates(self.model.city_map, self.pos)
        return {
            "name": self.agent_name,
            "role": self.role,
            "phase": self.phase,
            "x": round(x, 1),
            "y": round(y, 1),
            "target_exit": self.target_exit,
            "route_len": len(self.route),
            "route_changes": self.route_changes,
            "visible_police_count": len(self.police_memory),
            "distance_m": round(self.distance_travelled_m, 1),
        }
