from __future__ import annotations
import math
import random
from typing import Literal
import networkx as nx
from pydantic import BaseModel
from brrs.config import MapConfig


class NodeData(BaseModel):
    id: int
    x: float
    y: float
    role: Literal["intersection", "bank", "station", "exit"]
    has_camera: bool = False
    name: str = ""


class EdgeData(BaseModel):
    u: int
    v: int
    length_m: float
    speed_limit: float
    is_arterial: bool = False


class CityMap:
    """Represents the city road network, node roles, coordinates, and physical properties."""

    def __init__(self, config: MapConfig, seed: int | None = None):
        self.config = config
        self.rng = random.Random(seed)
        self.graph = nx.Graph()
        self.bank_node: int = -1
        self.exit_nodes: list[int] = []
        self.station_nodes: list[int] = []
        self._build_grid()

    def _build_grid(self) -> None:
        rows = self.config.rows
        cols = self.config.cols
        spacing = self.config.block_m
        jitter = self.config.jitter

        # 1. Create nodes with (x, y) coordinates
        node_id = 0
        grid_to_id: dict[tuple[int, int], int] = {}
        for r in range(rows):
            for c in range(cols):
                base_x = c * spacing
                base_y = r * spacing
                if jitter > 0:
                    offset_x = self.rng.uniform(-jitter * spacing, jitter * spacing)
                    offset_y = self.rng.uniform(-jitter * spacing, jitter * spacing)
                else:
                    offset_x, offset_y = 0.0, 0.0
                
                x = base_x + offset_x
                y = base_y + offset_y
                self.graph.add_node(
                    node_id,
                    x=x,
                    y=y,
                    role="intersection",
                    has_camera=False,
                    name=f"N{node_id}"
                )
                grid_to_id[(r, c)] = node_id
                node_id += 1

        # 2. Select arterial rows / columns
        n_arterials = min(self.config.arterials, min(rows, cols))
        arterial_rows = set(self.rng.sample(range(1, rows - 1), min(n_arterials // 2, rows - 2))) if rows > 2 else set()
        arterial_cols = set(self.rng.sample(range(1, cols - 1), min((n_arterials + 1) // 2, cols - 2))) if cols > 2 else set()

        # 3. Add edges with physical distance
        all_candidate_edges: list[tuple[int, int, bool]] = []
        for r in range(rows):
            for c in range(cols):
                u = grid_to_id[(r, c)]
                # Horizontal neighbor
                if c + 1 < cols:
                    v = grid_to_id[(r, c + 1)]
                    is_art = (r in arterial_rows)
                    all_candidate_edges.append((u, v, is_art))
                # Vertical neighbor
                if r + 1 < rows:
                    v = grid_to_id[(r + 1, c)]
                    is_art = (c in arterial_cols)
                    all_candidate_edges.append((u, v, is_art))

        for u, v, is_art in all_candidate_edges:
            p1 = (self.graph.nodes[u]["x"], self.graph.nodes[u]["y"])
            p2 = (self.graph.nodes[v]["x"], self.graph.nodes[v]["y"])
            dist = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
            spd = 20.0 if is_art else 12.0  # arterial vs standard street limit m/s
            self.graph.add_edge(u, v, length_m=dist, speed_limit=spd, is_arterial=is_art)

        # 4. Stochastic edge removal without breaking connectivity
        if self.config.removal_prob > 0:
            edges = list(self.graph.edges())
            self.rng.shuffle(edges)
            for u, v in edges:
                if self.rng.random() < self.config.removal_prob:
                    edge_data = self.graph.get_edge_data(u, v)
                    self.graph.remove_edge(u, v)
                    if not nx.is_connected(self.graph):
                        # Re-add to preserve full network connectivity
                        self.graph.add_edge(u, v, **edge_data)

        # 5. Place roles
        # Bank: center node
        center_r, center_c = rows // 2, cols // 2
        self.bank_node = grid_to_id[(center_r, center_c)]
        self.graph.nodes[self.bank_node]["role"] = "bank"
        self.graph.nodes[self.bank_node]["name"] = "City Central Bank"

        # Exits: boundary nodes
        boundary_nodes = []
        for r in range(rows):
            for c in range(cols):
                if r == 0 or r == rows - 1 or c == 0 or c == cols - 1:
                    nid = grid_to_id[(r, c)]
                    if nid != self.bank_node:
                        boundary_nodes.append(nid)

        n_exits = min(self.config.n_exits, len(boundary_nodes))
        # Pick maximally separated boundary nodes if possible
        self.exit_nodes = self.rng.sample(boundary_nodes, n_exits)
        for i, ex in enumerate(self.exit_nodes):
            self.graph.nodes[ex]["role"] = "exit"
            self.graph.nodes[ex]["name"] = f"Highway Exit {i+1}"

        # Police Stations: farthest-point sampling away from bank and each other
        candidate_stations = [
            n for n in self.graph.nodes()
            if n != self.bank_node and n not in self.exit_nodes
        ]
        # At least 10 distinct stations so every police unit in any scenario gets a unique starting spot
        num_stations = min(12, len(candidate_stations))
        chosen_stations: list[int] = []
        for _ in range(num_stations):
            best_node = None
            best_min_dist = -1.0
            for cand in candidate_stations:
                if cand in chosen_stations:
                    continue
                # Calculate min distance to bank and already chosen stations
                refs = [self.bank_node] + chosen_stations
                cand_pos = (self.graph.nodes[cand]["x"], self.graph.nodes[cand]["y"])
                min_d = min(
                    math.hypot(cand_pos[0] - self.graph.nodes[r]["x"], cand_pos[1] - self.graph.nodes[r]["y"])
                    for r in refs
                )
                if min_d > best_min_dist:
                    best_min_dist = min_d
                    best_node = cand
            if best_node is not None:
                chosen_stations.append(best_node)

        self.station_nodes = chosen_stations
        for i, st in enumerate(self.station_nodes):
            self.graph.nodes[st]["role"] = "station"
            self.graph.nodes[st]["name"] = f"Precinct {i+1}"

    def node_coords(self, node: int) -> tuple[float, float]:
        """Return (x, y) coordinates of node."""
        return self.graph.nodes[node]["x"], self.graph.nodes[node]["y"]

    def edge_length(self, u: int, v: int) -> float:
        """Return distance in meters between adjacent nodes u and v."""
        return self.graph.edges[u, v]["length_m"]

    def edge_speed_limit(self, u: int, v: int) -> float:
        """Return speed limit in m/s on edge (u, v)."""
        return self.graph.edges[u, v]["speed_limit"]

    def neighbors(self, node: int) -> list[int]:
        """Return adjacent nodes."""
        return list(self.graph.neighbors(node))

    def euclidean_distance(self, u: int, v: int) -> float:
        """Euclidean distance between two nodes."""
        x1, y1 = self.node_coords(u)
        x2, y2 = self.node_coords(v)
        return math.hypot(x1 - x2, y1 - y2)

    def to_dict(self) -> dict:
        """Serialize map for frontend and client transmission."""
        nodes = []
        for n, d in self.graph.nodes(data=True):
            nodes.append({
                "id": n,
                "x": d["x"],
                "y": d["y"],
                "role": d["role"],
                "name": d.get("name", f"N{n}"),
                "has_camera": d.get("has_camera", False),
            })
        edges = []
        for u, v, d in self.graph.edges(data=True):
            edges.append({
                "u": u,
                "v": v,
                "length_m": d["length_m"],
                "speed_limit": d["speed_limit"],
                "is_arterial": d.get("is_arterial", False),
            })
        return {
            "nodes": nodes,
            "edges": edges,
            "bank_node": self.bank_node,
            "exit_nodes": self.exit_nodes,
            "station_nodes": self.station_nodes,
        }
