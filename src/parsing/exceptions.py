class ParseError(Exception):
    """Base exception for any error encountered while parsing a map.

    Attributes:
        message: Human-readable description of the problem.
        line_number: The 1-indexed line number where the error was
            detected, if applicable.
    """

    def __init__(self, message: str, line_number: int | None = None) -> None:
        """Initialize a ParseError.

        Args:
            message: Description of what went wrong.
            line_number: The line where the error occurred, if known.
        """
        self.message = message
        self.line_number = line_number
        prefix = f"Line {line_number}: " if line_number is not None else ""
        super().__init__(f"{prefix}{message}")


class SyntaxErrorInMap(ParseError):
    """Raised when a line does not match the expected map syntax."""


class MetadataError(ParseError):
    """Raised when a metadata block is malformed or invalid."""


class StructuralError(ParseError):
    """Raised for whole-file structural issues.

    Examples include a missing or duplicated start/end hub, or a
    missing nb_drones declaration.
    """
