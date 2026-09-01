from models.zone import Zone


class Connection:
    """A bidirectional connection (edge) between two zones.

    Attributes:
        zone_a: One endpoint of the connection.
        zone_b: The other endpoint of the connection.
        max_link_capacity: Maximum number of drones that may traverse
            this connection simultaneously.
        drones_in_transit: Identifiers of drones currently traversing
            this connection (used for multi-turn restricted-zone
            movement tracking).
    """

    def __init__(
        self,
        zone_a: Zone,
        zone_b: Zone,
        max_link_capacity: int = 1,
    ) -> None:
        """Initialize a Connection.

        Args:
            zone_a: One endpoint of the connection.
            zone_b: The other endpoint of the connection.
            max_link_capacity: Maximum simultaneous traversals.
                Defaults to 1.
        """
        self.zone_a = zone_a
        self.zone_b = zone_b
        self.max_link_capacity = max_link_capacity
        self.drones_in_transit: set[str] = set()

    def name(self) -> str:
        """Return a display name for this connection.

        Returns:
            The two endpoint names joined by a dash, in the order the
            connection was originally defined (e.g. "hub-roof1").
            Used in simulation output when a drone is in flight.
        """
        return f"{self.zone_a.name}-{self.zone_b.name}"

    def other_end(self, zone: Zone) -> Zone:
        """Return the zone on the opposite end of the connection.

        Args:
            zone: One of the two zones of this connection.

        Returns:
            The other zone of the connection.

        Raises:
            ValueError: If the given zone is not part of this connection.
        """
        if zone == self.zone_a:
            return self.zone_b
        if zone == self.zone_b:
            return self.zone_a
        raise ValueError(f"Zone {zone.name!r} is not part of this connection.")

    def connects(self, name_a: str, name_b: str) -> bool:
        """Check whether this connection links the two given zone names.

        Args:
            name_a: Name of the first zone.
            name_b: Name of the second zone.

        Returns:
            True if this connection links the two zones, in either
            direction.
        """
        pair = {self.zone_a.name, self.zone_b.name}
        return pair == {name_a, name_b}

    def has_capacity_for(self, incoming_count: int = 1) -> bool:
        """Check whether the connection can accept additional drones.

        Args:
            incoming_count: Number of drones attempting to traverse.

        Returns:
            True if the connection can accommodate the incoming drones
            given its current transit load and max_link_capacity.
        """
        return (
            len(self.drones_in_transit) + incoming_count
            <= self.max_link_capacity
        )
