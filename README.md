*This project has been created as part of the 42 curriculum by romgutie.*

# Fly-in

## Description

Fly-in is a drone routing simulation. Given a map file describing a network
of connected zones, the program parses it into a graph, computes paths
from the start zone to the end zone with a hand-rolled Dijkstra search,
then schedules a fleet of drones through the network turn by turn while
respecting zone occupancy and connection capacity limits. The full
simulation is computed first; a pygame window then lets you step through
the result one turn at a time.

The goal is to deliver every drone from start to end in as few turns as
possible without ever violating a capacity constraint.

## Instructions

Uses [uv](https://docs.astral.sh/uv/) for dependencies.

```
make install        # install dependencies
make run             # run the simulation (edit MAP in the Makefile to change map)
make debug           # run under pdb
make lint            # flake8 + required mypy flags
make lint-strict     # flake8 + mypy --strict
make clean           # remove caches
```

The program takes the map file path as its only argument:

```
uv run python -m flyin.flyin maps/easy/01_linear_path.txt
```

Once the pygame window is open: **Right/Left arrow** step one turn
forward/backward (nothing advances on its own, and the terminal prints
each turn's line as it appears on screen), **mouse wheel** zooms on the
cursor, **left-click drag** pans, **R** resets the camera, **Escape**
quits.

## Algorithm choices and implementation strategy

Four packages under `src/flyin/`:

- **`parsing/`** — `MapParser` reads the map line by line straight into a
  `Graph`, validating metadata and structure as it goes. Any error is
  raised as a `ParseError` naming the line and cause.
- **`models/`** — `Zone`, `Connection`, `Graph`, `Drone` carry their own
  behaviour (e.g. `Zone.has_capacity_for` counts both drones physically
  present and drones already committed to land). No third-party graph
  library is used; `Graph` is entirely hand-rolled with an adjacency
  list for O(1) neighbor lookups.
- **`pathfinding/`** — `Pathfinder` runs Dijkstra (stdlib `heapq` only),
  using each zone's movement cost as edge weight. `PathDistributor`
  spreads drones across several routes instead of one: it reruns
  Dijkstra while penalizing already-used zones, but only keeps
  alternatives whose cost equals the cheapest path found — a costlier
  detour is discarded, since routing a drone through it can make that
  drone finish later than simply queueing on the cheapest path. Drones
  are assigned round-robin across the surviving equal-cost paths.
- **`simulation/`** — `SimulationEngine` runs the turn loop: landings
  are processed first (freeing capacity), then `TurnScheduler` resolves
  moves for the rest, in ascending `drone_id` order, applying each move
  immediately so a departure frees capacity within the same turn. A
  drone that lands this turn is excluded from that turn's movement
  phase, so it can't act twice in one turn. A drone entering a
  `restricted` zone commits for `movement_cost - 1` further turns (the
  commit turn is itself the first of the two) and reserves its landing
  slot immediately, since the subject forbids waiting mid-transit.

`SimulationEngine` stops with a `RuntimeError` past a configurable turn
cap (1000 by default) as a safety net against deadlock — given a single
start/end zone and an always-unlimited end zone, a true circular wait
does not appear constructible, so this exists as a guard against bugs
rather than a reachable case in practice.

Complexity (`V` zones, `E` connections, `D` drones): each Dijkstra run is
`O((V+E) log V)`, run at most 5 times regardless of `D`; each simulation
turn is `O(D)`. Paths are computed once and never recalculated.

## Visual representation

Built with `pygame`. `run_visualization` precomputes every drone's
position at every turn from the full turn log (interpolated along a
connection while mid-transit), then only replays that history — nothing
is recalculated live. Each turn draws every connection as a line, every
zone as a circle (using its declared `color`, or a color derived from
its `zone_type` otherwise), and every drone as a labelled dot.
Navigation is entirely manual (arrow keys, one turn at a time), and the
terminal output stays in sync with what's on screen. Mouse wheel/drag
zoom and pan, useful on larger maps where zones would otherwise overlap.

## Resources

- [Dijkstra's algorithm](https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm)
- [uv documentation](https://docs.astral.sh/uv/)
- [pygame documentation](https://www.pygame.org/docs/)

AI assistance (Claude) was used as a supporting tool during development, mainly for:

- Assisting with initial implementations and code refactoring.
- Helping identify and fix `flake8`/`mypy` issues and bugs found during testing.
- Reviewing implementation choices, including path distribution and turn-counting logic.
- Helping identify and remove unused code.

Every change was tested against the project's maps and the subject's
benchmarks, and the reasoning behind each decision was discussed and
understood, not accepted as a black box.

## Map file format

Plain text, blank lines and `#` comments ignored. `nb_drones: <n>` first,
then `start_hub:`/`end_hub:`/`hub: <name> <x> <y> [metadata]`, then
`connection: <name1>-<name2> [metadata]` (names cannot contain a dash).

| Tag | Applies to | Default | Meaning |
| --- | --- | --- | --- |
| `zone=` | zones | `normal` | `normal`, `priority` (1 turn), `restricted` (2 turns), `blocked` |
| `color=` | zones | none | display color |
| `max_drones=` | zones | `1` | capacity; unlimited on start/end |
| `max_link_capacity=` | connections | `1` | simultaneous crossings |

## Example

`maps/easy/01_linear_path.txt`:

```
nb_drones: 2
start_hub: start 0 0
hub: a 1 0
hub: b 2 0
end_hub: end 3 0
connection: start-a
connection: a-b
connection: b-end
```

```
uv run python -m flyin.flyin maps/easy/01_linear_path.txt
```

The pygame window opens showing the map. The terminal prints the initial
state, then one line per turn as you step through with the arrow keys:

```
Turn 0: (all drones at start)
Turn 1: D1-a
Turn 2: D1-b D2-a
Turn 3: D1-end D2-b
Turn 4: D2-end
```

Both drones follow the only path, one turn behind each other since every
zone here defaults to a capacity of one.
