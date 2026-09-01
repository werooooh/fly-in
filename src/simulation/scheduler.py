from models.connection import Connection
from models.drone import Drone, DroneStatus
from models.graph import Graph
from models.zone import Zone, ZoneType


class TurnScheduler:
    """Resolves one turn's worth of drone movement intents."""

    def resolve_turn(self, drones: list[Drone], graph: Graph) -> list[str]:
        """Attempt to move every eligible drone once, in priority order.

        Args:
            drones: All drones in the simulation.
            graph: The network the drones are moving through.

        Returns:
            The list of movement strings for this turn (subject
            output format), one per drone that successfully moved.
            Drones that could not move are simply omitted.
        """
        movements: list[str] = []
        connection_usage: dict[int, int] = {}

        eligible = sorted(
            (
                drone
                for drone in drones
                if not drone.has_arrived()
                and drone.status is not DroneStatus.IN_TRANSIT
            ),
            key=lambda drone: drone.drone_id,
        )

        for drone in eligible:
            movement = self._try_move(drone, graph, connection_usage)
            if movement is not None:
                movements.append(movement)

        return movements

    def _try_move(
        self,
        drone: Drone,
        graph: Graph,
        connection_usage: dict[int, int],
    ) -> str | None:
        """Attempt to move a single drone toward the next zone in its path.

        Args:
            drone: The drone to move. Must not be arrived or in transit.
            graph: The network the drone is moving through.
            connection_usage: Per-connection count of single-turn
                crossings already committed this turn. Mutated in
                place.

        Returns:
            The movement string if the move succeeded, or None if the
            drone had to wait (no path left, or capacity unavailable).
        """
        next_zone = drone.next_zone()
        current_zone = drone.current_zone
        if next_zone is None or current_zone is None:
            return None

        connection = graph.get_connection(current_zone.name, next_zone.name)
        if connection is None:
            raise RuntimeError(
                f"No connection between {current_zone.name!r} and "
                f"{next_zone.name!r}, but the assigned path uses one."
            )

        used_this_turn = connection_usage.get(id(connection), 0)
        connection_available = (
            len(connection.drones_in_transit) + used_this_turn
            < connection.max_link_capacity
        )
        if not connection_available:
            return None

        if not next_zone.has_capacity_for(1):
            return None

        connection_usage[id(connection)] = used_this_turn + 1

        if next_zone.zone_type is ZoneType.RESTRICTED:
            return self._start_transit(
                drone, current_zone, next_zone, connection
            )
        return self._single_turn_move(drone, current_zone, next_zone)

    def _single_turn_move(
        self, drone: Drone, current_zone: Zone, next_zone: Zone
    ) -> str:
        """Move a drone into a normal/priority zone within one turn.

        Args:
            drone: The drone being moved.
            current_zone: The zone the drone is leaving.
            next_zone: The zone the drone is entering.

        Returns:
            The movement string "D<id>-<zone_name>".
        """
        current_zone.current_occupants.discard(drone.label())
        next_zone.current_occupants.add(drone.label())
        drone.current_zone = next_zone
        drone.advance_path()
        drone.status = (
            DroneStatus.ARRIVED if next_zone.is_end else DroneStatus.WAITING
        )
        return f"{drone.label()}-{next_zone.name}"

    def _start_transit(
        self,
        drone: Drone,
        current_zone: Zone,
        next_zone: Zone,
        connection: Connection,
    ) -> str:
        """Commit a drone to a multi-turn transit toward a restricted zone.

        The drone leaves its current zone immediately, occupies the
        connection for the duration of the transit, and reserves a
        landing slot at the destination so a second drone cannot
        overbook it while this one is still in flight.

        Args:
            drone: The drone being moved.
            current_zone: The zone the drone is leaving.
            next_zone: The restricted zone the drone is heading to.
            connection: The connection being traversed.

        Returns:
            The movement string "D<id>-<connection_name>".
        """
        current_zone.current_occupants.discard(drone.label())
        connection.drones_in_transit.add(drone.label())
        next_zone.incoming_reservations.add(drone.label())
        drone.current_zone = None
        drone.status = DroneStatus.IN_TRANSIT
        # The commit turn itself counts as the first of the zone's
        # movement_cost turns (subject: drone "MUST reach its
        # destination during the next turn"), so only cost - 1 more
        # turns remain before landing.
        drone.turns_remaining = next_zone.zone_type.movement_cost() - 1
        drone.transit_connection = connection
        return f"{drone.label()}-{connection.name()}"
