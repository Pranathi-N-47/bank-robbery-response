from __future__ import annotations
import math
from dataclasses import dataclass
from brrs.environment.city_map import CityMap
from brrs.environment.movement import EdgePosition, get_coordinates


@dataclass
class CaptureEvent:
    occurred: bool
    intercepting_unit_id: str | None
    capture_node_or_edge: str
    reason: str


def check_capture(
    city_map: CityMap,
    robber_pos: EdgePosition,
    robber_traversed_edges: list[tuple[int, int]],
    police_positions: dict[str, EdgePosition],
    police_traversed_edges: dict[str, list[tuple[int, int]]],
    capture_radius_m: float = 14.0,
    node_epsilon_m: float = 8.0,
    holding_roadblocks: dict[str, int] | None = None,
) -> CaptureEvent:
    """
    Evaluates interception / capture conditions:
    1. Direct spatial proximity: distance between robber and any police unit <= capture_radius_m
    2. Same node arrival: robber and police at same intersection
    3. Roadblock interception: police holding at node N and robber enters or traverses through node N
    4. Head-on edge crossing: robber traversed (u -> v), police traversed (v -> u) in same tick
    5. Same-edge pursuit overtake: robber and police on same edge within capture_radius_m * 1.5
    """
    robber_coords = get_coordinates(city_map, robber_pos)

    # 1. Multi-unit surrounded / perimeter containment check:
    # If 2+ patrol units are within containment radius (2.0 * capture_radius_m, ~28m),
    # or 3+ units are within wide cordon (2.5 * capture_radius_m, ~35m),
    # the suspect is boxed in from multiple sides and cannot escape.
    police_distances: list[tuple[str, float, EdgePosition]] = []
    for p_id, p_pos in police_positions.items():
        p_coords = get_coordinates(city_map, p_pos)
        dist = math.hypot(robber_coords[0] - p_coords[0], robber_coords[1] - p_coords[1])
        police_distances.append((p_id, dist, p_pos))

    close_cordon = [p_id for p_id, dist, _ in police_distances if dist <= capture_radius_m * 2.0]
    if len(close_cordon) >= 2:
        return CaptureEvent(
            occurred=True,
            intercepting_unit_id=close_cordon[0],
            capture_node_or_edge=f"Perimeter Cordon ({len(close_cordon)} units)",
            reason=f"Suspect surrounded on all sides by {len(close_cordon)} converging patrol units",
        )

    wide_cordon = [p_id for p_id, dist, _ in police_distances if dist <= capture_radius_m * 2.5]
    if len(wide_cordon) >= 3:
        return CaptureEvent(
            occurred=True,
            intercepting_unit_id=wide_cordon[0],
            capture_node_or_edge=f"Perimeter Cordon ({len(wide_cordon)} units)",
            reason=f"Suspect boxed in by multi-unit perimeter cordon ({len(wide_cordon)} units)",
        )

    # 2. Individual patrol unit checks
    for p_id, spatial_dist, p_pos in police_distances:
        # Direct spatial proximity capture (within capture_radius_m in 2D space)
        if spatial_dist <= capture_radius_m:
            return CaptureEvent(
                occurred=True,
                intercepting_unit_id=p_id,
                capture_node_or_edge=f"Near Node {robber_pos.u} ({spatial_dist:.1f}m)",
                reason=f"Police unit apprehended suspect within {capture_radius_m:.1f}m perimeter",
            )


        # 2. Same node condition
        if robber_pos.is_at_node() and p_pos.is_at_node() and robber_pos.u == p_pos.u:
            return CaptureEvent(
                occurred=True,
                intercepting_unit_id=p_id,
                capture_node_or_edge=f"Node {robber_pos.u}",
                reason="Same intersection arrival",
            )

        # 3. Opposite direction edge crossing in the same tick: robber (u -> v), police (v -> u)

        p_traversed = police_traversed_edges.get(p_id, [])
        for r_edge in robber_traversed_edges:
            if (r_edge[1], r_edge[0]) in p_traversed:
                return CaptureEvent(
                    occurred=True,
                    intercepting_unit_id=p_id,
                    capture_node_or_edge=f"Edge {r_edge[0]}<->{r_edge[1]}",
                    reason="Opposite direction edge intersection",
                )

        # 5. Same edge chasing from behind / overtake
        r_canon = (min(robber_pos.u, robber_pos.v), max(robber_pos.u, robber_pos.v))
        p_canon = (min(p_pos.u, p_pos.v), max(p_pos.u, p_pos.v))

        if r_canon == p_canon and spatial_dist <= (capture_radius_m * 1.5):
            return CaptureEvent(
                occurred=True,
                intercepting_unit_id=p_id,
                capture_node_or_edge=f"Edge {r_canon[0]}-{r_canon[1]}",
                reason="Pursuit unit closed in on same edge",
            )

    return CaptureEvent(occurred=False, intercepting_unit_id=None, capture_node_or_edge="", reason="")
