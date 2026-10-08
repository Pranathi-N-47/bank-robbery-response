from __future__ import annotations
import math
from typing import Any
import mesa
from brrs.agents.base import CommAgent
from brrs.core.messaging import MessageType, Message
from brrs.algorithms.escape_prediction import EscapePredictor, EscapeRoute
from brrs.algorithms.interception import InterceptionPlanner, InterceptionCandidate


class CommandIntelAgent(CommAgent):
    """
    Command and Intelligence (C&I) Agent:
    - Maintains operational belief state of suspect location & uncertainty ellipse
    - Predicts escape routes and likelihoods using EscapePredictor
    - Evaluates reachable interception points using InterceptionPlanner
    - Issues INTERCEPT_PLAN to Dispatch Agent
    - Replans when new sightings invalidate previous assumptions or reveal route deviations
    """

    def __init__(
        self,
        model: mesa.Model,
        top_k_routes: int = 3,
        horizon_s: float = 120.0,
        safety_buffer_s: float = 3.0,
        switch_gain: float = 0.15,
        min_route_prob: float = 0.1,
    ):
        super().__init__(model, name="command_intel", role="command")
        self.top_k_routes = top_k_routes
        self.horizon_s = horizon_s
        self.safety_buffer_s = safety_buffer_s
        self.switch_gain = switch_gain
        self.min_route_prob = min_route_prob

        self.subscribe("incident.alerts")
        self.subscribe("surveillance.sightings")
        self.subscribe("unit.status")

        self.escape_predictor = EscapePredictor(model.city_map, model.traffic_model)
        self.interception_planner = InterceptionPlanner(model.city_map, model.traffic_model)

        self.incident_active = False
        self.estimated_pos: tuple[float, float] | None = None
        self.estimated_node: int | None = None
        self.estimated_heading: tuple[float, float] | None = None
        self.uncertainty_radius_m: float = 0.0
        self.last_sighting_tick: int = 0

        self.police_positions: dict[str, int] = {}  # unit_id -> current_node
        self.predicted_routes: list[EscapeRoute] = []
        self.active_plan_candidates: list[InterceptionCandidate] = []
        self.plan_version: int = 0
        self.total_replans: int = 0

    def perceive(self) -> None:
        messages = self.fetch_messages()
        current_tick = self.model.steps

        new_sighting = False
        for msg in messages:
            if msg.type == MessageType.INCIDENT_ALERT:
                self.incident_active = True
                self.estimated_node = msg.payload["location_node"]
                self.estimated_pos = (msg.payload["x"], msg.payload["y"])
                self.uncertainty_radius_m = 20.0
                self.last_sighting_tick = current_tick
                new_sighting = True

            elif msg.type == MessageType.ROBBER_SIGHTING:
                self.incident_active = True
                self.estimated_node = msg.payload["nearest_node"]
                self.estimated_pos = (msg.payload["x"], msg.payload["y"])
                self.estimated_heading = msg.payload.get("heading")
                self.uncertainty_radius_m = 15.0
                self.last_sighting_tick = current_tick
                new_sighting = True

            elif msg.type == MessageType.POSITION_UPDATE:
                unit_id = msg.sender
                self.police_positions[unit_id] = msg.payload["node"]

        # Dead-reckoning & uncertainty expansion in the absence of fresh sightings
        if self.incident_active and not new_sighting and self.estimated_pos is not None:
            dt = current_tick - self.last_sighting_tick
            robber_nominal_speed = 13.0
            # Uncertainty radius expands as robber could have moved in any direction
            self.uncertainty_radius_m = min(400.0, 15.0 + (dt * robber_nominal_speed * 0.8))

        self.model.metrics.uncertainty_radius_history.append(self.uncertainty_radius_m)

    def decide(self) -> None:
        if not self.incident_active or self.estimated_node is None:
            return

        # 1. Update escape route predictions
        self.predicted_routes = self.escape_predictor.predict(
            current_node=self.estimated_node,
            estimated_heading=self.estimated_heading,
            top_k=self.top_k_routes,
        )

        # Interception / roadblock nodes removed: All units coordinate in active pursuit & perimeter containment
        self.active_plan_candidates = []

        # Check replanning criteria vs active plan
        if self.estimated_node is not None:
            self.plan_version += 1
            self.total_replans += 1

            # Dispatch pursuit plan to dispatch agent
            plan_payload = {
                "version": self.plan_version,
                "estimated_node": self.estimated_node,
                "interception_points": [],
                "pursuit_target_node": self.estimated_node,
            }
            self.send(
                recipient="role:dispatch",
                topic="plans.intercept",
                type=MessageType.INTERCEPT_PLAN,
                payload=plan_payload,
                priority=8,
            )


    def act(self) -> None:
        pass

    def state_dict(self) -> dict[str, Any]:
        return {
            "name": self.agent_name,
            "role": self.role,
            "incident_active": self.incident_active,
            "estimated_node": self.estimated_node,
            "uncertainty_radius_m": round(self.uncertainty_radius_m, 1),
            "plan_version": self.plan_version,
            "total_replans": self.total_replans,
            "active_intercept_points": [c.point for c in self.active_plan_candidates],
            "predicted_routes_count": len(self.predicted_routes),
        }
