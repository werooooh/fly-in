import re

import pygame

from models.graph import Graph
from models.zone import Zone, ZoneType

_WINDOW_WIDTH = 900
_WINDOW_HEIGHT = 650
_MARGIN = 80
_ZONE_RADIUS = 26
_DRONE_RADIUS = 8
_FPS = 60

_ZOOM_MIN = 0.2
_ZOOM_MAX = 6.0
_ZOOM_STEP = 1.1

_BACKGROUND = (18, 18, 22)
_LINE_COLOR = (90, 90, 100)
_TEXT_COLOR = (235, 235, 235)
_DRONE_COLOR = (255, 255, 255)

_NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "red": (220, 60, 60),
    "green": (70, 190, 90),
    "blue": (70, 120, 220),
    "yellow": (230, 200, 60),
    "magenta": (200, 70, 200),
    "cyan": (70, 200, 200),
    "white": (230, 230, 230),
    "gray": (130, 130, 130),
    "grey": (130, 130, 130),
}

_TYPE_FALLBACK_COLORS: dict[ZoneType, tuple[int, int, int]] = {
    ZoneType.NORMAL: (200, 200, 200),
    ZoneType.PRIORITY: (230, 200, 60),
    ZoneType.RESTRICTED: (220, 120, 60),
    ZoneType.BLOCKED: (70, 70, 70),
}

_MOVEMENT_RE = re.compile(r"^(?P<drone>D\d+)-(?P<destination>.+)$")


class Camera:
    """Tracks the current zoom level and pan offset of the viewport."""

    def __init__(self) -> None:
        """Initialize the camera at identity zoom with no pan offset."""
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0

    def reset(self) -> None:
        """Reset the camera to its initial identity state."""
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0

    def to_screen(self, position: tuple[int, int]) -> tuple[int, int]:
        """Convert a base (unzoomed) pixel position to screen space.

        Args:
            position: A base pixel position from the layout.

        Returns:
            The corresponding on-screen pixel position after applying
            the current zoom and pan.
        """
        x, y = position
        return (
            int(x * self.zoom + self.pan_x),
            int(y * self.zoom + self.pan_y),
        )

    def zoom_at(self, cursor: tuple[int, int], factor: float) -> None:
        """Zoom in or out while keeping the point under the cursor fixed.

        Args:
            cursor: The current mouse position in screen space.
            factor: Multiplier applied to the current zoom level
                (>1.0 zooms in, <1.0 zooms out).
        """
        mouse_x, mouse_y = cursor
        world_x = (mouse_x - self.pan_x) / self.zoom
        world_y = (mouse_y - self.pan_y) / self.zoom

        new_zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self.zoom * factor))
        self.pan_x = mouse_x - world_x * new_zoom
        self.pan_y = mouse_y - world_y * new_zoom
        self.zoom = new_zoom

    def pan_by(self, dx: int, dy: int) -> None:
        """Shift the viewport by a screen-space pixel delta.

        Args:
            dx: Horizontal shift in pixels.
            dy: Vertical shift in pixels.
        """
        self.pan_x += dx
        self.pan_y += dy


def _zone_color(zone: Zone) -> tuple[int, int, int]:
    """Resolve the RGB fill color of a zone for rendering.

    Args:
        zone: The zone to color.

    Returns:
        An RGB tuple. Uses the zone's declared color if valid,
        otherwise falls back to a color based on its zone type.
    """
    if zone.color is not None:
        named = _NAMED_COLORS.get(zone.color.lower())
        if named is not None:
            return named
    return _TYPE_FALLBACK_COLORS[zone.zone_type]


