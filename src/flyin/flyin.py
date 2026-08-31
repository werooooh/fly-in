import argparse
import sys

from flyin.parsing import ParseError, parse_file
from flyin.simulation import OutputFormatter, SimulationEngine
from flyin.visualization import run_visualization


class FlyInCLI:
    """Command-line entry point: parse, simulate, print, then visualize."""

    def __init__(self) -> None:
        """Initialize the CLI with its formatter and argument parser."""
        self._formatter = OutputFormatter()
        self._arg_parser = self._build_arg_parser()

    def _build_arg_parser(self) -> argparse.ArgumentParser:
        """Build the command-line argument parser for the simulator.

        Returns:
            A configured ArgumentParser instance.
        """
        parser = argparse.ArgumentParser(
            prog="flyin",
            description=(
                "Simulate a fleet of drones routing from a start zone "
                "to an end zone through a network of connected zones."
            ),
        )
        parser.add_argument(
            "map_file",
            help="Path to the map file describing zones and connections.",
        )
        parser.add_argument(
            "--no-visual",
            action="store_true",
            help="Skip the graphical pygame visualization window.",
        )
        parser.add_argument(
            "--max-turns",
            type=int,
            default=1000,
            help=(
                "Safety cap on the number of turns to simulate before "
                "giving up (default: 1000)."
            ),
        )
        return parser

    def run(self, argv: list[str] | None = None) -> int:
        """Run the full pipeline: parse, simulate, print, then visualize.

        Args:
            argv: Command-line arguments, excluding the program name.
                Defaults to sys.argv[1:] when None.

        Returns:
            Process exit code: 0 on success, 1 on a parsing or
            simulation error.
        """
        args = self._arg_parser.parse_args(argv)

        try:
            graph, nb_drones = parse_file(args.map_file)
        except ParseError as exc:
            print(f"Error parsing map file: {exc}", file=sys.stderr)
            return 1

        engine = SimulationEngine(graph, nb_drones, max_turns=args.max_turns)
        try:
            turn_log = engine.run()
        except RuntimeError as exc:
            print(f"Simulation error: {exc}", file=sys.stderr)
            return 1

        if args.no_visual:
            print(self._formatter.format(turn_log))
            print(f"\nCompleted in {len(turn_log)} turns.", file=sys.stderr)
        else:
            print(f"Completed in {len(turn_log)} turns.", file=sys.stderr)
            run_visualization(graph, turn_log, nb_drones)

        return 0


if __name__ == "__main__":
    sys.exit(FlyInCLI().run())
