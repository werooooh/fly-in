"""Tests for the turn-by-turn simulation engine."""

import pytest

from flyin.models.connection import Connection
from flyin.models.graph import Graph
from flyin.models.zone import Zone, ZoneType
from flyin.simulation.engine import SimulationEngine
from flyin.simulation.output import OutputFormatter


def _simple_linear_graph() -> Graph:
    """Build a start-a-end linear graph with default (1) capacities.

    Returns:
        A ready-to-simulate Graph.
    """
    graph = Graph()
    start = Zone("start", 0, 0, is_start=True)
    a = Zone("a", 1, 0)
    end = Zone("end", 2, 0, is_end=True)
    for zone in (start, a, end):
        graph.add_zone(zone)
    graph.add_connection(Connection(start, a))
    graph.add_connection(Connection(a, end))
    return graph


def _restricted_bottleneck_graph() -> Graph:
    """Build a start-danger-end graph where danger is a restricted zone.

    Both the connection and the restricted zone default to a
    capacity of 1, forcing drones to queue.

    Returns:
        A ready-to-simulate Graph.
    """
    graph = Graph()
    start = Zone("start", 0, 0, is_start=True)
    danger = Zone("danger", 1, 0, zone_type=ZoneType.RESTRICTED)
    end = Zone("end", 2, 0, is_end=True)
    for zone in (start, danger, end):
        graph.add_zone(zone)
    graph.add_connection(Connection(start, danger))
    graph.add_connection(Connection(danger, end))
    return graph


def test_single_drone_reaches_end_on_linear_graph() -> None:
    """A single drone on a simple graph must arrive in exactly 2 turns."""
    engine = SimulationEngine(_simple_linear_graph(), nb_drones=1)
    turn_log = engine.run()

    assert len(turn_log) == 2
    assert turn_log[0] == ["D1-a"]
    assert turn_log[1] == ["D1-end"]
    assert engine.drones[0].has_arrived


def test_all_drones_eventually_arrive() -> None:
    """Every drone must reach ARRIVED status by the end of the run."""
    engine = SimulationEngine(_simple_linear_graph(), nb_drones=3)
    engine.run()

    assert all(drone.has_arrived for drone in engine.drones)


def test_default_zone_capacity_serializes_drones() -> None:
    """Two drones sharing a default-capacity (1) zone must not overlap.

    On this map, "a" has max_drones=1, so the second drone must wait
    a turn before entering it.
    """
    engine = SimulationEngine(_simple_linear_graph(), nb_drones=2)
    turn_log = engine.run()

    # D1 must clear zone "a" before D2 can enter it.
    turn_with_d2_entering_a = next(
        i for i, turn in enumerate(turn_log) if "D2-a" in turn
    )
    turn_with_d1_leaving_a = next(
        i for i, turn in enumerate(turn_log) if "D1-end" in turn
    )
    assert turn_with_d1_leaving_a <= turn_with_d2_entering_a


def test_no_drone_acts_twice_in_the_same_turn() -> None:
    """A drone that lands from transit must not also move that turn.

    Regression test: landing and taking a fresh move in the same
    turn would let a drone perform two actions in one turn.
    """
    engine = SimulationEngine(_restricted_bottleneck_graph(), nb_drones=1)
    turn_log = engine.run()

    for turn_movements in turn_log:
        labels = [movement.split("-", 1)[0] for movement in turn_movements]
        assert len(labels) == len(set(labels))


def test_restricted_zone_transit_takes_two_turns() -> None:
    """A drone entering a restricted zone must land on the very next turn.

    The subject states the drone "MUST reach its destination during
    the next turn" -- the commit turn itself is the first of the
    zone's 2-turn cost, so landing happens on the turn right after
    committing, with no idle turn in between.

    Turn 1: enters the connection. Turn 2: lands in the restricted
    zone.
    """
    engine = SimulationEngine(_restricted_bottleneck_graph(), nb_drones=1)
    turn_log = engine.run()

    assert turn_log[0] == ["D1-start-danger"]
    assert turn_log[1] == ["D1-danger"]


def test_connection_capacity_blocks_second_drone_until_first_clears() -> None:
    """A second drone must not enter a full-capacity connection early."""
    engine = SimulationEngine(_restricted_bottleneck_graph(), nb_drones=2)
    turn_log = engine.run()

    turn_d1_enters = next(
        i for i, turn in enumerate(turn_log) if "D1-start-danger" in turn
    )
    turn_d2_enters = next(
        i for i, turn in enumerate(turn_log) if "D2-start-danger" in turn
    )
    turn_d1_lands = next(
        i for i, turn in enumerate(turn_log) if "D1-danger" in turn
    )
    assert turn_d2_enters > turn_d1_enters
    assert turn_d2_enters >= turn_d1_lands


def test_raises_when_no_path_exists() -> None:
    """SimulationEngine must fail loudly if start and end are severed."""
    graph = Graph()
    start = Zone("start", 0, 0, is_start=True)
    wall = Zone("wall", 1, 0, zone_type=ZoneType.BLOCKED)
    end = Zone("end", 2, 0, is_end=True)
    for zone in (start, wall, end):
        graph.add_zone(zone)
    graph.add_connection(Connection(start, wall))
    graph.add_connection(Connection(wall, end))

    engine = SimulationEngine(graph, nb_drones=1)
    with pytest.raises(RuntimeError):
        engine.run()


def test_format_output_joins_turns_with_newlines() -> None:
    """format_output must produce one space-separated line per turn."""
    turn_log = [["D1-a", "D2-b"], ["D1-end"]]
    assert OutputFormatter().format(turn_log) == "D1-a D2-b\nD1-end"
