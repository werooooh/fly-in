import sys

from flyin.parsing import ParseError, parse_file
from flyin.simulation import SimulationEngine
from flyin.visualization import run_visualization


def main() -> int:
    """Run the full pipeline: parse the map, simulate, then visualize.

    Reads the map file path from the first command-line argument.

    Returns:
        Process exit code: 0 on success, 1 on a usage, parsing, or
        simulation error.
    """
    if len(sys.argv) < 2:
        print("Usage: python -m flyin.flyin <map_file>", file=sys.stderr)
        return 1

    map_file = sys.argv[1]

    try:
        graph, nb_drones = parse_file(map_file)
    except ParseError as exc:
        print(f"Error parsing map file: {exc}", file=sys.stderr)
        return 1

    engine = SimulationEngine(graph, nb_drones)
    try:
        turn_log = engine.run()
    except RuntimeError as exc:
        print(f"Simulation error: {exc}", file=sys.stderr)
        return 1

    print(f"Completed in {len(turn_log)} turns.", file=sys.stderr)
    run_visualization(graph, turn_log, nb_drones)

    return 0


if __name__ == "__main__":
    sys.exit(main())
