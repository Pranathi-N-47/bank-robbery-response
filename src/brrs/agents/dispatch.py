from __future__ import annotations
from typing import Any
import mesa
from brrs.agents.base import CommAgent
from brrs.core.messaging import MessageType, Message
from brrs.algorithms.assignment import assign_police_units
from brrs.algorithms.interception import InterceptionCandidate


class DispatchAgent(CommAgent):
    """
    Dispatch Agent:
    - Maintains availability and state of all police patrol units
    - Uses Hungarian algorithm to solve unit-to-interception assignment
    - Allocates 1 unit specifically to active PURSUIT of suspect's last known location
    - Issues ASSIGNMENT and RECALL commands to Patrol Agents
    """

    def __init__(self, model: mesa.Model):
        super().__init__(model, name="dispatch", role="dispatch")
        self.subscribe("plans.intercept")
        self.subscribe("unit.status")

        # Patrol unit registry: id -> {"node": int, "status": str, "dest": int | None}
        self.units: dict[str, dict[str, Any]] = {}
        self.current_plan_version: int = 0

    def perceive(self) -> None:
        messages = self.fetch_messages()
        for msg in messages:
            if msg.type == MessageType.POSITION_UPDATE:
                unit_id = msg.sender
                self.units[unit_id] = {
                    "node": msg.payload["node"],
                    "status": msg.payload["status"],
                    "destination": msg.payload.get("destination"),
                }
            elif msg.type == MessageType.INTERCEPT_PLAN:
                self._handle_intercept_plan(msg)

    def _handle_intercept_plan(self, msg: Message) -> None:
        self.current_plan_version = msg.payload["version"]
        pursuit_node = msg.payload.get("pursuit_target_node")
        if pursuit_node is None:
            return

        available_unit_ids = list(self.units.keys())
        unit_nodes = {uid: u["node"] for uid, u in self.units.items()}
        if not available_unit_ids:
            return

        # Sort units by distance to suspect's estimated location
        sorted_units = sorted(
            available_unit_ids,
            key=lambda uid: self.model.city_map.euclidean_distance(unit_nodes[uid], pursuit_node),
        )

        # Immediate direct pursuit: closest unit heads straight to suspect's node
        primary_pursuit_unit = sorted_units[0]
        self.send(
            recipient=primary_pursuit_unit,
            topic="unit.orders",
            type=MessageType.ASSIGNMENT,
            payload={
                "mode": "PURSUE",
                "destination": pursuit_node,
                "plan_version": self.current_plan_version,
            },
            priority=9,
        )

        # Encirclement units: assign remaining units to neighboring nodes to box the suspect in from all sides
        flanking_units = sorted_units[1:]
        surrounding_nodes = list(self.model.city_map.graph.adj[pursuit_node].keys()) if self.model.city_map.graph.has_node(pursuit_node) else []

        for idx, uid in enumerate(flanking_units):
            # Target a surrounding intersection or reinforce direct pursuit
            if surrounding_nodes:
                target_dest = surrounding_nodes[idx % len(surrounding_nodes)]
            else:
                target_dest = pursuit_node

            self.send(
                recipient=uid,
                topic="unit.orders",
                type=MessageType.ASSIGNMENT,
                payload={
                    "mode": "PURSUE",
                    "destination": target_dest,
                    "plan_version": self.current_plan_version,
                },
                priority=8,
            )


    def decide(self) -> None:
        pass

    def act(self) -> None:
        pass

    def state_dict(self) -> dict[str, Any]:
        return {
            "name": self.agent_name,
            "role": self.role,
            "managed_units": len(self.units),
            "plan_version": self.current_plan_version,
        }
