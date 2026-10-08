from __future__ import annotations
import math
import random
from dataclasses import dataclass
import networkx as nx
from brrs.config import CCTVConfig
from brrs.environment.city_map import CityMap


@dataclass
class DetectionResult:
    camera_id: int
    detected: bool
    confidence: float
    estimated_x: float
    estimated_y: float
    nearest_node: int


class Camera:
    """Individual CCTV camera with spatial coverage, detection probability, and sensor noise."""

    def __init__(
        self,
        camera_id: int,
        node: int,
        city_map: CityMap,
        range_m: float,
        p_detect_max: float,
        noise_sigma_m: float,
        rng: random.Random,
    ):
        self.camera_id = camera_id
        self.node = node
        self.city_map = city_map
        self.range_m = range_m
        self.p_detect_max = p_detect_max
        self.noise_sigma_m = noise_sigma_m
        self.rng = rng
        self.x, self.y = city_map.node_coords(node)

    def sense(self, target_x: float, target_y: float) -> DetectionResult | None:
        """Sense target position. Returns DetectionResult if triggered, else None."""
        dist = math.hypot(target_x - self.x, target_y - self.y)
        if dist > self.range_m:
            return None

        # Probability decreases with distance to periphery of camera cone
        p_detect = self.p_detect_max * max(0.0, 1.0 - (dist / self.range_m))
        if self.rng.random() > p_detect:
            return None

        # Add Gaussian noise
        noise_x = self.rng.gauss(0.0, self.noise_sigma_m)
        noise_y = self.rng.gauss(0.0, self.noise_sigma_m)
        est_x = target_x + noise_x
        est_y = target_y + noise_y

        # Snap to nearest node for discrete reasoning support
        nearest_node = min(
            self.city_map.graph.nodes(),
            key=lambda n: math.hypot(
                self.city_map.graph.nodes[n]["x"] - est_x,
                self.city_map.graph.nodes[n]["y"] - est_y,
            ),
        )

        return DetectionResult(
            camera_id=self.camera_id,
            detected=True,
            confidence=max(0.1, min(1.0, p_detect)),
            estimated_x=est_x,
            estimated_y=est_y,
            nearest_node=nearest_node,
        )


class CCTVNetwork:
    """Manages placement and collective sensing of urban surveillance cameras."""

    def __init__(self, city_map: CityMap, config: CCTVConfig, seed: int | None = None):
        self.city_map = city_map
        self.config = config
        self.rng = random.Random(seed)
        self.cameras: list[Camera] = []
        self._place_cameras()

    def _place_cameras(self) -> None:
        count = self.config.count
        available_nodes = [
            n for n in self.city_map.graph.nodes()
            if n != self.city_map.bank_node and n not in self.city_map.exit_nodes
        ]

        if self.config.placement == "chokepoints":
            # Stratified radial distribution: inner downtown, mid-city arterial hubs, and outer perimeter exits
            bank_pos = self.city_map.node_coords(self.city_map.bank_node)
            dists = {
                n: math.hypot(self.city_map.graph.nodes[n]["x"] - bank_pos[0],
                              self.city_map.graph.nodes[n]["y"] - bank_pos[1])
                for n in available_nodes
            }
            max_dist = max(dists.values()) if dists else 1.0

            inner_nodes = [n for n in available_nodes if dists[n] < 0.35 * max_dist]
            mid_nodes = [n for n in available_nodes if 0.35 * max_dist <= dists[n] < 0.70 * max_dist]
            outer_nodes = [n for n in available_nodes if dists[n] >= 0.70 * max_dist]

            centrality = nx.betweenness_centrality(self.city_map.graph)
            inner_nodes.sort(key=lambda n: centrality.get(n, 0.0), reverse=True)
            mid_nodes.sort(key=lambda n: centrality.get(n, 0.0), reverse=True)
            outer_nodes.sort(key=lambda n: centrality.get(n, 0.0), reverse=True)

            # Allocate cameras across rings: ~30% inner, ~40% mid, ~30% outer
            n_inner = max(1, int(round(count * 0.3)))
            n_outer = max(1, int(round(count * 0.3)))
            n_mid = max(1, count - n_inner - n_outer)

            chosen_nodes = []
            if inner_nodes:
                chosen_nodes.extend(inner_nodes[:n_inner])
            if mid_nodes:
                chosen_nodes.extend(mid_nodes[:n_mid])
            if outer_nodes:
                chosen_nodes.extend(outer_nodes[:n_outer])

            # Fill any remaining quota from available nodes
            while len(chosen_nodes) < count and len(chosen_nodes) < len(available_nodes):
                rem = [n for n in available_nodes if n not in chosen_nodes]
                chosen_nodes.append(self.rng.choice(rem))
        elif self.config.placement == "bank_ring":
            # Nodes directly surrounding the bank
            bank_neighbors = list(self.city_map.neighbors(self.city_map.bank_node))
            if len(bank_neighbors) >= count:
                chosen_nodes = bank_neighbors[:count]
            else:
                chosen_nodes = bank_neighbors + self.rng.sample(
                    [n for n in available_nodes if n not in bank_neighbors],
                    min(count - len(bank_neighbors), len(available_nodes) - len(bank_neighbors)),
                )
        else:  # random
            chosen_nodes = self.rng.sample(available_nodes, min(count, len(available_nodes)))

        for i, node in enumerate(chosen_nodes):
            self.city_map.graph.nodes[node]["has_camera"] = True
            cam = Camera(
                camera_id=i,
                node=node,
                city_map=self.city_map,
                range_m=self.config.range_m,
                p_detect_max=self.config.p_detect_max,
                noise_sigma_m=self.config.noise_sigma_m,
                rng=random.Random(self.rng.randint(0, 1000000)),
            )
            self.cameras.append(cam)

    def scan(self, target_x: float, target_y: float) -> list[DetectionResult]:
        """Query all cameras against target coordinates."""
        detections = []
        for cam in self.cameras:
            res = cam.sense(target_x, target_y)
            if res is not None:
                detections.append(res)
        return detections

    def to_dict(self) -> list[dict]:
        """Serialize camera network for UI overlay."""
        return [
            {
                "id": cam.camera_id,
                "node": cam.node,
                "x": cam.x,
                "y": cam.y,
                "range_m": cam.range_m,
            }
            for cam in self.cameras
        ]
