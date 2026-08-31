from flyin.models.connection import Connection
from flyin.models.graph import Graph
from flyin.models.zone import Zone, ZoneType
from flyin.pathfinding.dijkstra import Pathfinder
from flyin.pathfinding.distribution import PathDistributor


def test_distribute_spreads_drones_across_equal_cost_paths() -> None:
    """Drones must round-robin across paths that cost exactly the same."""
    graph = Graph()
    start = Zone("start", 0, 0, is_start=True)
    branch_a = Zone("branch_a", 1, -1)
    branch_b = Zone("branch_b", 1, 1)
    end = Zone("end", 2, 0, is_end=True)
    for zone in (start, branch_a, branch_b, end):
        graph.add_zone(zone)
    graph.add_connection(Connection(start, branch_a))
    graph.add_connection(Connection(branch_a, end))
    graph.add_connection(Connection(start, branch_b))
    graph.add_connection(Connection(branch_b, end))

    distributor = PathDistributor(Pathfinder())
    assignments = distributor.distribute(graph, start, end, nb_drones=4)

    used_branches = {path[1].name for path in assignments}
    assert used_branches == {"branch_a", "branch_b"}
    assert len(assignments) == 4


def test_distribute_never_uses_a_costlier_detour() -> None:
    """A pricier alternative route must never be assigned to any drone.

    Mirrors the subject's example map: a restricted-zone detour costs
    more than the direct route, so every drone should stay on the
    cheapest path even though an alternative technically exists.
    """
    graph = Graph()
    start = Zone("hub", 0, 0, is_start=True)
    cheap_mid = Zone("cheap_mid", 1, 0, zone_type=ZoneType.PRIORITY)
    costly_mid = Zone("costly_mid", 1, 1, zone_type=ZoneType.RESTRICTED)
    end = Zone("goal", 2, 0, is_end=True)
    for zone in (start, cheap_mid, costly_mid, end):
        graph.add_zone(zone)
    graph.add_connection(Connection(start, cheap_mid))
    graph.add_connection(Connection(cheap_mid, end))
    graph.add_connection(Connection(start, costly_mid))
    graph.add_connection(Connection(costly_mid, end))

    distributor = PathDistributor(Pathfinder())
    assignments = distributor.distribute(graph, start, end, nb_drones=5)

    used_zones = {path[1].name for path in assignments}
    assert used_zones == {"cheap_mid"}


def test_distribute_returns_empty_when_no_path_exists() -> None:
    """An unreachable end zone must yield no assignments at all."""
    graph = Graph()
    start = Zone("start", 0, 0, is_start=True)
    wall = Zone("wall", 1, 0, zone_type=ZoneType.BLOCKED)
    end = Zone("end", 2, 0, is_end=True)
    for zone in (start, wall, end):
        graph.add_zone(zone)
    graph.add_connection(Connection(start, wall))
    graph.add_connection(Connection(wall, end))

    distributor = PathDistributor(Pathfinder())
    assignments = distributor.distribute(graph, start, end, nb_drones=3)

    assert assignments == []


def test_distribute_caps_distinct_paths_at_five() -> None:
    """Even with many equal-cost branches, at most 5 are searched for."""
    graph = Graph()
    start = Zone("start", 0, 0, is_start=True)
    end = Zone("end", 2, 0, is_end=True)
    graph.add_zone(start)
    graph.add_zone(end)
    for i in range(8):
        branch = Zone(f"branch_{i}", 1, i)
        graph.add_zone(branch)
        graph.add_connection(Connection(start, branch))
        graph.add_connection(Connection(branch, end))

    distributor = PathDistributor(Pathfinder())
    assignments = distributor.distribute(graph, start, end, nb_drones=8)

    used_branches = {path[1].name for path in assignments}
    assert len(used_branches) <= 5
