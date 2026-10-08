import pytest
from brrs.environment.city_map import CityMap
from brrs.config import MapConfig
from brrs.environment.movement import EdgePosition
from brrs.core.capture import check_capture

def test_capture_same_node():
    city_map = CityMap(MapConfig(), seed=42)
    robber_pos = EdgePosition(u=10, v=10, offset_m=0.0)
    police_positions = {"police_1": EdgePosition(u=10, v=10, offset_m=0.0)}
    
    event = check_capture(
        city_map,
        robber_pos,
        robber_traversed_edges=[],
        police_positions=police_positions,
        police_traversed_edges={"police_1": []},
    )
    assert event.occurred is True
    assert event.intercepting_unit_id == "police_1"

def test_capture_head_on_edge_crossing():
    city_map = CityMap(MapConfig(), seed=42)
    robber_pos = EdgePosition(u=10, v=11, offset_m=30.0)
    police_positions = {"police_1": EdgePosition(u=11, v=10, offset_m=40.0)}

    # Both traversed opposite directions along the same edge in this tick
    robber_traversed = [(10, 11)]
    police_traversed = {"police_1": [(11, 10)]}

    event = check_capture(
        city_map,
        robber_pos,
        robber_traversed,
        police_positions,
        police_traversed,
    )
    assert event.occurred is True
    assert event.intercepting_unit_id == "police_1"
    assert "Opposite direction" in event.reason

def test_no_capture_when_distant():
    city_map = CityMap(MapConfig(), seed=42)
    robber_pos = EdgePosition(u=1, v=1, offset_m=0.0)
    police_positions = {"police_1": EdgePosition(u=30, v=30, offset_m=0.0)}

    event = check_capture(
        city_map,
        robber_pos,
        robber_traversed_edges=[],
        police_positions=police_positions,
        police_traversed_edges={"police_1": []},
    )
    assert event.occurred is False


def test_capture_multi_unit_surrounded():
    city_map = CityMap(MapConfig(), seed=42)
    # Robber at node 10
    robber_pos = EdgePosition(u=10, v=10, offset_m=0.0)
    # Two police units on adjacent edges within 20m of robber (each > 14m alone)
    police_positions = {
        "police_1": EdgePosition(u=10, v=11, offset_m=18.0),
        "police_2": EdgePosition(u=10, v=9, offset_m=19.0),
    }

    event = check_capture(
        city_map,
        robber_pos,
        robber_traversed_edges=[],
        police_positions=police_positions,
        police_traversed_edges={"police_1": [], "police_2": []},
        capture_radius_m=14.0,
    )
    assert event.occurred is True
    assert "surrounded" in event.reason.lower()


def test_capture_pursuit_overtake():
    city_map = CityMap(MapConfig(), seed=42)
    robber_pos = EdgePosition(u=10, v=11, offset_m=25.0)
    police_positions = {"police_1": EdgePosition(u=10, v=11, offset_m=12.0)}

    # Both on same edge, police closed within 13m
    event = check_capture(
        city_map,
        robber_pos,
        robber_traversed_edges=[],
        police_positions=police_positions,
        police_traversed_edges={"police_1": []},
        capture_radius_m=14.0,
    )
    assert event.occurred is True
    assert event.intercepting_unit_id == "police_1"


