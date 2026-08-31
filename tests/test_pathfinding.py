"""Unit tests for the hand-written Dijkstra pathfinding module."""

from flyin.models.connection import Connection
from flyin.models.graph import Graph
from flyin.models.zone import Zone, ZoneType
from flyin.pathfinding.dijkstra import Pathfinder


def _linear_graph() -> tuple[Graph, Zone, Zone]:
    """Build a simple start-a-b-end linear graph, all normal zones.

    Returns:
        A tuple of (graph, start_zone, end_zone).
    """
    graph = Graph()
    start = Zone("start", 0, 0, is_start=True)
    a = Zone("a", 1, 0)
    b = Zone("b", 2, 0)
    end = Zone("end", 3, 0, is_end=True)
    for zone in (start, a, b, end):
        graph.add_zone(zone)
    graph.add_connection(Connection(start, a))
    graph.add_connection(Connection(a, b))
    graph.add_connection(Connection(b, end))
    return graph, start, end


def test_shortest_path_on_linear_graph() -> None:
    """A simple linear path should be found with cost equal to hops."""
    graph, start, end = _linear_graph()
    result = Pathfinder().find_shortest_path(graph, start, end)

    assert result is not None
    assert [zone.name for zone in result.path] == ["start", "a", "b", "end"]
    assert result.total_cost == 3


def test_shortest_path_start_equals_end() -> None:
    """Searching from a zone to itself should yield a zero-cost path."""
    graph, start, _end = _linear_graph()
    result = Pathfinder().find_shortest_path(graph, start, start)

    assert result is not None
    assert [zone.name for zone in result.path] == ["start"]
    assert result.total_cost == 0


def test_shortest_path_returns_none_when_unreachable() -> None:
    """No path exists if the only route is severed by a blocked zone."""
    graph = Graph()
    start = Zone("start", 0, 0, is_start=True)
    wall = Zone("wall", 1, 0, zone_type=ZoneType.BLOCKED)
    end = Zone("end", 2, 0, is_end=True)
    for zone in (start, wall, end):
        graph.add_zone(zone)
    graph.add_connection(Connection(start, wall))
    graph.add_connection(Connection(wall, end))

    assert Pathfinder().find_shortest_path(graph, start, end) is None


def test_shortest_path_prefers_cheaper_route_over_restricted() -> None:
    """A longer but cheaper route must win over a shorter restricted one.

    Mirrors the subject's example map: going through a restricted
    zone (cost 2) is more expensive than a two-hop normal/priority
    route (cost 1 + 1), even though both reach the end.
    """
    graph = Graph()
    start = Zone("hub", 0, 0, is_start=True)
    restricted = Zone("roof1", 1, 0, zone_type=ZoneType.RESTRICTED)
    normal = Zone("roof2", 2, 0, zone_type=ZoneType.NORMAL)
    priority = Zone("corridorA", 1, 1, zone_type=ZoneType.PRIORITY)
    tunnel = Zone("tunnelB", 2, 1, zone_type=ZoneType.NORMAL)
    end = Zone("goal", 3, 0, is_end=True)
    for zone in (start, restricted, normal, priority, tunnel, end):
        graph.add_zone(zone)
    graph.add_connection(Connection(start, restricted))
    graph.add_connection(Connection(restricted, normal))
    graph.add_connection(Connection(normal, end))
    graph.add_connection(Connection(start, priority))
    graph.add_connection(Connection(priority, tunnel))
    graph.add_connection(Connection(tunnel, end))

    result = Pathfinder().find_shortest_path(graph, start, end)

    assert result is not None
    assert [zone.name for zone in result.path] == [
        "hub",
        "corridorA",
        "tunnelB",
        "goal",
    ]
    assert result.total_cost == 3


def test_shortest_path_skips_blocked_zone_for_alternate_route() -> None:
    """A blocked zone on one branch must be bypassed, not fail the search."""
    graph = Graph()
    start = Zone("start", 0, 0, is_start=True)
    wall = Zone("wall", 1, 0, zone_type=ZoneType.BLOCKED)
    detour = Zone("detour", 1, 1)
    end = Zone("end", 2, 0, is_end=True)
    for zone in (start, wall, detour, end):
        graph.add_zone(zone)
    graph.add_connection(Connection(start, wall))
    graph.add_connection(Connection(wall, end))
    graph.add_connection(Connection(start, detour))
    graph.add_connection(Connection(detour, end))

    result = Pathfinder().find_shortest_path(graph, start, end)

    assert result is not None
    assert [zone.name for zone in result.path] == ["start", "detour", "end"]
    assert result.total_cost == 2


def test_path_result_repr_contains_zone_names_and_cost() -> None:
    """PathResult's repr must be usable for quick debugging output."""
    graph, start, end = _linear_graph()
    result = Pathfinder().find_shortest_path(graph, start, end)
    assert result is not None

    text = repr(result)
    assert "start" in text
    assert "end" in text
    assert "total_cost=3" in text
