"""Zone model representing a single node in the drone routing graph."""

from __future__ import annotations

from enum import Enum


class ZoneType(Enum):
    """Type of a zone, determining its movement cost and accessibility.

    Attributes:
        NORMAL: Standard zone, costs 1 turn to enter.
        BLOCKED: Inaccessible zone, cannot be entered or passed through.
        RESTRICTED: Sensitive zone, costs 2 turns to enter.
        PRIORITY: Preferred zone, costs 1 turn but should be favored
            by pathfinding algorithms.
    """

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    def movement_cost(self) -> int:
        """Return the number of turns required to enter this zone type.

        Returns:
            The movement cost in turns. Blocked zones return -1 since
            they can never actually be entered; callers must check
            `is_accessible` before relying on this value.
        """
        costs: dict[ZoneType, int] = {
            ZoneType.NORMAL: 1,
            ZoneType.RESTRICTED: 2,
            ZoneType.PRIORITY: 1,
            ZoneType.BLOCKED: -1,
        }
        return costs[self]

    def is_accessible(self) -> bool:
        """Return whether drones are allowed to enter this zone type.

        Returns:
            True if the zone type can be entered, False otherwise.
        """
        return self is not ZoneType.BLOCKED


class Zone:
    """A single zone (node) in the drone routing network.

    Attributes:
        name: Unique identifier of the zone.
        x: X coordinate of the zone.
        y: Y coordinate of the zone.
        zone_type: The type of the zone, determining cost and access.
        color: Optional color tag used for visual representation.
        max_drones: Maximum number of drones allowed simultaneously
            in this zone. Ignored (treated as unlimited) for the
            start and end zones.
        is_start: Whether this zone is the unique start hub.
        is_end: Whether this zone is the unique end hub.
        current_occupants: Labels of drones physically present here
            right now.
        incoming_reservations: Labels of drones committed to land
            here after a multi-turn restricted-zone transit, reserved
            ahead of arrival to prevent overbooking a low-capacity
            zone.
    """

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        zone_type: ZoneType = ZoneType.NORMAL,
        color: str | None = None,
        max_drones: int = 1,
        is_start: bool = False,
        is_end: bool = False,
    ) -> None:
        """Initialize a Zone.

        Args:
            name: Unique identifier of the zone.
            x: X coordinate of the zone.
            y: Y coordinate of the zone.
            zone_type: The type of the zone. Defaults to NORMAL.
            color: Optional color tag for visual representation.
            max_drones: Maximum simultaneous occupancy. Defaults to 1.
            is_start: Whether this zone is the start hub.
            is_end: Whether this zone is the end hub.
        """
        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.color = color
        self.max_drones = max_drones
        self.is_start = is_start
        self.is_end = is_end
        self.current_occupants: set[str] = set()
        self.incoming_reservations: set[str] = set()

    def has_unlimited_capacity(self) -> bool:
        """Return whether this zone ignores max_drones (start/end zones).

        Returns:
            True if the zone is the start or end hub.
        """
        return self.is_start or self.is_end

    def has_capacity_for(self, incoming_count: int = 1) -> bool:
        """Check whether the zone can accept additional drones.

        Args:
            incoming_count: Number of drones attempting to enter.

        Returns:
            True if the zone can accommodate the incoming drones given
            its current occupancy and max_drones limit.
        """
        if self.has_unlimited_capacity():
            return True
        committed = len(self.current_occupants) + len(
            self.incoming_reservations
        )
        return committed + incoming_count <= self.max_drones

    def __repr__(self) -> str:
        """Return a debug-friendly representation of the zone."""
        return (
            f"Zone(name={self.name!r}, type={self.zone_type.value}, "
            f"pos=({self.x}, {self.y}))"
        )

    def __eq__(self, other: object) -> bool:
        """Compare zones by name, which is expected to be unique."""
        if not isinstance(other, Zone):
            return NotImplemented
        return self.name == other.name

    def __hash__(self) -> int:
        """Hash a zone by its unique name."""
        return hash(self.name)
