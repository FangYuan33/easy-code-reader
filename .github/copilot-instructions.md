# Copilot Instructions for Easy Code Reader

This guide helps AI coding agents work productively in the Easy Code Reader codebase. It summarizes architecture, workflows, conventions, and integration points unique to this project.

## Architecture Overview
**Purpose:** MCP (Model Context Protocol) server that extracts Java source code from Maven dependencies and local projects.

**Core Components:**
- `src/easy_code_reader/server.py`: MCP server implementation (4 tools: `read_jar_source`, `read_project_code`, `list_all_project`, `list_project_files`)
- `decompiler.py`: Auto-selects CFR (Java 8-20) or Fernflower (Java 21+) based on `_detect_java_version()`
- `config.py`: Maven repo path resolution via `MAVEN_HOME`, `M2_HOME`, or `MAVEN_REPO` env vars
- `decompilers/`: Bundled `fernflower.jar` and `cfr.jar` via setuptools package_data

**Data Flow:**
1. MCP request → `server.py` tool handler (`_read_jar_source` or project tools)
2. Maven path lookup: `group.id/artifact/version/artifact-version.jar` (handles SNAPSHOT timestamps)
3. Source extraction priority: sources JAR → decompilation → fallback class info
4. Decompilation cache: `{jar_dir}/easy-code-reader/{jar_name}/` (cleaned for SNAPSHOT updates)
5. Return JSON response with class/file code

**SNAPSHOT Handling:** For `-SNAPSHOT` versions, searches for timestamped JARs (e.g., `artifact-1.0.0-20251030.085053-1.jar`) for decompilation but caches under timestamped name. Old SNAPSHOT caches auto-deleted via `_cleanup_old_snapshot_cache` when newer timestamps detected.

## Developer Workflows
**Run Service:**
```bash
# Recommended (if published to PyPI)
uvx easy-code-reader [--maven-repo PATH] [--project-dir PATH]

# Development mode
python -m easy_code_reader [--maven-repo PATH] [--project-dir PATH]
```

**Testing:**
```bash
pytest tests/                     # All tests
pytest tests/test_jar_reader.py -v  # Specific test file
```

**Development Install:**
```bash
pip install -e .           # Editable install
pip install -e ".[dev]"    # With dev dependencies (pytest, build, twine)
```

**Publishing (maintainers only):**
```bash
./scripts/pre-publish-check.sh  # Validate before publish
./scripts/publish.sh            # Build and upload to PyPI
```

**Java Requirement:** JDK must be on PATH. Decompiler selection:
- Java < 21: CFR (backward compatible)
- Java ≥ 21: Fernflower (better for modern bytecode)
- Detection failure: defaults to CFR, logs warning

## Project-Specific Conventions
**Source Extraction Strategy:**
1. Check `artifact-version-sources.jar` (if `prefer_sources=True`, default)
2. Fallback to decompile `artifact-version.jar`
3. Last resort: `_fallback_class_info()` returns bytecode metadata stub

**Path Patterns (local projects):**
- Input: `com.example.MyClass` (Java class) or `pom.xml` or `src/main/resources/application.yml`
- Search order for Java classes: `src/main/java/`, `src/`, root, then submodules (detects via `pom.xml`/`build.gradle`)
- Search order for config files: root, `src/main/resources/`, `src/`, `config/`, then submodules
- Module detection: `_search_in_modules()` recursively checks subdirs with Maven/Gradle markers
- Supports all file types: `.java`, `.xml`, `.properties`, `.yaml`, `.json`, `.gradle`, `.md`, `.sql`, etc.

**File Filtering (list_project_files):**
- **Include:** `.java`, `.xml`, `.properties`, `.yaml`, `.json`, `.gradle`, `.md`, `pom.xml`
- **Exclude:** `src/test`, `target/`, `build/`, `.git/`, `.idea/`, `node_modules/`
- **Sub-path mode:** Use `sub_path` param to scope to `{project}/{sub_path}` for large projects (e.g., `"core"`)

**Caching Behavior:**
- Cache key: actual JAR path (Fernflower outputs to same dir, CFR uses temp dir then repackaged to ZIP → renamed to JAR)
- Cache invalidation: SNAPSHOT version timestamp changes trigger cleanup of old caches via `_cleanup_old_snapshot_cache()`
- Location: `{maven_repo}/{group}/{artifact}/{version}/easy-code-reader/{jar_name}.jar`
- Cache contains: Full JAR with decompiled `.java` files preserving package structure

