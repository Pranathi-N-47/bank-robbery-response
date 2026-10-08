from __future__ import annotations
import math
from typing import Any
import mesa
from brrs.config import ScenarioConfig
from brrs.environment.city_map import CityMap
from brrs.environment.traffic import TrafficModel
from brrs.environment.cctv import CCTVNetwork
from brrs.environment.movement import get_coordinates
from brrs.core.messaging import MessageBus, MessageType
from brrs.core.capture import check_capture
from brrs.core.metrics import MetricsTracker
from brrs.agents.surveillance import SurveillanceAgent
from brrs.agents.command_intel import CommandIntelAgent
from brrs.agents.dispatch import DispatchAgent
from brrs.agents.patrol import PatrolAgent
from brrs.agents.robber import RobberAgent
from brrs.agents.civilian import CivilianAgent


class BankRobberyModel(mesa.Model):
    """
    Central simulation model orchestrating the Daytime Bank Robbery Response Multi-Agent System.
    """

    def __init__(self, config: ScenarioConfig, seed: int | None = None):
        super().__init__(seed=seed)
        self.config = config
        self.bus = MessageBus()
        self.metrics = MetricsTracker()

        # 1. Environment Models
        self.city_map = CityMap(config.map, seed=seed)
        self.traffic_model = TrafficModel(self.city_map, config.traffic, seed=seed)
        self.cctv_network = CCTVNetwork(self.city_map, config.cctv, seed=seed)

        # 2. Instantiate Agents
        self.surveillance_agents: list[SurveillanceAgent] = []
        for z in range(config.surveillance.zones):
            s_agent = SurveillanceAgent(
                self,
                zone_id=z + 1,
                detection_threshold=config.surveillance.detection_threshold,
                alarm_prob=config.alarm.probability,
                alarm_delay_min=config.alarm.delay_min,
                alarm_delay_max=config.alarm.delay_max,
            )
            self.surveillance_agents.append(s_agent)

        self.command_agent = CommandIntelAgent(
            self,
            top_k_routes=config.command.top_k_routes,
            horizon_s=config.command.horizon_s,
            safety_buffer_s=config.command.safety_buffer_s,
            switch_gain=config.command.switch_gain,
            min_route_prob=config.command.min_route_prob,
        )

        self.dispatch_agent = DispatchAgent(self)

        self.patrol_agents: list[PatrolAgent] = []
        # Partition precinct stations into 4 geographic quadrants around the bank: NW, NE, SW, SE
        bank_x, bank_y = self.city_map.node_coords(self.city_map.bank_node)
        quadrants: dict[str, list[int]] = {"NW": [], "NE": [], "SW": [], "SE": []}
        for st in self.city_map.station_nodes:
            sx, sy = self.city_map.node_coords(st)
            q = ("S" if sy >= bank_y else "N") + ("E" if sx >= bank_x else "W")
            quadrants[q].append(st)

        # Shuffle each quadrant's stations using the simulation's random generator
        for q_list in quadrants.values():
            self.random.shuffle(q_list)

        # Assign police units cyclically across quadrants: NW -> SE -> NE -> SW
        # This guarantees police units surround the city from multiple directions
        quad_cycle = ["NW", "SE", "NE", "SW"]
        assigned_stations: list[int] = []
        for i in range(config.police.count):
            q_key = quad_cycle[i % len(quad_cycle)]
            if quadrants[q_key]:
                assigned_stations.append(quadrants[q_key].pop(0))
            else:
                remaining = [s for s in self.city_map.station_nodes if s not in assigned_stations]
                assigned_stations.append(self.random.choice(remaining) if remaining else self.random.choice(self.city_map.station_nodes))

        for i in range(config.police.count):
            st_node = assigned_stations[i]
            p_agent = PatrolAgent(
                self,
                unit_id=i + 1,
                station_node=st_node,
                speed=config.police.speed,
                report_interval=config.police.report_interval,
                replan_threshold=config.police.replan_threshold,
            )
            self.patrol_agents.append(p_agent)

        self.robber_agent = RobberAgent(
            self,
            speed=config.robber.speed,
            vision_radius_m=config.robber.vision_radius_m,
            temperature=config.robber.temperature,
            danger_lambda=config.robber.danger_lambda,
            threat_radius_m=config.robber.threat_radius_m,
            cooldown_ticks=config.robber.cooldown_ticks,
            memory_ticks=config.robber.memory_ticks,
            robbery_duration=config.sim.robbery_duration,
        )

        self.civilian_agents: list[CivilianAgent] = []
        all_nodes = list(self.city_map.graph.nodes())
        for i in range(config.civilians.count):
            st_node = self.random.choice(all_nodes)
            c_agent = CivilianAgent(
                self,
                civilian_id=i + 1,
                start_node=st_node,
                speed=config.civilians.speed,
            )
            self.civilian_agents.append(c_agent)

        self.is_finished = False

    def step(self) -> None:
        """
        Orchestrates one discrete simulation tick in rigorous MAS sequence:
        1. Environment & traffic update, civilians move
        2. Robber agent step
        3. Surveillance agents step
        4. Command and Intelligence agent step
        5. Dispatch agent step
        6. Patrol agents step
        7. Termination & capture checks
        """
        if self.is_finished:
            return

        # Phase 1: Environment & Civilians
        # Update civilian counts per edge
        edge_counts: dict[tuple[int, int], int] = {}
        for civ in self.civilian_agents:
            civ.step()
            edge_key = (civ.pos.u, civ.pos.v)
            edge_counts[edge_key] = edge_counts.get(edge_key, 0) + 1
        self.traffic_model.set_civilian_counts(edge_counts)
        self.traffic_model.step()

        # Phase 2: Robber Agent
        self.robber_agent.step()

        # Phase 3: Surveillance Agents
        for s_agent in self.surveillance_agents:
            s_agent.step()

        # Phase 4: Command & Intelligence Agent
        self.command_agent.step()

        # Phase 5: Dispatch Agent
        self.dispatch_agent.step()

        # Phase 6: Patrol Agents
        for p_agent in self.patrol_agents:
            p_agent.step()

        # Phase 7: Capture & Termination Evaluation
        p_positions = {p.agent_name: p.pos for p in self.patrol_agents}
        p_traversed = {p.agent_name: p.traversed_edges for p in self.patrol_agents}

        capture_event = check_capture(
            self.city_map,
            self.robber_agent.pos,
            self.robber_agent.traversed_edges,
            p_positions,
            p_traversed,
            capture_radius_m=self.config.police.capture_radius_m,
        )


        rx, ry = get_coordinates(self.city_map, self.robber_agent.pos)
        min_p_dist = min(
            math.hypot(rx - get_coordinates(self.city_map, p.pos)[0], ry - get_coordinates(self.city_map, p.pos)[1])
            for p in self.patrol_agents
        )
        self.metrics.police_robber_min_dist_history.append(min_p_dist)
        self.metrics.total_messages_exchanged = len(self.bus.event_log)

        if capture_event.occurred:
            self.robber_agent.phase = "CAUGHT"
            self.is_finished = True
            self.metrics.outcome = "INTERCEPTED"
            self.metrics.interception_tick = self.steps
            self.metrics.intercepting_unit = capture_event.intercepting_unit_id
            self.bus.send(
                tick=self.steps,
                sender="model",
                recipient=None,
                topic="incident.status",
                type=MessageType.INCIDENT_CLOSED,
                payload={"outcome": "INTERCEPTED", "unit": capture_event.intercepting_unit_id, "reason": capture_event.reason},
            )
        elif self.robber_agent.phase == "ESCAPED":
            self.is_finished = True
            self.metrics.outcome = "ESCAPED"
            self.bus.send(
                tick=self.steps,
                sender="model",
                recipient=None,
                topic="incident.status",
                type=MessageType.INCIDENT_CLOSED,
                payload={"outcome": "ESCAPED"},
            )
        elif self.steps >= self.config.sim.max_ticks:
            self.is_finished = True
            self.metrics.outcome = "TIMEOUT"
            self.bus.send(
                tick=self.steps,
                sender="model",
                recipient=None,
                topic="incident.status",
                type=MessageType.INCIDENT_CLOSED,
                payload={"outcome": "TIMEOUT"},
            )

    def snapshot(self) -> dict[str, Any]:
        """Produce full serialization snapshot of current simulation state."""
        rx, ry = get_coordinates(self.city_map, self.robber_agent.pos)

        police_data = []
        for p in self.patrol_agents:
            px, py = get_coordinates(self.city_map, p.pos)
            police_data.append({
                "id": p.agent_name,
                "x": round(px, 1),
                "y": round(py, 1),
                "status": p.status,
                "destination": p.destination,
                "route": p.route,
                "replans": p.route_replans,
                "distance_m": round(p.distance_travelled_m, 1),
            })

        civ_coords = []
        for c in self.civilian_agents:
            cx, cy = get_coordinates(self.city_map, c.pos)
            civ_coords.append([round(cx, 1), round(cy, 1)])

        return {
            "tick": self.steps,
            "is_finished": self.is_finished,
            "metrics": self.metrics.to_summary_dict(),
            "robber": {
                "x": round(rx, 1),
                "y": round(ry, 1),
                "phase": self.robber_agent.phase,
                "route": self.robber_agent.route,
                "target_exit": self.robber_agent.target_exit,
                "visible_police": len(self.robber_agent.police_memory),
                "vision_radius_m": self.robber_agent.vision_radius_m,
                "threat_radius_m": self.robber_agent.threat_radius_m,
            },
            "police": police_data,
            "civilians": civ_coords,
            "traffic": self.traffic_model.to_dict(),
            "command": {
                "estimated_node": self.command_agent.estimated_node,
                "estimated_pos": self.command_agent.estimated_pos,
                "uncertainty_radius_m": round(self.command_agent.uncertainty_radius_m, 1),
                "predicted_routes": [
                    {"path": r.path, "prob": round(r.probability, 3)}
                    for r in self.command_agent.predicted_routes
                ],
                "interception_points": [
                    {"point": c.point, "prob": round(c.route_prob, 3), "margin_s": round(c.margin_s, 1)}
                    for c in self.command_agent.active_plan_candidates
                ],
            },
            "surveillance": [
                s.state_dict() for s in self.surveillance_agents
            ],
            "dispatch": self.dispatch_agent.state_dict(),
            "recent_messages": self.bus.get_recent_events(limit=15),
        }
