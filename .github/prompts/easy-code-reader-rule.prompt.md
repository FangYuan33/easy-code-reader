---
mode: agent
---
# Easy Code Reader Usage Rules

Use these two tools for Java source in a local Maven repository:

1. `search_group_id`: find candidate Maven groupIds and versions from a known artifact ID.
2. `read_jar_source`: read a fully qualified class from an explicit Maven coordinate.

## Search

Supply `artifact_id` without the version. If known, provide a complete `group_prefix`, such as `org.springframework`; it matches group segments from the beginning, case-insensitively. `version_hint` is an optional version substring. Omit uncertain filters. Every search reads the current repository directly, so newly installed or removed dependencies appear on the next call.

Choose the intended groupId and version from `matches`. Numeric version segments follow Maven ordering; do not infer the desired application version solely from the first result.

## Read

```json
{
  "group_id": "org.springframework",
  "artifact_id": "spring-core",
  "version": "5.3.21",
  "class_name": "org.springframework.core.SpringVersion"
}
```

Omitted line bounds return the complete source. To reduce subsequent output, pass `start_line` and/or `end_line`; lines are 1-based and both bounds are inclusive. For an explicit range, inspect `total_lines` and `is_partial` before treating a snippet as the whole implementation. Those fields are omitted for full reads.

Internal classes use binary names, such as `org.example.Outer$Inner`. The tool may return the outer file with a short warning. Full reads otherwise return only class_name, artifact, source_type and code.

Sources are preferred unless `prefer_sources=false`. SNAPSHOTs prefer the ordinary main JAR for reading and the latest timestamped main JAR name for caching, with numeric build-number ordering. If the ordinary main JAR is absent, read the timestamped JAR. Ordinary main JARs prefer ordinary sources, then matching timestamped sources; timestamped main JARs use matching sources. The actual path and resolved version are kept in internal diagnostics rather than repeated in every response.

## Errors

A tool failure sets MCP `isError=true` and provides `error.code`, `message` and `hint`. Do not treat diagnostic text as Java source.

- `ARTIFACT_NOT_FOUND`: verify coordinates with `search_group_id`, then download/install the dependency if needed.
- `CLASS_NOT_FOUND`: verify the full binary class name; the tool does not enumerate JAR classes.
- `SOURCE_DECODE_ERROR` / `INVALID_JAR`: check the input artifact.
- `DECOMPILER_UNAVAILABLE`: configure a compatible JDK.
- `DECOMPILE_FAILED` / `DECOMPILE_TIMEOUT`: inspect the hint; prefer a matching sources JAR or adjust the CLI timeout.
- `CACHE_UNAVAILABLE`: check write permissions on the `easy-code-reader` cache directory beside the original JAR.
- `INPUT_CHANGED`: retry after Maven finishes updating the input.

## Configuration

Use `--maven-repo` for an explicit path. Otherwise precedence is MAVEN_REPO, user settings.xml, global Maven settings.xml, and `~/.m2/repository`. MAVEN_HOME/M2_HOME only locate the Maven installation. Decompiled sources are cached beside the original JAR as `easy-code-reader/<cache JAR filename>`. Size and modification time validate the actual input JAR, even when the cache name uses a timestamp label. No content hashes or cross-process locks are used. No separate cache path is configured. Logs use stderr; no project directory configuration is needed.

MCP calls wait until source extraction or decompilation completes, or an error occurs. Asynchronous subprocess execution does not require task polling.
