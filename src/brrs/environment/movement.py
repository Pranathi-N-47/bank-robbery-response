from __future__ import annotations
import math
from dataclasses import dataclass
from brrs.environment.city_map import CityMap


@dataclass
class EdgePosition:
    """Represents a position along directed edge u -> v at a specific offset in meters."""
    u: int
    v: int
    offset_m: float

    def is_at_node(self) -> bool:
        return self.offset_m <= 0.001


def get_coordinates(city_map: CityMap, pos: EdgePosition) -> tuple[float, float]:
    """Compute interpolated (x, y) coordinates from EdgePosition."""
    if pos.u == pos.v or pos.is_at_node():
        return city_map.node_coords(pos.u)
    
    total_len = city_map.edge_length(pos.u, pos.v)
    if total_len <= 0:
        return city_map.node_coords(pos.u)
    
    t = min(1.0, max(0.0, pos.offset_m / total_len))
    x1, y1 = city_map.node_coords(pos.u)
    x2, y2 = city_map.node_coords(pos.v)
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def move_along_route(
    city_map: CityMap,
    current_pos: EdgePosition,
    route: list[int],
    distance_budget_m: float,
    blocked_nodes: set[int] | None = None,
) -> tuple[EdgePosition, list[int], list[tuple[int, int]], float]:
    """
    Move an entity along a route with a given distance budget.
    If blocked_nodes is specified, movement halts immediately upon reaching any blocked roadblock node.
    
    Returns:
        (new_position, updated_route, edges_traversed, actual_distance_moved)
    """
    remaining_dist = distance_budget_m
    traversed_edges: list[tuple[int, int]] = []
    actual_moved = 0.0

    pos_u = current_pos.u
    pos_v = current_pos.v
    offset = current_pos.offset_m

    # If at node (or pos_u == pos_v), we must be prepared to transition to the first edge in route
    while remaining_dist > 0.0001:
        # Case 1: We are currently mid-edge between u and v
        if pos_u != pos_v:
            edge_len = city_map.edge_length(pos_u, pos_v)
            needed_to_reach_v = edge_len - offset
            traversed_edges.append((pos_u, pos_v))

            if remaining_dist < needed_to_reach_v:
                # Still within the current edge
                offset += remaining_dist
                actual_moved += remaining_dist
                remaining_dist = 0.0
                break
            else:
                # We reach node v
                offset = 0.0
                actual_moved += needed_to_reach_v
                remaining_dist -= needed_to_reach_v
                pos_u = pos_v

                # If route has pos_v at start, pop it
                if route and route[0] == pos_v:
                    route = route[1:]

                # If node v is a blocked roadblock, halt movement right here at node v!
                if blocked_nodes and pos_v in blocked_nodes:
                    pos_v = pos_u
                    remaining_dist = 0.0
                    break

        # Case 2: We are at node pos_u, check route for next segment
        if not route:
            # Reached end of assigned route, stay at pos_u
            pos_v = pos_u
            offset = 0.0
            break

        next_node = route[0]
        if next_node == pos_u:
            route = route[1:]
            continue

        # Start traveling edge pos_u -> next_node
        pos_v = next_node
        offset = 0.0
        edge_len = city_map.edge_length(pos_u, pos_v)
        traversed_edges.append((pos_u, pos_v))

        if remaining_dist < edge_len:
            offset = remaining_dist
            actual_moved += remaining_dist
            remaining_dist = 0.0
            break
        else:
            # Traversed the whole edge and reached next_node!
            actual_moved += edge_len
            remaining_dist -= edge_len
            pos_u = pos_v
            route = route[1:]
            pos_v = pos_u
            offset = 0.0

            # If next_node is a blocked roadblock, halt movement right here at this node!
            if blocked_nodes and pos_u in blocked_nodes:
                remaining_dist = 0.0
                break

    return (
        EdgePosition(u=pos_u, v=pos_v, offset_m=offset),
        route,
        traversed_edges,
        actual_moved,
    )
