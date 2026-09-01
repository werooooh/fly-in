"""Parser that turns a Fly-in map file into a Graph and drone count."""

from __future__ import annotations

import re
from pathlib import Path

from models.connection import Connection
from models.graph import Graph
from models.zone import Zone, ZoneType
from parsing.exceptions import (
    MetadataError,
    ParseError,
    StructuralError,
    SyntaxErrorInMap,
)

_ZONE_TYPES_BY_VALUE = {zone_type.value: zone_type for zone_type in ZoneType}

_ZONE_LINE_RE = re.compile(
    r"^(?P<name>[^\s\[\]-]+)\s+(?P<x>-?\d+)\s+(?P<y>-?\d+)"
    r"(?:\s*\[(?P<metadata>.*)\])?$"
)
_CONNECTION_LINE_RE = re.compile(
    r"^(?P<a>[^\s\[\]-]+)-(?P<b>[^\s\[\]-]+)"
    r"(?:\s*\[(?P<metadata>.*)\])?$"
)
_NB_DRONES_RE = re.compile(r"^(?P<count>\d+)$")

_ZONE_METADATA_KEYS = {"zone", "color", "max_drones"}
_CONNECTION_METADATA_KEYS = {"max_link_capacity"}


class MapParser:
    """Parses a Fly-in map file into a Graph and a drone count.

    Usage:
        parser = MapParser()
        graph, nb_drones = parser.parse("maps/easy_1.txt")
    """

    def __init__(self) -> None:
        """Initialize an empty parser state."""
        self.graph = Graph()
        self.nb_drones: int | None = None

    def parse(self, filepath: str) -> tuple[Graph, int]:
        """Parse a map file into a Graph and a drone count.

        Args:
            filepath: Path to the map file to parse.

        Returns:
            A tuple of (graph, nb_drones).

        Raises:
            ParseError: If the file cannot be read, or contains any
                syntax, metadata, or structural error.
        """
        path = Path(filepath)
        if not path.is_file():
            raise ParseError(f"Map file not found: {filepath!r}")

        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                self._process_line(line_number, raw_line)

        self._validate_structure()
        assert self.nb_drones is not None  # guaranteed by validation
        return self.graph, self.nb_drones

    def _process_line(self, line_number: int, raw_line: str) -> None:
        """Dispatch a single line to the appropriate handler.

        Args:
            line_number: 1-indexed position of the line in the file.
            raw_line: The raw line content, including whitespace.

        Raises:
            ParseError: If the line has an unrecognized prefix or is
                otherwise invalid.
        """
        line = raw_line.strip()
        if not line or line.startswith("#"):
            return

        if ":" not in line:
            raise SyntaxErrorInMap(
                "Missing ':' after line prefix.", line_number
            )

        prefix, _, rest = line.partition(":")
        prefix = prefix.strip()
        rest = rest.strip()

        handlers = {
            "nb_drones": self._parse_nb_drones,
            "start_hub": lambda ln, r: self._parse_zone(ln, r, is_start=True),
            "end_hub": lambda ln, r: self._parse_zone(ln, r, is_end=True),
            "hub": lambda ln, r: self._parse_zone(ln, r),
            "connection": self._parse_connection,
        }

        handler = handlers.get(prefix)
        if handler is None:
            raise SyntaxErrorInMap(
                f"Unknown line prefix {prefix!r}.", line_number
            )
        handler(line_number, rest)

    def _parse_nb_drones(self, line_number: int, rest: str) -> None:
        """Parse the nb_drones declaration.

        Args:
            line_number: 1-indexed line position, for error reporting.
            rest: The content of the line after "nb_drones:".

        Raises:
            StructuralError: If nb_drones is declared more than once.
            SyntaxErrorInMap: If the value is not a positive integer.
        """
        if self.nb_drones is not None:
            raise StructuralError(
                "nb_drones declared more than once.", line_number
            )

        match = _NB_DRONES_RE.match(rest)
        if match is None or int(match.group("count")) <= 0:
            raise SyntaxErrorInMap(
                f"Invalid nb_drones value: {rest!r}. "
                "Expected a positive integer.",
                line_number,
            )
        self.nb_drones = int(match.group("count"))

    def _parse_zone(
        self,
        line_number: int,
        rest: str,
        is_start: bool = False,
        is_end: bool = False,
    ) -> None:
        """Parse a hub/start_hub/end_hub line and register the zone.

        Args:
            line_number: 1-indexed line position, for error reporting.
            rest: The line content after the prefix (e.g. "hub:").
            is_start: Whether this line defines the start hub.
            is_end: Whether this line defines the end hub.

        Raises:
            SyntaxErrorInMap: If the line does not match the expected
                zone syntax.
            MetadataError: If the metadata block is invalid.
            StructuralError: If the zone conflicts with an existing
                one (duplicate name, duplicate start/end).
        """
        match = _ZONE_LINE_RE.match(rest)
        if match is None:
            raise SyntaxErrorInMap(
                f"Invalid zone definition: {rest!r}.", line_number
            )

        metadata = self._parse_metadata(
            line_number, match.group("metadata"), _ZONE_METADATA_KEYS
        )
        zone_type = self._resolve_zone_type(line_number, metadata)
        max_drones = self._resolve_max_drones(line_number, metadata)

        zone = Zone(
            name=match.group("name"),
            x=int(match.group("x")),
            y=int(match.group("y")),
            zone_type=zone_type,
            color=metadata.get("color"),
            max_drones=max_drones,
            is_start=is_start,
            is_end=is_end,
        )
        try:
            self.graph.add_zone(zone)
        except ValueError as exc:
            raise StructuralError(str(exc), line_number) from exc

    def _parse_connection(self, line_number: int, rest: str) -> None:
        """Parse a connection line and register it in the graph.

        Args:
            line_number: 1-indexed line position, for error reporting.
            rest: The line content after "connection:".

        Raises:
            SyntaxErrorInMap: If the line does not match the expected
                connection syntax.
            MetadataError: If the metadata block is invalid.
            StructuralError: If either endpoint is undefined or the
                connection duplicates an existing one.
        """
        match = _CONNECTION_LINE_RE.match(rest)
        if match is None:
            raise SyntaxErrorInMap(
                f"Invalid connection definition: {rest!r}.", line_number
            )

        metadata = self._parse_metadata(
            line_number, match.group("metadata"), _CONNECTION_METADATA_KEYS
        )
        capacity = self._resolve_positive_int(
            line_number, metadata, "max_link_capacity", default=1
        )

        name_a, name_b = match.group("a"), match.group("b")
        try:
            zone_a = self.graph.get_zone(name_a)
            zone_b = self.graph.get_zone(name_b)
        except KeyError as exc:
            raise StructuralError(
                f"Connection references undefined zone: {exc}", line_number
            ) from exc

        try:
            self.graph.add_connection(
                Connection(zone_a, zone_b, max_link_capacity=capacity)
            )
        except ValueError as exc:
            raise StructuralError(str(exc), line_number) from exc

    def _parse_metadata(
        self,
        line_number: int,
        raw_metadata: str | None,
        allowed_keys: set[str],
    ) -> dict[str, str]:
        """Parse a "[key=value key2=value2]" metadata block.

        Args:
            line_number: 1-indexed line position, for error reporting.
            raw_metadata: The raw content between brackets, or None if
                no metadata block was present.
            allowed_keys: The set of metadata keys valid in this
                context (differs between zone and connection lines).

        Returns:
            A mapping of metadata key to its raw string value.

        Raises:
            MetadataError: If a token is malformed or uses an unknown
                key for this context.
        """
        if not raw_metadata:
            return {}

        result: dict[str, str] = {}
        for token in raw_metadata.split():
            if "=" not in token:
                raise MetadataError(
                    f"Malformed metadata token: {token!r}.", line_number
                )
            key, _, value = token.partition("=")
            if key not in allowed_keys:
                raise MetadataError(
                    f"Unknown metadata key: {key!r}.", line_number
                )
            result[key] = value
        return result

    def _resolve_zone_type(
        self, line_number: int, metadata: dict[str, str]
    ) -> ZoneType:
        """Resolve the zone= metadata entry into a ZoneType.

        Args:
            line_number: 1-indexed line position, for error reporting.
            metadata: Parsed metadata for the zone line.

        Returns:
            The resolved ZoneType, defaulting to NORMAL if unset.

        Raises:
            MetadataError: If the declared zone type is not valid.
        """
        raw_type = metadata.get("zone", ZoneType.NORMAL.value)
        if raw_type not in _ZONE_TYPES_BY_VALUE:
            raise MetadataError(
                f"Invalid zone type: {raw_type!r}.", line_number
            )
        return _ZONE_TYPES_BY_VALUE[raw_type]

    def _resolve_max_drones(
        self, line_number: int, metadata: dict[str, str]
    ) -> int:
        """Resolve the max_drones= metadata entry.

        Args:
            line_number: 1-indexed line position, for error reporting.
            metadata: Parsed metadata for the zone line.

        Returns:
            The declared max_drones value, defaulting to 1.

        Raises:
            MetadataError: If the value is not a positive integer.
        """
        return self._resolve_positive_int(
            line_number, metadata, "max_drones", default=1
        )

    def _resolve_positive_int(
        self,
        line_number: int,
        metadata: dict[str, str],
        key: str,
        default: int,
    ) -> int:
        """Resolve a metadata entry expected to be a positive integer.

        Args:
            line_number: 1-indexed line position, for error reporting.
            metadata: Parsed metadata mapping.
            key: The metadata key to resolve.
            default: Value to use if the key is absent.

        Returns:
            The resolved positive integer.

        Raises:
            MetadataError: If the value is present but not a positive
                integer.
        """
        if key not in metadata:
            return default
        raw_value = metadata[key]
        if not raw_value.isdigit() or int(raw_value) <= 0:
            raise MetadataError(
                f"{key} must be a positive integer, got {raw_value!r}.",
                line_number,
            )
        return int(raw_value)

    def _validate_structure(self) -> None:
        """Validate whole-file structural requirements after parsing.

        Raises:
            StructuralError: If nb_drones is missing, or the graph
                lacks a start or end zone.
        """
        if self.nb_drones is None:
            raise StructuralError("Missing nb_drones declaration.")
        if not self.graph.is_ready():
            missing = []
            if self.graph.start_zone is None:
                missing.append("start_hub")
            if self.graph.end_zone is None:
                missing.append("end_hub")
            raise StructuralError(
                f"Missing required zone(s): {', '.join(missing)}."
            )


def parse_file(filepath: str) -> tuple[Graph, int]:
    """Parse a map file into a Graph and drone count.

    Convenience wrapper around MapParser for one-off parsing.

    Args:
        filepath: Path to the map file to parse.

    Returns:
        A tuple of (graph, nb_drones).

    Raises:
        ParseError: If the file cannot be read or is invalid.
    """
    return MapParser().parse(filepath)
