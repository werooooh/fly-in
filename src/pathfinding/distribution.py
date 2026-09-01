from models.graph import Graph
from models.zone import Zone
from pathfinding.dijkstra import Pathfinder

_PENALTY_PER_USE = 3


class PathDistributor:
    """Spreads drones across multiple distinct paths to reduce congestion.

    Computing a single shortest path and sending every drone down it
    creates an avoidable bottleneck whenever the graph offers real
    alternatives. This class searches for several distinct paths by
    repeatedly running Dijkstra while penalizing zones already used
    by previously found paths, then assigns drones to the discovered
    paths in round-robin order.

    This is a practical heuristic rather than a full k-shortest-paths
    algorithm (such as Yen's algorithm): it favors simplicity and
    speed over guaranteeing the globally optimal set of alternative
    routes. It only ever spreads drones across paths of equal total
    cost -- a costlier detour is never used, since routing a drone
    through it could make that drone finish later than if it had
    simply queued on the cheapest path instead.
    """

    def __init__(self, pathfinder: Pathfinder) -> None:
        """Initialize the distributor with a pathfinder to search with.

        Args:
            pathfinder: The Dijkstra search used to compute each
                candidate path.
        """
        self._pathfinder = pathfinder

    def distribute(
        self, graph: Graph, start: Zone, end: Zone, nb_drones: int
    ) -> list[list[Zone]]:
        """Compute a path assignment for every drone in the fleet.

        Args:
            graph: The network to route through.
            start: The zone all drones depart from.
            end: The zone all drones must reach.
            nb_drones: Number of drones needing a path.

        Returns:
            One path per drone (start and end zones included), in
            drone order. Drones share paths round-robin across the
            distinct alternatives found. Empty if no path exists.
        """
        distinct_paths = self._find_distinct_paths(
            graph, start, end, max_paths=min(nb_drones, 5)
        )
        if not distinct_paths:
            return []

        return [
            distinct_paths[i % len(distinct_paths)]
            for i in range(nb_drones)
        ]

    def _find_distinct_paths(
        self, graph: Graph, start: Zone, end: Zone, max_paths: int
    ) -> list[list[Zone]]:
        """Search for up to max_paths equal-cost distinct routes.

        Only alternatives whose total cost matches the cheapest path
        found are kept. A costlier detour would make any drone
        routed through it finish later than it would have simply
        waiting its turn on the cheapest path, so diversifying onto
        it can hurt overall completion time instead of helping it.
        Equal-cost alternatives are always safe to spread drones
        across, since no drone is individually worse off.

        Args:
            graph: The network to route through.
            start: The zone to depart from.
            end: The zone to reach.
            max_paths: Upper bound on the number of distinct paths to
                collect.

        Returns:
            A list of distinct, equal-cost paths (each a list of
            Zone). Empty if no path exists at all.
        """
        zone_penalty: dict[str, int] = {}
        paths: list[list[Zone]] = []
        cheapest_cost: int | None = None

        for _ in range(max_paths):
            result = self._pathfinder.find_shortest_path(
                graph, start, end, zone_penalty
            )
            if result is None:
                break
            if cheapest_cost is None:
                cheapest_cost = result.total_cost
            elif result.total_cost > cheapest_cost:
                break
            if paths and self._same_path(result.path, paths[-1]):
                break

            paths.append(result.path)
            for zone in result.path[1:-1]:
                zone_penalty[zone.name] = (
                    zone_penalty.get(zone.name, 0) + _PENALTY_PER_USE
                )

        return paths

    def _same_path(self, path_a: list[Zone], path_b: list[Zone]) -> bool:
        """Check whether two paths visit the exact same zone sequence.

        Args:
            path_a: The first path to compare.
            path_b: The second path to compare.

        Returns:
            True if both paths have identical zone sequences.
        """
        return [z.name for z in path_a] == [z.name for z in path_b]
