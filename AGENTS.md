# Repository Guidelines

## Project Structure & Module Organization

- `src/easy_code_reader/server.py` implements the MCP server, exposing `search_group_id` and `read_jar_source`, plus a usage-guide resource.
- `__main__.py` handles CLI arguments; `config.py` resolves Maven settings; `decompiler.py` selects CFR/Fernflower and manages caches.
- `src/easy_code_reader/decompilers/` contains bundled decompiler JARs. Preserve their package-data configuration in `pyproject.toml`.
- `tests/` contains JAR, decompiler, Maven-search, SNAPSHOT, and integration tests; shared fixtures belong in `conftest.py`.
- `README.md`, `.github/`, `imges/`, and `icon.png` contain documentation, automation, and illustrations. Release helpers live in `scripts/`.

## Build, Test, and Development Commands

Use Python 3.10+ and a JDK on `PATH` for decompilation. Run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]" "mcp<2"
python -m easy_code_reader --maven-repo /path/to/repository
python -m pytest -q
python -m pytest tests/test_search_group_id.py -v
python -m build
python -m twine check dist/*
```

These commands create a development environment, start the stdio server, run all or targeted tests, build distributions, and validate package metadata. The current server uses MCP 1 APIs; MCP 2 is incompatible despite the unrestricted dependency declaration. Release scripts contain legacy `easy-jar-reader` references; inspect them before use.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` for modules/functions/variables, `PascalCase` for classes, and uppercase constants. Follow surrounding Python style, retain type hints and concise docstrings, and prefix internal helpers with `_`. MCP handlers are asynchronous and return `TextContent` responses. Keep tool schemas, error hints, README examples, and the embedded guide consistent. No formatter or linter is configured.

## Testing Guidelines

Tests use pytest and pytest-asyncio with automatic asyncio mode. Name files `test_*.py` and functions `test_<behavior>`. Create temporary Maven repositories and synthetic JARs rather than relying on personal dependencies. Cover changed behavior, including source extraction, decompiler fallback, cache handling, and SNAPSHOT selection where relevant. No numeric coverage threshold is configured.

## Commit & Pull Request Guidelines

History uses short, descriptive subjects such as “Fix links and references in README”; no mandatory prefix scheme is evident. Keep commits focused. PR descriptions should explain the problem, resulting behavior, validation commands/results, and configuration changes. Link related issues when applicable and update affected documentation. Preserve unrelated working-tree changes.