def _compute_layout(graph: Graph) -> dict[str, tuple[int, int]]:
    """Map every zone's model coordinates to base pixel positions.

    Args:
        graph: The graph whose zones need pixel coordinates.

    Returns:
        A mapping of zone name to (pixel_x, pixel_y) in base
        (unzoomed) space, scaled and centered to fit the window with
        margins. The camera applies zoom/pan on top of this.
    """
    xs = [zone.x for zone in graph.zones.values()]
    ys = [zone.y for zone in graph.zones.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    span_x = max(max_x - min_x, 1)
    span_y = max(max_y - min_y, 1)
    drawable_w = _WINDOW_WIDTH - 2 * _MARGIN
    drawable_h = _WINDOW_HEIGHT - 2 * _MARGIN

    layout: dict[str, tuple[int, int]] = {}
    for zone in graph.zones.values():
        px = _MARGIN + int((zone.x - min_x) / span_x * drawable_w)
        py = _MARGIN + int((zone.y - min_y) / span_y * drawable_h)
        layout[zone.name] = (px, py)
    return layout


def _replay_positions(
    turn_log: list[list[str]], graph: Graph, nb_drones: int
) -> list[dict[str, tuple[str, float]]]:
    """Reconstruct each drone's location at every turn of the simulation.

    A drone's location is either a zone it currently occupies, or a
    connection it is mid-transit on with a progress fraction (0.0
    just departed, 1.0 about to land). Turns where a drone produces
    no movement string mean it is either stationary at a zone or
    still in flight, so its state simply carries forward.

    Args:
        turn_log: One list of movement strings per simulated turn.
        graph: The graph the simulation ran on.
        nb_drones: Number of drones in the simulation.

    Returns:
        One snapshot per step, index 0 being the initial state before
        any movement (all drones at the start zone), followed by one
        snapshot per simulated turn. Each snapshot maps drone label to
        (identifier, progress), where identifier is a zone name or a
        connection name and progress is the transit fraction.
    """
    assert graph.start_zone is not None
    state: dict[str, tuple[str, float]] = {
        f"D{i}": (graph.start_zone.name, 0.0) for i in range(1, nb_drones + 1)
    }
    connection_names = {conn.name(): conn for conn in graph.connections}
    transit_progress: dict[str, int] = {}

    snapshots: list[dict[str, tuple[str, float]]] = [dict(state)]
    for movements in turn_log:
        moved_this_turn: set[str] = set()
        for movement in movements:
            match = _MOVEMENT_RE.match(movement)
            if match is None:
                continue
            label = match.group("drone")
            destination = match.group("destination")
            moved_this_turn.add(label)

            if destination in graph.zones:
                state[label] = (destination, 0.0)
                transit_progress.pop(label, None)
            elif destination in connection_names:
                state[label] = (destination, 0.0)
                transit_progress[label] = 1

        for label in list(transit_progress.keys()):
            if label in moved_this_turn:
                continue
            transit_progress[label] += 1
            elapsed = transit_progress[label]
            fraction = min(elapsed / 2.0, 1.0)
            name, _ = state[label]
            state[label] = (name, fraction)

        snapshots.append(dict(state))
    return snapshots


def _drone_base_position(
    location: tuple[str, float],
    graph: Graph,
    layout: dict[str, tuple[int, int]],
) -> tuple[int, int]:
    """Compute a drone's base (unzoomed) pixel position from its state.

    Args:
        location: The drone's (identifier, progress) state, where
            identifier is either a zone name or a connection name.
        graph: The graph the simulation ran on.
        layout: Precomputed base pixel positions for every zone.

    Returns:
        The (x, y) base pixel coordinates to draw the drone at,
        before camera zoom/pan is applied.
    """
    identifier, fraction = location
    if identifier in layout:
        return layout[identifier]

    connection = next(
        (conn for conn in graph.connections if conn.name() == identifier),
        None,
    )
    if connection is None:
        return (_WINDOW_WIDTH // 2, _WINDOW_HEIGHT // 2)

    start_x, start_y = layout[connection.zone_a.name]
    end_x, end_y = layout[connection.zone_b.name]
    x = start_x + (end_x - start_x) * fraction
    y = start_y + (end_y - start_y) * fraction
    return (int(x), int(y))


def _draw_zones(
    surface: "pygame.Surface",
    graph: Graph,
    layout: dict[str, tuple[int, int]],
    font: "pygame.font.Font",
    camera: Camera,
) -> None:
    """Draw every connection then every zone onto the surface.

    Args:
        surface: The pygame surface to draw on.
        graph: The graph to render.
        layout: Precomputed base pixel positions for every zone.
        font: The font used for zone labels.
        camera: The current viewport zoom and pan state.
    """
    for connection in graph.connections:
        start = camera.to_screen(layout[connection.zone_a.name])
        end = camera.to_screen(layout[connection.zone_b.name])
        pygame.draw.line(surface, _LINE_COLOR, start, end, 2)

    radius = max(4, int(_ZONE_RADIUS * camera.zoom))
    for zone in graph.zones.values():
        position = camera.to_screen(layout[zone.name])
        pygame.draw.circle(surface, _zone_color(zone), position, radius)
        pygame.draw.circle(surface, _TEXT_COLOR, position, radius, width=2)
        label = font.render(zone.name, True, _TEXT_COLOR)
        label_pos = (
            position[0] - label.get_width() // 2,
            position[1] + radius + 4,
        )
        surface.blit(label, label_pos)


def _draw_drones(
    surface: "pygame.Surface",
    snapshot: dict[str, tuple[str, float]],
    graph: Graph,
    layout: dict[str, tuple[int, int]],
    font: "pygame.font.Font",
    camera: Camera,
) -> None:
    """Draw every drone at its current position for this turn.

    Args:
        surface: The pygame surface to draw on.
        snapshot: This turn's drone-to-location mapping.
        graph: The graph the simulation ran on.
        layout: Precomputed base pixel positions for every zone.
        font: The font used for drone labels.
        camera: The current viewport zoom and pan state.
    """
    radius = max(3, int(_DRONE_RADIUS * camera.zoom))
    for label, location in snapshot.items():
        base_pos = _drone_base_position(location, graph, layout)
        x, y = camera.to_screen(base_pos)
        pygame.draw.circle(surface, _DRONE_COLOR, (x, y), radius)
        text = font.render(label, True, _DRONE_COLOR)
        surface.blit(text, (x + radius, y - radius))


def _print_turn(index: int, turn_log: list[list[str]]) -> None:
    """Print the movement line for a single step to the terminal.

    Called at the moment that step becomes visible on screen, so the
    terminal output stays in sync with the graphical navigation.

    Args:
        index: The displayed step number. 0 is the initial state
            before any movement; index i (i >= 1) corresponds to
            turn_log[i - 1].
        turn_log: One list of movement strings per simulated turn.
    """
    if index == 0:
        print("Turn 0: (all drones at start)")
        return
    movements = turn_log[index - 1]
    line = " ".join(movements) if movements else "(waiting)"
    print(f"Turn {index}: {line}")


def run_visualization(
    graph: Graph, turn_log: list[list[str]], nb_drones: int
) -> None:
    """Open a pygame window and step through the simulation manually.

    Controls:
        RIGHT/LEFT step one turn forward/backward. Each step prints
        that turn's movement line to the terminal, in sync with what
        appears on screen.
        Mouse wheel zooms in/out, centered on the cursor.
        Left-click drag pans the view.
        R resets the camera to the default fit-to-window view.
        ESC or closing the window exits.

    Args:
        graph: The graph the simulation ran on.
        turn_log: One list of movement strings per simulated turn.
        nb_drones: Number of drones in the simulation.
    """
    pygame.init()
    pygame.key.set_repeat(0)
    screen = pygame.display.set_mode((_WINDOW_WIDTH, _WINDOW_HEIGHT))
    pygame.display.set_caption("Fly-in - Drone Routing Simulation")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 14)
    big_font = pygame.font.SysFont("consolas", 20, bold=True)

    layout = _compute_layout(graph)
    snapshots = _replay_positions(turn_log, graph, nb_drones)
    camera = Camera()

    current_turn = 0
    running = True
    dragging = False
    _print_turn(current_turn, turn_log)

    while running:
        clock.tick(_FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    if current_turn < len(snapshots) - 1:
                        current_turn += 1
                        _print_turn(current_turn, turn_log)
                elif event.key == pygame.K_LEFT:
                    if current_turn > 0:
                        current_turn -= 1
                        _print_turn(current_turn, turn_log)
                elif event.key == pygame.K_r:
                    camera.reset()
            elif event.type == pygame.MOUSEWHEEL:
                factor = _ZOOM_STEP if event.y > 0 else 1 / _ZOOM_STEP
                camera.zoom_at(pygame.mouse.get_pos(), factor)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    dragging = True
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    dragging = False
            elif event.type == pygame.MOUSEMOTION:
                if dragging:
                    rel_x, rel_y = event.rel
                    camera.pan_by(rel_x, rel_y)

        screen.fill(_BACKGROUND)
        _draw_zones(screen, graph, layout, font, camera)
        _draw_drones(
            screen, snapshots[current_turn], graph, layout, font, camera
        )

        header = big_font.render(
            f"Turn {current_turn} / {len(snapshots) - 1}", True, _TEXT_COLOR
        )
        screen.blit(header, (_MARGIN // 2, 20))

        pygame.display.flip()

    pygame.quit()
