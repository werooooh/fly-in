from flyin.models.connection import Connection
from flyin.models.zone import Zone


class Graph:
    """The full drone routing network.

    Attributes:
        zones: Mapping of zone name to Zone instance.
        connections: List of all connections in the network.
        start_zone: The unique start hub, once set.
        end_zone: The unique end hub, once set.
    """

    def __init__(self) -> None:
        """Initialize an empty Graph."""
        self.zones: dict[str, Zone] = {}
        self.connections: list[Connection] = []
        self.start_zone: Zone | None = None
        self.end_zone: Zone | None = None
        self._adjacency: dict[str, list[Connection]] = {}

    def add_zone(self, zone: Zone) -> None:
        """Add a zone to the graph.

        Args:
            zone: The zone to add.

        Raises:
            ValueError: If a zone with the same name already exists,
                or if this is a second start/end zone.
        """
        if zone.name in self.zones:
            raise ValueError(f"Duplicate zone name: {zone.name!r}")

        if zone.is_start:
            if self.start_zone is not None:
                raise ValueError("A start zone is already defined.")
            self.start_zone = zone

        if zone.is_end:
            if self.end_zone is not None:
                raise ValueError("An end zone is already defined.")
            self.end_zone = zone

        self.zones[zone.name] = zone
        self._adjacency[zone.name] = []

    def add_connection(self, connection: Connection) -> None:
        """Add a connection to the graph.

        Args:
            connection: The connection to add.

        Raises:
            ValueError: If either endpoint is not already part of the
                graph, or if this connection duplicates an existing one.
        """
        name_a = connection.zone_a.name
        name_b = connection.zone_b.name

        if name_a not in self.zones or name_b not in self.zones:
            raise ValueError(
                f"Connection {name_a!r}-{name_b!r} references an "
                "undefined zone."
            )

        if self.get_connection(name_a, name_b) is not None:
            raise ValueError(
                f"Duplicate connection between {name_a!r} and {name_b!r}."
            )

        self.connections.append(connection)
        self._adjacency[name_a].append(connection)
        self._adjacency[name_b].append(connection)

    def get_zone(self, name: str) -> Zone:
        """Retrieve a zone by name.

        Args:
            name: The name of the zone.

        Returns:
            The matching Zone instance.

        Raises:
            KeyError: If no zone with that name exists.
        """
        if name not in self.zones:
            raise KeyError(f"No such zone: {name!r}")
        return self.zones[name]

    def get_connection(self, name_a: str, name_b: str) -> Connection | None:
        """Retrieve the connection between two zone names, if any.

        Args:
            name_a: Name of the first zone.
            name_b: Name of the second zone.

        Returns:
            The matching Connection, or None if no such connection
            exists.
        """
        for connection in self.connections:
            if connection.connects(name_a, name_b):
                return connection
        return None

    def neighbors(self, zone: Zone) -> list[tuple[Zone, Connection]]:
        """List the zones directly reachable from the given zone.

        Args:
            zone: The zone to inspect.

        Returns:
            A list of (neighbor_zone, connection) pairs.
        """
        result: list[tuple[Zone, Connection]] = []
        for connection in self._adjacency.get(zone.name, []):
            result.append((connection.other_end(zone), connection))
        return result

    def is_ready(self) -> bool:
        """Check whether the graph has both a start and an end zone.

        Returns:
            True if both start_zone and end_zone are set.
        """
        return self.start_zone is not None and self.end_zone is not None
