---
mode: agent
---
# Easy Code Reader MCP Server - Usage Rules

## Overview
This MCP server provides tools for reading Java source code from two main sources:
1. **Maven JAR dependencies** - Read source code from JAR files in the Maven repository
2. **Local project files** - Read source code from local Java projects on disk

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

### Scenario 2: Reading Local Project Source Code

**When to use:** User wants to read, analyze, or understand code from local Java projects.

This scenario uses **three complementary tools** that work together:

#### Tool 1: `list_all_project`
**Purpose:** Discover available projects in the configured directory.

**When to use:**
- User asks "what projects are available?"
- User mentions a project name that might not be exact
- Need to verify project existence before reading code
- User's prompt doesn't specify a clear project name

**Usage pattern:**
```
User: "What Java projects do you have?"
Action: Call list_all_project
Returns: List of all project folder names
```

**Best practice:** When user mentions a project name that doesn't exist, call this tool to find the closest match and suggest alternatives.

#### Tool 2: `list_project_files`
**Purpose:** Get an overview of a project's structure and available files.

**When to use:**
- User wants to understand project structure
- Need to find specific files or classes within a project
- Analyzing class relationships and dependencies
- Project has too many files and need to focus on specific modules
- Before reading multiple related files

**Usage pattern:**
```
User: "Show me all files in the nacos project"
Action: Call list_project_files with:
  - project_name: "nacos"
  
User: "Show me files in the core module of nacos"
Action: Call list_project_files with:
  - project_name: "nacos"
  - sub_path: "core"
```

**Returns:**
- Filtered list of source files (.java) and configuration files
- Automatically excludes test directories, build outputs, and IDE configs
- Relative paths from project root (e.g., "core/src/main/java/...")

**Two modes:**
1. **Whole project mode** (no sub_path): Returns all files in the entire project
2. **Focused mode** (with sub_path): Returns only files in specified subdirectory

**Use focused mode when:**
- Project has hundreds of files
- User asks about a specific module (e.g., "core", "api", "client")
- Need to narrow down to a specific package or directory

#### Tool 3: `read_project_code`
**Purpose:** Read the actual content of a specific source file.

**When to use:**
- User asks to read a specific class or file
- After using list_project_files to identify files of interest
- User provides class name or file path to read

**Usage pattern:**
```
User: "Read the AddressServerGeneratorManager class from nacos"
Action: Call read_project_code with:
  - project_name: "nacos"
  - class_name: "com.alibaba.nacos.address.component.AddressServerGeneratorManager"
  
Or with relative path:
  - project_name: "nacos"
  - class_name: "address/src/main/java/com/alibaba/nacos/address/component/AddressServerGeneratorManager.java"
```

**Input formats supported:**
- Fully qualified class name: `com.example.MyClass`
- Relative file path: `src/main/java/com/example/MyClass.java`
- Module-relative path: `core/src/main/java/com/example/MyClass.java`

**Smart search:**
- Searches common Maven/Gradle source directories
- Supports multi-module projects
- Automatically searches in submodules

---

## Recommended Workflows

### Workflow 1: Explore Unknown Project
```
Step 1: list_all_project
  → Get available project names

Step 2: list_project_files (project_name: "target-project")
  → Understand project structure and available files

Step 3: read_project_code (based on files found in Step 2)
  → Read specific source files of interest
```

### Workflow 2: Analyze Specific Module
```
Step 1: list_project_files (project_name: "nacos", sub_path: "core")
  → Get all files in the core module

Step 2: Identify relevant classes from the file list

Step 3: read_project_code for each relevant class
  → Read and analyze the code
```

### Workflow 3: Find and Read Specific Class
```
Step 1: If project name uncertain → list_all_project

Step 2: read_project_code with class name
  → Directly read if you know the class name
```

### Workflow 4: Analyze Class Relationships
```
Step 1: list_project_files (optionally with sub_path)
  → Get comprehensive file list

Step 2: Analyze file paths to understand package structure

Step 3: read_project_code for related classes
  → Read classes in the same package or related packages
```

---

## Tool Selection Decision Tree

```
User mentions JAR/dependency/Maven coordinates?
  ├─ YES → Use read_jar_source
  └─ NO → Reading local project code?
      ├─ Needs project list or uncertain project name?
      │   └─ Use list_all_project
      │
      ├─ Needs file overview or project structure?
      │   ├─ Whole project → list_project_files (no sub_path)
      │   └─ Specific module → list_project_files (with sub_path)
      │
      └─ Knows specific file/class to read?
          └─ Use read_project_code
```

---

## Important Notes

### For read_jar_source:
- Always provide complete Maven coordinates (groupId, artifactId, version)
- Use fully qualified class names (e.g., `org.example.MyClass`, not just `MyClass`)
- The tool automatically tries sources JAR first, then decompiles if needed

### For list_project_files:
- Returns **filtered results** - only source code and config files
- Excludes: test directories (`src/test`), build outputs (`target`, `build`), IDE configs
- Use `sub_path` parameter to reduce results when project is large
- File paths in results are relative to project root

### For read_project_code:
- Supports both fully qualified class names and relative file paths
- Automatically searches in multi-module projects
- If class name is ambiguous, the tool searches common patterns

### Error Handling:
- If project name doesn't match, call `list_all_project` to find correct name
- If class not found, call `list_project_files` to explore available files
- If sub_path doesn't exist in `list_project_files`, remove it or verify with project structure

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

**Example 2: Exploring local project**
```
User: "I want to understand the nacos project structure"

Assistant thought process:
- Keywords: understand structure → Need file overview
- Action 1: list_project_files(project_name: "nacos")
  → Returns list of all source files with paths
- Action 2: Analyze the returned file list and explain the structure
```

**Example 3: Finding specific class in unknown project**
```
User: "Read the UserService class, I think it's in one of my projects"

Assistant thought process:
- Unknown project → Need to find it first
- Action 1: list_all_project
  → Get: ["project-a", "project-b", "my-app"]
- Action 2: Try read_project_code for each project or ask user to specify
```

**Example 4: Analyzing module in large project**
```
User: "Show me all the configuration files in the nacos core module"

Assistant thought process:
- Keywords: core module, configuration → Focused file listing
- Action: list_project_files(project_name: "nacos", sub_path: "core")
  → Returns filtered list showing .properties, .xml, .yaml files in core/
```

---

## Configuration Requirements

- **Maven Repository Path**: Configure via `--maven-repo-path` or uses default `~/.m2/repository`
- **Local Project Directory**: Configure via `--project-dir` parameter when starting the MCP server
- Both paths can also be provided in individual tool calls if different from server defaults

---

By following these rules, you can effectively utilize the Easy Code Reader MCP Server to read and analyze Java source code from both Maven dependencies and local projects.
