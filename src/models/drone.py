from enum import Enum

from models.connection import Connection
from models.zone import Zone


class DroneStatus(Enum):
    """Current status of a drone within the simulation.

    Attributes:
        WAITING: The drone is stationed at a zone and not moving
            this turn.
        MOVING: The drone is moving into a normal or priority zone
            this turn (single-turn movement).
        IN_TRANSIT: The drone is traversing a connection toward a
            restricted zone and is committed to arriving after the
            required number of turns.
        ARRIVED: The drone has reached the end zone and is delivered.
    """

    WAITING = "waiting"
    MOVING = "moving"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"


class Drone:
    """A single drone navigating from the start zone to the end zone.

    Attributes:
        drone_id: Unique identifier of the drone (e.g. 1 for "D1").
        current_zone: The zone the drone currently occupies. None
            while the drone is in transit on a connection.
        status: The current status of the drone.
        path: The full sequence of zones the drone intends to follow,
            from its current position to the end zone.
        turns_remaining: Number of turns left before the drone lands,
            when status is IN_TRANSIT. Unused otherwise.
        transit_connection: The connection currently being traversed,
            when status is IN_TRANSIT. None otherwise.
    """

    def __init__(self, drone_id: int, start_zone: Zone) -> None:
        """Initialize a Drone at the start zone.

        Args:
            drone_id: Unique identifier of the drone.
            start_zone: The zone where the drone begins the simulation.
        """
        self.drone_id = drone_id
        self.current_zone: Zone | None = start_zone
        self.status = DroneStatus.WAITING
        self.path: list[Zone] = []
        self.turns_remaining: int = 0
        self.transit_connection: Connection | None = None

    def label(self) -> str:
        """Return the display label used in simulation output.

        Returns:
            The drone identifier formatted as "D<id>" (e.g. "D1").
        """
        return f"D{self.drone_id}"

    def has_arrived(self) -> bool:
        """Return whether the drone has reached the end zone.

        Returns:
            True if the drone's status is ARRIVED.
        """
        return self.status is DroneStatus.ARRIVED

    def assign_path(self, path: list[Zone]) -> None:
        """Assign a new path for the drone to follow.

        Args:
            path: The sequence of zones from the drone's current
                position to the end zone, current zone excluded.
        """
        self.path = list(path)

    def next_zone(self) -> Zone | None:
        """Return the next zone the drone should move toward.

        Returns:
            The next Zone in the assigned path, or None if the path
            is empty (drone has no further move planned).
        """
        if not self.path:
            return None
        return self.path[0]

    def advance_path(self) -> None:
        """Pop the next zone off the path after successfully moving.

        Raises:
            IndexError: If called while the path is already empty.
        """
        if not self.path:
            raise IndexError("Cannot advance an empty path.")
        self.path.pop(0)
