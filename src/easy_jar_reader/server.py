#!/usr/bin/env python3
"""
Easy JAR Reader MCP Server

This is a Model Context Protocol (MCP) server that provides tools for reading
and analyzing JAR (Java Archive) files. It allows you to:
- List contents of JAR files
- Read files from within JAR archives
- Extract class file information
- Get JAR manifest details

Example usage with MCP client:
    The server provides the following tools:
    - list_jar_contents: List all files in a JAR archive
    - read_jar_file: Read a specific file from a JAR archive
    - get_jar_manifest: Get the MANIFEST.MF content from a JAR
    - extract_class_info: Get basic information about a class file
"""

import asyncio
import json
import logging
import zipfile
from pathlib import Path
from typing import Any, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("easy-jar-reader")

# Create MCP server instance
app = Server("easy-jar-reader")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for JAR file operations."""
    return [
        Tool(
            name="read_jar_file",
            description="Read a specific file from within a JAR archive",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id": {"type": "string", "description": "Maven group ID"},
                    "artifact_id": {"type": "string", "description": "Maven artifact ID"},
                    "version": {"type": "string", "description": "Maven version"},
                    "class_name": {"type": "string", "description": "Fully qualified class name"},
                    "prefer_sources": {"type": "boolean", "default": True,
                                       "description": "Prefer source jar over decompilation"},
                    "summarize_large_content": {"type": "boolean", "default": True,
                                                "description": "Summarize large content automatically"},
                    "max_lines": {"type": "integer", "default": 500,
                                  "description": "Maximum lines to return (0 for all)"}
                },
                "required": ["group_id", "artifact_id", "version", "class_name"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls for JAR file operations."""
    try:
        if name == "read_jar_file":
            return await read_jar_file(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def read_jar_file(self, group_id: str, artifact_id: str, version: str,
                        class_name: str, prefer_sources: bool = True,
                        summarize_large_content: bool = True, max_lines: int = 500) -> List[TextContent]:
    """Extract source code from jar or decompile"""
    # First try to find sources jar
    if prefer_sources:
        sources_jar = self._get_sources_jar_path(group_id, artifact_id, version)
        if sources_jar and sources_jar.exists():
            source_code = self._extract_from_sources_jar(sources_jar, class_name)
            if source_code:
                result = {
                    "source": "sources-jar",
                    "class_name": class_name,
                    "artifact": f"{group_id}:{artifact_id}:{version}",
                    "code": source_code
                }
                if summarize_large_content and self.response_manager.should_summarize(result["code"]):
                    result["code"] = self.response_manager.summarize_large_text(result["code"])
                    result["summarized"] = True
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Fall back to decompilation
    jar_path = self._get_jar_path(group_id, artifact_id, version)
    if not jar_path or not jar_path.exists():
        return [TextContent(type="text", text=f"Jar file not found: {group_id}:{artifact_id}:{version}")]

    try:
        decompiled_code = self.decompiler.decompile_class(jar_path, class_name)
        result = {
            "source": "decompiled",
            "class_name": class_name,
            "artifact": f"{group_id}:{artifact_id}:{version}",
            "code": decompiled_code or "Failed to decompile class",
            "available_decompilers": list(self.decompiler.available_decompilers.keys())
        }
        if summarize_large_content and self.response_manager.should_summarize(result["code"]):
            result["code"] = self.response_manager.summarize_large_text(result["code"])
            result["summarized"] = True
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error extracting source code: {str(e)}")]

def get_sources_jar_path(self, group_id: str, artifact_id: str, version: str) -> Optional[Path]:
    """Get path to sources jar file"""
    group_path = group_id.replace('.', os.sep)
    jar_dir = self.maven_home / group_path / artifact_id / version
    sources_jar = jar_dir / f"{artifact_id}-{version}-sources.jar"
    return sources_jar if sources_jar.exists() else None

def extract_from_sources_jar(self, sources_jar: Path, class_name: str) -> Optional[str]:
    """Extract source code from sources jar"""
    try:
        java_file = class_name.replace('.', '/') + '.java'
        with zipfile.ZipFile(sources_jar, 'r') as jar:
            if java_file in jar.namelist():
                return jar.read(java_file).decode('utf-8', errors='ignore')
    except Exception:
        pass
    return None


async def main():
    """Run the MCP server."""
    logger.info("Starting Easy JAR Reader MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
