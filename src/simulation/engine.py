from models.drone import Drone, DroneStatus
from models.graph import Graph
from pathfinding.dijkstra import Pathfinder
from pathfinding.distribution import PathDistributor
from simulation.scheduler import TurnScheduler


class SimulationEngine:
    """Runs the full drone routing simulation for a parsed map.

    Attributes:
        graph: The network the drones move through.
        drones: All drones participating in the simulation.
        turn_log: Movement strings recorded per turn, filled in by run().
        current_turn: The number of turns simulated so far.
    """

    def __init__(
        self,
        graph: Graph,
        nb_drones: int,
        max_turns: int = 1000,
    ) -> None:
        """Initialize the simulation engine.

        Args:
            graph: The parsed and validated network to simulate on.
            nb_drones: Number of drones to spawn at the start zone.
            max_turns: Safety cap on the number of turns to simulate,
                guarding against an unresolved deadlock looping
                forever. Defaults to 1000.

        Raises:
            RuntimeError: If the graph has no start or end zone set.
        """
        if graph.start_zone is None or graph.end_zone is None:
            raise RuntimeError(
                "Graph must have both a start and an end zone."
            )

        self.graph = graph
        self.drones: list[Drone] = [
            Drone(drone_id=i, start_zone=graph.start_zone)
            for i in range(1, nb_drones + 1)
        ]
        for drone in self.drones:
            graph.start_zone.current_occupants.add(drone.label())

        self._scheduler = TurnScheduler()
        self._path_distributor = PathDistributor(Pathfinder())
        self.turn_log: list[list[str]] = []
        self.current_turn = 0
        self._max_turns = max_turns

    def run(self) -> list[list[str]]:
        """Run the simulation until every drone arrives.

        Returns:
            The full turn log: one list of movement strings per turn.

        Raises:
            RuntimeError: If no path exists between start and end, or
                if the simulation does not converge within max_turns
                (indicating an unresolved deadlock).
        """
        self._assign_initial_paths()
        self._print_occupancy()

        while not self._all_arrived():
            if self.current_turn >= self._max_turns:
                raise RuntimeError(
                    f"Simulation did not converge within "
                    f"{self._max_turns} turns (possible deadlock)."
                )
            self.current_turn += 1
            self.turn_log.append(self._step())
            self._print_occupancy()

        return self.turn_log

    def _step(self) -> list[str]:
        """Simulate a single turn: process landings, then new moves.

        A drone that lands this turn has already used its action for
        the turn (completing the multi-turn transit it started
        earlier) and must not also move again in the same turn.

        Returns:
            The movement strings produced during this turn.
        """
        landing_movements, landed_labels = self._process_landings()
        movable_drones = [
            drone
            for drone in self.drones
            if drone.label() not in landed_labels
        ]
        movement_movements = self._scheduler.resolve_turn(
            movable_drones, self.graph
        )
        return landing_movements + movement_movements

    def _process_landings(self) -> tuple[list[str], set[str]]:
        """Advance every in-transit drone and land those whose time is up.

        Returns:
            A tuple of (movement strings for this turn's landings,
            labels of the drones that landed this turn).
        """
        movements: list[str] = []
        landed_labels: set[str] = set()
        for drone in self.drones:
            if drone.status is not DroneStatus.IN_TRANSIT:
                continue
            drone.turns_remaining -= 1
            if drone.turns_remaining <= 0:
                movements.append(self._land(drone))
                landed_labels.add(drone.label())
        return movements, landed_labels

    def _land(self, drone: Drone) -> str:
        """Land a drone that has completed its restricted-zone transit.

        Args:
            drone: The drone landing this turn. Must be IN_TRANSIT
                with a valid transit_connection and a non-empty path.

        Returns:
            The movement string "D<id>-<zone_name>" for this landing.
        """
        next_zone = drone.next_zone()
        connection = drone.transit_connection
        if next_zone is None or connection is None:
            raise RuntimeError(
                f"{drone.label()} cannot land: missing target zone or "
                "transit connection."
            )

        connection.drones_in_transit.discard(drone.label())
        next_zone.incoming_reservations.discard(drone.label())
        next_zone.current_occupants.add(drone.label())

        drone.current_zone = next_zone
        drone.transit_connection = None
        drone.advance_path()
        drone.status = (
            DroneStatus.ARRIVED if next_zone.is_end else DroneStatus.WAITING
        )
        return f"{drone.label()}-{next_zone.name}"

    def _print_occupancy(self) -> None:
        """Print zone and connection occupancy for the current turn.

        Start and end zones are shown without a capacity ratio since
        they are always unlimited.
        """
        zone_parts = []
        for zone in self.graph.zones.values():
            occupants = sorted(zone.current_occupants)
            if zone.has_unlimited_capacity():
                zone_parts.append(f"{zone.name}={occupants}")
            else:
                zone_parts.append(
                    f"{zone.name}={occupants}"
                    f"({len(zone.current_occupants)}/{zone.max_drones})"
                )

        connection_parts = [
            f"{connection.name()}="
            f"{len(connection.drones_in_transit)}/"
            f"{connection.max_link_capacity}"
            for connection in self.graph.connections
        ]

        print(f"Turn {self.current_turn} occupancy:")
        print("  zones: " + " ".join(zone_parts))
        print("  connections: " + " ".join(connection_parts))

    def _assign_initial_paths(self) -> None:
        """Compute and assign a path to every drone, spread across routes.

        Drones are distributed round-robin across several distinct
        paths (when the graph offers real alternatives) instead of
        all following the single globally shortest route, reducing
        avoidable congestion on zones and connections with limited
        capacity.

        Raises:
            RuntimeError: If no accessible path exists between the
                start and end zones.
        """
        start, end = self.graph.start_zone, self.graph.end_zone
        assert start is not None and end is not None

        assignments = self._path_distributor.distribute(
            self.graph, start, end, len(self.drones)
        )
        if not assignments:
            raise RuntimeError(
                "No accessible path exists between start and end zones."
            )

        for drone, path in zip(self.drones, assignments):
            drone.assign_path(path[1:])

    def _all_arrived(self) -> bool:
        """Check whether every drone has reached the end zone.

        Returns:
            True if all drones have status ARRIVED.
        """
        return all(drone.has_arrived() for drone in self.drones)
