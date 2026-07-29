MAIN = flyin.py
MAP = maps/easy/01_linear_path.txt
#MAP = maps/easy/02_simple_fork.txt
#MAP = maps/easy/03_basic_capacity.txt
#MAP = maps/medium/01_dead_end_trap.txt
#MAP = maps/medium/02_circular_loop.txt
#MAP = maps/medium/03_priority_puzzle.txt
#MAP = maps/hard/01_maze_nightmare.txt
#MAP = maps/hard/02_capacity_hell.txt
#MAP = maps/hard/03_ultimate_challenge.txt
#MAP = maps/challenger/01_the_impossible_dream.txt

install:
	uv sync

run: ${NAME}
	uv run python ${NAME} ${MAP}

debug:
	uv run python -m pdb ${NAME} ${MAP}

clean:
	rm -rf .mypy_cache __pycache__ .pytest_cache

lint:
	uv run flake8 .
	uv run mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	uv run flake8 .
	uv run mypy . --strict

.PHONY: install run debug clean lint lint-strict test
