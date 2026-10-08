from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class MetricsTracker:
    detection_tick: int | None = None
    first_response_tick: int | None = None
    interception_tick: int | None = None
    outcome: Literal["IN_PROGRESS", "INTERCEPTED", "ESCAPED", "TIMEOUT"] = "IN_PROGRESS"
    intercepting_unit: str | None = None
    
    total_police_travel_distance_m: float = 0.0
    total_robber_travel_distance_m: float = 0.0
    total_route_replannings: int = 0
    replans_by_reason: dict[str, int] = field(default_factory=lambda: {"traffic": 0, "destination": 0, "pursuit": 0})
    
    robber_route_changes: int = 0
    total_messages_exchanged: int = 0
    astar_nodes_expanded_total: int = 0
    
    # Timeseries for UI chart
    uncertainty_radius_history: list[float] = field(default_factory=list)
    police_robber_min_dist_history: list[float] = field(default_factory=list)

    def record_detection(self, tick: int) -> None:
        if self.detection_tick is None:
            self.detection_tick = tick

    def record_first_response(self, tick: int) -> None:
        if self.first_response_tick is None and self.detection_tick is not None:
            self.first_response_tick = tick

    def record_replan(self, reason: str = "destination") -> None:
        self.total_route_replannings += 1
        self.replans_by_reason[reason] = self.replans_by_reason.get(reason, 0) + 1

    def to_summary_dict(self) -> dict:
        det_time = self.detection_tick if self.detection_tick is not None else -1
        
        # If a police unit caught the robber before any unit reached a holding interception point,
        # the response time is the duration between detection and interception.
        effective_resp_tick = self.first_response_tick
        if effective_resp_tick is None and self.interception_tick is not None:
            effective_resp_tick = self.interception_tick

        resp_time = (effective_resp_tick - self.detection_tick) if (effective_resp_tick is not None and self.detection_tick is not None) else -1
        intercept_time = (self.interception_tick - self.detection_tick) if (self.interception_tick is not None and self.detection_tick is not None) else -1

        return {
            "outcome": self.outcome,
            "intercepting_unit": self.intercepting_unit,
            "detection_time_ticks": det_time,
            "response_time_ticks": resp_time,
            "interception_time_ticks": intercept_time,
            "interception_success": (self.outcome == "INTERCEPTED"),
            "total_police_travel_distance_m": round(self.total_police_travel_distance_m, 1),
            "total_robber_travel_distance_m": round(self.total_robber_travel_distance_m, 1),
            "total_route_replannings": self.total_route_replannings,
            "replans_by_reason": self.replans_by_reason,
            "robber_route_changes": self.robber_route_changes,
            "total_messages": self.total_messages_exchanged,
            "astar_nodes_expanded": self.astar_nodes_expanded_total,
        }
