class OutputFormatter:
    """Formats simulation results into the subject's required text output."""

    def format(self, turn_log: list[list[str]]) -> str:
        """Format a full simulation trace as the subject's text output.

        Each turn becomes one line, listing space-separated movements.
        Drones that did not move during a turn are simply absent from
        that line, per the subject's output format.

        Args:
            turn_log: One list of movement strings per simulated turn,
                in order (e.g. [["D1-roof1", "D2-corridorA"],
                ["D1-roof2"]]).

        Returns:
            The full simulation trace as newline-separated text.
        """
        return "\n".join(
            " ".join(turn_movements) for turn_movements in turn_log
        )
