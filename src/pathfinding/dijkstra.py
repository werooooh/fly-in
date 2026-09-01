import heapq

from models.graph import Graph
from models.zone import Zone


class PathResult:
    """The outcome of a shortest-path search between two zones.

    Attributes:
        path: The sequence of zones from start to end, both included.
        total_cost: The sum of movement costs to enter each zone
            along the path (the start zone itself is not counted).
    """

    def __init__(self, path: list[Zone], total_cost: int) -> None:
        """Initialize a PathResult.

        Args:
            path: The sequence of zones from start to end, inclusive.
            total_cost: The total movement cost of the path.
        """
        self.path = path
        self.total_cost = total_cost


class Pathfinder:
    """Hand-written Dijkstra shortest-path search over a Graph.

    No external graph library is used, per the subject's constraints.
    The priority queue relies only on the standard library's heapq.
    """

    def find_shortest_path(
        self,
        graph: Graph,
        start: Zone,
        end: Zone,
        zone_penalty: dict[str, int] | None = None,
    ) -> PathResult | None:
        """Find the lowest-cost path between two zones using Dijkstra.

        Movement cost is determined by the zone type being entered
        (normal/priority cost 1, restricted costs 2), plus an
        optional per-zone penalty used to steer the search away from
        congested zones when computing alternative routes. Blocked
        zones are never traversed.

        Args:
            graph: The graph to search within.
            start: The zone to start the search from.
            end: The zone to reach.
            zone_penalty: Optional extra cost added when entering a
                given zone name, used to discourage reusing zones
                already assigned to other paths. Defaults to no
                penalty.

        Returns:
            A PathResult describing the cheapest path, or None if no
            accessible path exists between start and end.
        """
        penalty = zone_penalty or {}
        distances: dict[str, int] = {start.name: 0}
        previous: dict[str, str] = {}
        visited: set[str] = set()
        heap: list[tuple[int, str]] = [(0, start.name)]

        while heap:
            current_distance, current_name = heapq.heappop(heap)
            if current_name in visited:
                continue
            visited.add(current_name)

            if current_name == end.name:
                break

            current_zone = graph.get_zone(current_name)
            self._relax_neighbors(
                graph,
                current_zone,
                current_distance,
                distances,
                previous,
                heap,
                penalty,
            )

        if end.name not in distances:
            return None

        path = self._reconstruct_path(graph, previous, start.name, end.name)
        return PathResult(path=path, total_cost=distances[end.name])

    def _relax_neighbors(
        self,
        graph: Graph,
        current_zone: Zone,
        current_distance: int,
        distances: dict[str, int],
        previous: dict[str, str],
        heap: list[tuple[int, str]],
        penalty: dict[str, int],
    ) -> None:
        """Update tentative distances for every accessible neighbor.

        Args:
            graph: The graph being searched.
            current_zone: The zone currently being expanded.
            current_distance: The best known distance to current_zone.
            distances: Mapping of zone name to best known distance so
                far. Mutated in place.
            previous: Mapping of zone name to the predecessor zone
                name on its current best path. Mutated in place.
            heap: The Dijkstra priority queue. Mutated in place.
            penalty: Extra cost per zone name, used to discourage
                congested zones during alternative-path searches.
        """
        for neighbor, _connection in graph.neighbors(current_zone):
            if not neighbor.zone_type.is_accessible():
                continue

            tentative_distance = (
                current_distance
                + neighbor.zone_type.movement_cost()
                + penalty.get(neighbor.name, 0)
            )
            best_known = distances.get(neighbor.name)

            if best_known is None or tentative_distance < best_known:
                distances[neighbor.name] = tentative_distance
                previous[neighbor.name] = current_zone.name
                heapq.heappush(heap, (tentative_distance, neighbor.name))

    def _reconstruct_path(
        self,
        graph: Graph,
        previous: dict[str, str],
        start_name: str,
        end_name: str,
    ) -> list[Zone]:
        """Rebuild the zone sequence from start to end using backlinks.

        Args:
            graph: The graph the search was run on.
            previous: Mapping of zone name to predecessor zone name.
            start_name: Name of the start zone.
            end_name: Name of the end zone.

        Returns:
            The list of Zone objects from start to end, inclusive.
        """
        names_reversed = [end_name]
        while names_reversed[-1] != start_name:
            names_reversed.append(previous[names_reversed[-1]])
        names_reversed.reverse()
        return [graph.get_zone(name) for name in names_reversed]