## Integration Points
**MCP Protocol:**
- Uses `mcp>=0.9.0` via `stdio_server()` for Claude Desktop integration
- Tool schemas defined in `handle_list_tools()` (inputSchema = JSON Schema)
- Responses: JSON strings wrapped in `TextContent(type="text", text=...)`

**Claude Desktop Config Example:**
```json
{
  "mcpServers": {
    "easy-code-reader": {
      "command": "uvx",
      "args": ["easy-code-reader", "--maven-repo", "/custom/path"],
      "env": {}
    }
  }
}
```

**External Dependencies:**
- `uv`: Recommended for fast installs/runs (`uvx` command)
- Java: Must be in PATH for `subprocess.run(['java', '-jar', ...])` calls
- Decompiler JARs: Bundled via `package_data` in `pyproject.toml`

## Key Patterns & Examples
**AI-Friendly Error Messages:**
- Tools include intelligent, structured hints when queries fail with clear actionable steps
- `read_project_code` not found → Suggests using `list_project_files` with `file_name_pattern` for fuzzy matching first (reduces context size)
- `list_all_project` with `project_name_pattern` but no matches → Provides structured hint with emoji indicators (⚠️/✓) and numbered steps
- `list_project_files` with `file_name_pattern` but no matches → Explains possible reasons and multiple adjustment strategies
- Missing JAR → Returns detailed troubleshooting with priority-ordered steps, including how to check `pom.xml` and run Maven commands
- All hints emphasize context-efficiency strategies (fuzzy matching before full list) to optimize for LLM token usage

**Error Handling:**
- `UnsupportedClassVersionError` → Suggests upgrading Java or switching decompiler in `_decompile_with_cfr()` / `_decompile_with_fernflower()`
- Missing JAR → Returns error with Maven path, artifact coords, and step-by-step troubleshooting guide
- Bad class name → Returns error suggesting to use `list_project_files` first

**Testing Approach:**
- `tests/test_jar_reader.py`: Uses `tempfile` and `zipfile` to create test JARs with proper magic numbers
- `tests/test_decompiler.py`: Validates CFR/Fernflower selection logic based on Java version
- `tests/test_snapshot_*.py`: Tests SNAPSHOT version handling and cache cleanup
- No mocking of MCP protocol - tests focus on business logic

**Logging:**
- Configured in `server.py` to write to `easy_code_reader.log` + console (INFO level in production)
- Use `logger.info()` for key operations, `logger.warning()` for fallbacks
- Example: `logger.info(f"检测到 Java 版本: {java_version}")`

**Common Patterns:**
```python
# Path construction for Maven artifacts
group_path = group_id.replace('.', os.sep)
jar_dir = self.maven_home / group_path / artifact_id / version

# Decompilation with cache check
if decompiled_jar.exists():
    with zipfile.ZipFile(decompiled_jar, 'r') as zf:
        return zf.read(java_file_path).decode('utf-8')

# Multi-module project search
for subdir in project_path.iterdir():
    if (subdir / 'pom.xml').exists() or (subdir / 'build.gradle').exists():
        # Search in module
```

## Directory References
- `src/easy_code_reader/`: Main source (`server.py`, `decompiler.py`, `config.py`)
- `src/easy_code_reader/decompilers/`: Bundled `fernflower.jar`, `cfr.jar`
- `tests/`: Pytest tests (run with `pytest`)
- `scripts/`: Publish automation (`pre-publish-check.sh`, `publish.sh`)
- Docs: `README.md` (CN), `QUICK_START.md`, `PUBLISH_TO_PYPI.md`, `MIGRATION_TO_UVX.md`

## Troubleshooting
**"未找到 JAR 文件" error:** Verify Maven repo path and artifact exists via `ls ~/.m2/repository/{group}/{artifact}/{version}/`

**Decompilation hangs:** Check Java version with `java -version`. If < 8, decompilers won't work.

**SNAPSHOT not updating:** Cache is keyed by timestamped jar name. Manually delete `easy-code-reader/` cache dir if needed.

---
*Last updated: Based on codebase analysis as of v1.0.6*
