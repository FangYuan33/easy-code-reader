---
mode: agent
---
# Easy Code Reader MCP Server - Usage Rules

## Overview
This MCP server provides two tools for reading Java source code from Maven JAR dependencies: `search_group_id` and `read_jar_source`.

## Usage Scenarios and Tool Selection

### Scenario 1: Reading JAR Package Source Code

**When to use:** User wants to read source code from Maven dependencies or JAR packages.

**Tool:** `read_jar_source`

**Trigger keywords in user prompt:**
- "read jar", "read dependency", "read from jar"
- "Maven dependency source code"
- "show me the code from [group:artifact:version]"
- "decompile", "source jar"
- References to specific Maven coordinates (groupId:artifactId:version)

**Usage pattern:**
```
User: "Read the SpringVersion class from spring-core 5.3.21"
Action: Use read_jar_source with:
  - group_id: "org.springframework"
  - artifact_id: "spring-core"
  - version: "5.3.21"
  - class_name: "org.springframework.core.SpringVersion"
```

**How it works:**
- First attempts to extract source from `-sources.jar` if available
- Falls back to decompiling from the main JAR file if no source JAR exists
- Returns the complete Java source code

---

## Finding Maven Coordinates

Use `search_group_id` when the artifact ID is known but the groupId or available versions are uncertain.

- `artifact_id` (required): JAR name without its version, such as `spring-core`.
- `group_prefix` (optional): One or two groupId segments, such as `org.springframework`.
- `version_hint` (optional): Version filter; omit it if the version is uncertain.

Select a `group_id` and a version from `matches[].matched_versions`, then call `read_jar_source` with the complete Maven coordinates and fully qualified class name.

## Important Notes

- Use fully qualified class names, such as `org.example.MyClass`.
- Source extraction tries sources JAR first, then decompilation; set `prefer_sources=false` to request decompilation directly.
- If no Maven coordinates match, check the artifact ID and relax optional search filters.
- If a JAR is missing, verify the configured Maven repository and download or install the dependency there.

---

## Example Conversations

**Example 1: Reading JAR dependency**
```
User: "Show me the Gson class from google's gson library version 2.8.9"

Assistant thought process:
- Keywords: library, version → JAR dependency scenario
- Action: read_jar_source
  - group_id: "com.google.code.gson"
  - artifact_id: "gson"
  - version: "2.8.9"
  - class_name: "com.google.gson.Gson"
```

## Configuration Requirements

- Configure the Maven repository with `--maven-repo` when starting the server.
- Configuration priority: `--maven-repo`, `$MAVEN_HOME/repository`, `$M2_HOME/repository`, `$MAVEN_REPO`, then `~/.m2/repository`.
- A JDK is required for decompiling class files.
