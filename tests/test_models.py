import pytest

from flyin.models.connection import Connection
from flyin.models.drone import Drone, DroneStatus
from flyin.models.graph import Graph
from flyin.models.zone import Zone, ZoneType

# --- Zone ---------------------------------------------------------------


def test_zone_default_values() -> None:
    """A zone with no explicit metadata should use documented defaults."""
    zone = Zone(name="hub", x=0, y=0)
    assert zone.zone_type is ZoneType.NORMAL
    assert zone.max_drones == 1
    assert zone.color is None
    assert zone.is_start is False
    assert zone.is_end is False


def test_zone_type_movement_cost() -> None:
    """Movement cost must match the values defined in the subject."""
    assert ZoneType.NORMAL.movement_cost() == 1
    assert ZoneType.PRIORITY.movement_cost() == 1
    assert ZoneType.RESTRICTED.movement_cost() == 2


def test_zone_type_blocked_is_not_accessible() -> None:
    """Blocked zones must never be reported as accessible."""
    assert ZoneType.BLOCKED.is_accessible() is False
    assert ZoneType.NORMAL.is_accessible() is True


def test_zone_capacity_respects_max_drones() -> None:
    """A normal zone should refuse entry beyond its max_drones limit."""
    zone = Zone(name="hub", x=0, y=0, max_drones=1)
    assert zone.has_capacity_for(1) is True
    zone.current_occupants.add("D1")
    assert zone.has_capacity_for(1) is False


def test_zone_start_has_unlimited_capacity() -> None:
    """Start/end zones must ignore max_drones entirely."""
    zone = Zone(name="start", x=0, y=0, max_drones=1, is_start=True)
    for i in range(10):
        zone.current_occupants.add(f"D{i}")
    assert zone.has_capacity_for(5) is True


def test_zone_equality_and_hash_based_on_name() -> None:
    """Two zones sharing a name are equal and hash identically."""
    zone_a = Zone(name="hub", x=0, y=0)
    zone_b = Zone(name="hub", x=99, y=99)
    assert zone_a == zone_b
    assert hash(zone_a) == hash(zone_b)
    assert zone_a != Zone(name="other", x=0, y=0)


# --- Connection -----------------------------------------------------------


def test_connection_other_end() -> None:
    """other_end must return the opposite zone of the connection."""
    a = Zone(name="a", x=0, y=0)
    b = Zone(name="b", x=1, y=0)
    conn = Connection(a, b)
    assert conn.other_end(a) == b
    assert conn.other_end(b) == a


def test_connection_other_end_raises_for_foreign_zone() -> None:
    """other_end must reject a zone that isn't part of the connection."""
    a = Zone(name="a", x=0, y=0)
    b = Zone(name="b", x=1, y=0)
    foreign = Zone(name="foreign", x=2, y=0)
    conn = Connection(a, b)
    with pytest.raises(ValueError):
        conn.other_end(foreign)


def test_connection_connects_is_order_independent() -> None:
    """a-b and b-a must be recognized as the same connection."""
    a = Zone(name="a", x=0, y=0)
    b = Zone(name="b", x=1, y=0)
    conn = Connection(a, b)
    assert conn.connects("a", "b") is True
    assert conn.connects("b", "a") is True
    assert conn.connects("a", "c") is False


def test_connection_capacity_limit() -> None:
    """A connection must refuse traversal beyond max_link_capacity."""
    a = Zone(name="a", x=0, y=0)
    b = Zone(name="b", x=1, y=0)
    conn = Connection(a, b, max_link_capacity=1)
    assert conn.has_capacity_for(1) is True
    conn.drones_in_transit.add("D1")
    assert conn.has_capacity_for(1) is False


# --- Graph ------------------------------------------------------------


def test_graph_add_zone_and_get_zone() -> None:
    """A zone added to the graph must be retrievable by name."""
    graph = Graph()
    zone = Zone(name="hub", x=0, y=0)
    graph.add_zone(zone)
    assert graph.get_zone("hub") == zone


def test_graph_rejects_duplicate_zone_name() -> None:
    """Adding two zones with the same name must raise ValueError."""
    graph = Graph()
    graph.add_zone(Zone(name="hub", x=0, y=0))
    with pytest.raises(ValueError):
        graph.add_zone(Zone(name="hub", x=1, y=1))


