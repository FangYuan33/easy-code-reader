# Copilot Instructions for Easy Code Reader

## Architecture

The stdio MCP server exposes exactly `search_group_id` and `read_jar_source`.

- `server.py`: schemas, MCP responses, guide resource; failures use `CallToolResult(isError=True)`.
- `service.py`: source-first reading and fallback orchestration.
- `repository.py`: strict Maven resolution, normalized SNAPSHOT input with timestamp-based cache names, fresh repository searches without an in-memory result cache.
- `versions.py`: Maven ComparableVersion semantics; see NOTICE for attribution.
- `source.py`: class checks, strict UTF-8 source extraction, internal-class mapping and inclusive line ranges.
- `decompiler.py`: asynchronous Java child processes, compatible fallback, timeout and cancellation.
- `cache.py`: JAR-name disk caches, size/mtime validation, atomic publication and LRU cleanup; no hashes or file locks.
- `config.py`: immutable per-server settings. `io_utils.py` waits for cancelled file workers before workspace cleanup.

## Behavioral Contracts

- Prefer the ordinary SNAPSHOT JAR as input; use the newest timestamped main JAR name (timestamp plus numeric build number) for its cache. Fall back to that timestamped JAR when the ordinary input is absent; use the ordinary filename when no timestamps exist.
- For ordinary SNAPSHOT inputs, prefer ordinary sources, then matching timestamped sources. Timestamped inputs use matching sources. Source-only repositories are readable when `prefer_sources=True`.
- Never substitute tests/all classifier JARs or files outside the configured repository.
- Internal names use `Outer$Inner`; include a short warning when returning an outer file.
- Omitted line limits return the complete original text using only class_name, artifact, source_type and code; line metadata appears only for explicit ranges.
- Never manufacture Java source on failure. Return a stable error code and actionable hint.
- Cache names come from the selected timestamp label for SNAPSHOTs, or the actual input filename otherwise. Validate size and modification time against the actual input JAR; regenerate legacy archives missing that metadata. Cache hits read source directly without starting Java. Decompilers receive the absolute original JAR path; use private workspaces for output only and verify the original file state before publishing.
- Use independent temporary paths and atomic publication. Concurrent misses may decompile more than once; there is no cross-process lock. Construct the cache per request from the actual JAR path; never mutate a shared cache location when reading different versions concurrently. Do not put blocking scans or Java calls in the event loop.

## Development

```bash
python -m pip install -e ".[dev]"
python -m easy_code_reader --maven-repo /path/to/repository
python -m pytest -q
python scripts/smoke_test.py
python -m build
python -m twine check dist/*
```

Python 3.10+ is required. Tests compile real Java fixtures with `javac --release 8`; use JDK 11 or 21. MCP 1.30+ within major version 1 is supported.

Keep the two tool schemas, embedded guide, README and usage prompt consistent. Use temporary Maven repositories and caches in tests. Validate actual methods, cache freshness and protocol error flags; ensure an MCP call returns only after the source is ready; a placeholder string or class-file magic header alone does not prove successful decompilation.

## Configuration and Publishing

Repository priority: CLI, MAVEN_REPO, user settings, Maven global settings, default `~/.m2/repository`. MAVEN_HOME/M2_HOME locate the Maven installation, not its dependency repository. Logs go to stderr. Each artifact version stores its cache beside the original JAR in `easy-code-reader/<cache JAR filename>`, with a 1 GiB budget per version directory; Java request timeout defaults to 60 seconds; there is no application-level decompiler concurrency limit.

PR CI tests Python/JDK combinations and installed wheels on Linux/macOS/Windows. Publishing is a separate maintainer action and requires the verification workflow. Review scripts before publishing; do not upload as part of routine code changes.
