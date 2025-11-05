#!/usr/bin/env python3
"""
Example usage of the Easy Code Reader MCP Server

This example demonstrates how to interact with the MCP server programmatically.
"""

import asyncio
import json
from pathlib import Path

# Example 1: Basic server information
print("=" * 80)
print("Easy Code Reader MCP Server - Example Usage")
print("=" * 80)

print("""
The Easy Code Reader is a Model Context Protocol (MCP) server that provides
tools for reading and analyzing JAR files.

Available Tools:
1. list_jar_contents - List all files in a JAR archive
2. read_jar_file - Read a specific file from within a JAR
3. get_jar_manifest - Get the MANIFEST.MF content
4. extract_class_info - Get information about a class file

""")

# Example 2: Tool usage examples
print("Example Tool Calls:")
print("-" * 80)

example_calls = [
    {
        "tool": "list_jar_contents",
        "description": "List all contents of a JAR file",
        "arguments": {
            "jar_path": "/path/to/your/application.jar"
        }
    },
    {
        "tool": "read_jar_file",
        "description": "Read a specific file from the JAR",
        "arguments": {
            "jar_path": "/path/to/your/application.jar",
            "file_path": "META-INF/MANIFEST.MF",
            "encoding": "utf-8"
        }
    },
    {
        "tool": "get_jar_manifest",
        "description": "Get the JAR manifest",
        "arguments": {
            "jar_path": "/path/to/your/application.jar"
        }
    },
    {
        "tool": "extract_class_info",
        "description": "Get information about a compiled class",
        "arguments": {
            "jar_path": "/path/to/your/application.jar",
            "class_path": "com/example/MyClass.class"
        }
    }
]

for i, example in enumerate(example_calls, 1):
    print(f"\n{i}. {example['description']}")
    print(f"   Tool: {example['tool']}")
    print(f"   Arguments:")
    print(f"   {json.dumps(example['arguments'], indent=4)}")

print("\n" + "=" * 80)
print("Starting the server:")
print("-" * 80)
print("""
To start the MCP server, run:

    python -m easy_code_reader.server

Or use it with an MCP client by adding it to your client configuration.

Example Claude Desktop configuration (~/.config/claude/config.json):

{
  "mcpServers": {
    "easy-code-reader": {
      "command": "python",
      "args": ["-m", "easy_code_reader.server"]
    }
  }
}
""")

print("=" * 80)