def test_graph_rejects_second_start_zone() -> None:
    """Only one start zone is allowed per graph."""
    graph = Graph()
    graph.add_zone(Zone(name="s1", x=0, y=0, is_start=True))
    with pytest.raises(ValueError):
        graph.add_zone(Zone(name="s2", x=1, y=1, is_start=True))


def test_graph_rejects_second_end_zone() -> None:
    """Only one end zone is allowed per graph."""
    graph = Graph()
    graph.add_zone(Zone(name="e1", x=0, y=0, is_end=True))
    with pytest.raises(ValueError):
        graph.add_zone(Zone(name="e2", x=1, y=1, is_end=True))


def test_graph_add_connection_requires_existing_zones() -> None:
    """A connection referencing an unknown zone must be rejected."""
    graph = Graph()
    a = Zone(name="a", x=0, y=0)
    b = Zone(name="b", x=1, y=0)
    graph.add_zone(a)
    with pytest.raises(ValueError):
        graph.add_connection(Connection(a, b))


def test_graph_rejects_duplicate_connection() -> None:
    """a-b and b-a must both be rejected as duplicates of one another."""
    graph = Graph()
    a = Zone(name="a", x=0, y=0)
    b = Zone(name="b", x=1, y=0)
    graph.add_zone(a)
    graph.add_zone(b)
    graph.add_connection(Connection(a, b))
    with pytest.raises(ValueError):
        graph.add_connection(Connection(b, a))


def test_graph_neighbors_returns_connected_zones() -> None:
    """neighbors() must list every zone directly reachable from a zone."""
    graph = Graph()
    a = Zone(name="a", x=0, y=0)
    b = Zone(name="b", x=1, y=0)
    c = Zone(name="c", x=2, y=0)
    for zone in (a, b, c):
        graph.add_zone(zone)
    graph.add_connection(Connection(a, b))
    graph.add_connection(Connection(a, c))

    neighbor_names = {zone.name for zone, _ in graph.neighbors(a)}
    assert neighbor_names == {"b", "c"}
    assert graph.neighbors(b)[0][0] == a


def test_graph_is_ready_requires_start_and_end() -> None:
    """is_ready() must be False until both start and end are defined."""
    graph = Graph()
    assert graph.is_ready() is False
    graph.add_zone(Zone(name="s", x=0, y=0, is_start=True))
    assert graph.is_ready() is False
    graph.add_zone(Zone(name="e", x=1, y=1, is_end=True))
    assert graph.is_ready() is True


# --- Drone ------------------------------------------------------------


def test_drone_starts_at_start_zone_waiting() -> None:
    """A freshly created drone must sit at its start zone, waiting."""
    start = Zone(name="start", x=0, y=0, is_start=True)
    drone = Drone(drone_id=1, start_zone=start)
    assert drone.current_zone == start
    assert drone.status is DroneStatus.WAITING
    assert drone.label() == "D1"
    assert drone.has_arrived() is False


def test_drone_assign_and_advance_path() -> None:
    """assign_path/next_zone/advance_path must move through the path."""
    start = Zone(name="start", x=0, y=0, is_start=True)
    a = Zone(name="a", x=1, y=0)
    b = Zone(name="b", x=2, y=0)
    drone = Drone(drone_id=1, start_zone=start)

    drone.assign_path([a, b])
    assert drone.next_zone() == a

    drone.advance_path()
    assert drone.next_zone() == b

    drone.advance_path()
    assert drone.next_zone() is None


def test_drone_advance_path_raises_when_empty() -> None:
    """Advancing an empty path must raise IndexError, not fail silently."""
    start = Zone(name="start", x=0, y=0, is_start=True)
    drone = Drone(drone_id=1, start_zone=start)
    with pytest.raises(IndexError):
        drone.advance_path()


def test_drone_has_arrived_reflects_status() -> None:
    """has_arrived must be True only once status is set to ARRIVED."""
    start = Zone(name="start", x=0, y=0, is_start=True)
    drone = Drone(drone_id=1, start_zone=start)
    assert drone.has_arrived() is False
    drone.status = DroneStatus.ARRIVED
    assert drone.has_arrived() is True
