from __future__ import annotations
import math
from typing import Any
import mesa
from brrs.agents.base import CommAgent
from brrs.core.messaging import MessageType
from brrs.environment.movement import get_coordinates


class SurveillanceAgent(CommAgent):
    """
    Surveillance Agent:
    - Monitors bank silent alarm trigger and scans CCTV camera sensor network
    - Fuses camera detections into incident confidence level: 1 - prod(1 - c_i)
    - Sends INCIDENT_ALERT to Command & Intelligence Agent upon detection
    - Continuously emits ROBBER_SIGHTING messages with estimated location and heading
    """

    def __init__(
        self,
        model: mesa.Model,
        zone_id: int = 1,
        detection_threshold: float = 0.7,
        alarm_prob: float = 0.8,
        alarm_delay_min: int = 15,
        alarm_delay_max: int = 45,
    ):
        super().__init__(model, name=f"surveillance_z{zone_id}", role="surveillance")
        self.zone_id = zone_id
        self.detection_threshold = detection_threshold
        self.alarm_fired = False
        self.incident_detected = False
        self.last_sighting: tuple[float, float, int] | None = None  # (x, y, tick)

        # Silent alarm scheduling
        if model.random.random() < alarm_prob:
            self.alarm_tick = model.random.randint(alarm_delay_min, alarm_delay_max)
        else:
            self.alarm_tick = None

    def perceive(self) -> None:
        self.fetch_messages()

        current_tick = self.model.steps
        robber = self.model.robber_agent
        rx, ry = get_coordinates(self.model.city_map, robber.pos)

        # 1. Bank Silent Alarm check
        if self.alarm_tick is not None and not self.alarm_fired and current_tick >= self.alarm_tick:
            self.alarm_fired = True
            if not self.incident_detected:
                self.incident_detected = True
                self.model.metrics.record_detection(current_tick)
                bx, by = self.model.city_map.node_coords(self.model.city_map.bank_node)
                self.send(
                    recipient="role:command",
                    topic="incident.alerts",
                    type=MessageType.INCIDENT_ALERT,
                    payload={
                        "source": "bank_alarm",
                        "location_node": self.model.city_map.bank_node,
                        "x": bx,
                        "y": by,
                        "confidence": 1.0,
                        "tick": current_tick,
                    },
                    priority=10,
                )

        # 2. CCTV Network Scan
        detections = self.model.cctv_network.scan(rx, ry)
        if detections:
            # Multi-camera confidence fusion: 1 - prod(1 - c_i)
            prod_miss = 1.0
            for d in detections:
                prod_miss *= (1.0 - d.confidence)
            combined_confidence = 1.0 - prod_miss

            # Check if this triggers incident detection
            if not self.incident_detected and combined_confidence >= self.detection_threshold:
                self.incident_detected = True
                self.model.metrics.record_detection(current_tick)
                best_det = max(detections, key=lambda d: d.confidence)
                self.send(
                    recipient="role:command",
                    topic="incident.alerts",
                    type=MessageType.INCIDENT_ALERT,
                    payload={
                        "source": "cctv",
                        "location_node": best_det.nearest_node,
                        "x": best_det.estimated_x,
                        "y": best_det.estimated_y,
                        "confidence": round(combined_confidence, 2),
                        "tick": current_tick,
                    },
                    priority=10,
                )

            # Emit ROBBER_SIGHTING if incident is active
            if self.incident_detected:
                best_det = max(detections, key=lambda d: d.confidence)
                
                # Estimate velocity heading from last sighting
                est_heading: tuple[float, float] | None = None
                if self.last_sighting is not None:
                    lx, ly, ltick = self.last_sighting
                    dt = max(1, current_tick - ltick)
                    dx = (best_det.estimated_x - lx) / dt
                    dy = (best_det.estimated_y - ly) / dt
                    mag = math.hypot(dx, dy)
                    if mag > 0.1:
                        est_heading = (dx / mag, dy / mag)

                self.last_sighting = (best_det.estimated_x, best_det.estimated_y, current_tick)

                self.send(
                    recipient="role:command",
                    topic="surveillance.sightings",
                    type=MessageType.ROBBER_SIGHTING,
                    payload={
                        "camera_id": best_det.camera_id,
                        "nearest_node": best_det.nearest_node,
                        "x": best_det.estimated_x,
                        "y": best_det.estimated_y,
                        "confidence": round(best_det.confidence, 2),
                        "heading": est_heading,
                        "tick": current_tick,
                    },
                    priority=5,
                )

    def decide(self) -> None:
        pass

    def act(self) -> None:
        pass

    def state_dict(self) -> dict[str, Any]:
        return {
            "name": self.agent_name,
            "role": self.role,
            "zone_id": self.zone_id,
            "incident_detected": self.incident_detected,
            "alarm_fired": self.alarm_fired,
            "last_sighting_tick": self.last_sighting[2] if self.last_sighting else None,
        }
