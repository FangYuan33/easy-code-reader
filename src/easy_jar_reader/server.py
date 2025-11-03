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
import logging
import zipfile
from pathlib import Path
from typing import Any

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
            name="list_jar_contents",
            description="List all files and directories in a JAR archive",
            inputSchema={
                "type": "object",
                "properties": {
                    "jar_path": {
                        "type": "string",
                        "description": "Path to the JAR file to read"
                    }
                },
                "required": ["jar_path"]
            }
        ),
        Tool(
            name="read_jar_file",
            description="Read a specific file from within a JAR archive",
            inputSchema={
                "type": "object",
                "properties": {
                    "jar_path": {
                        "type": "string",
                        "description": "Path to the JAR file"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file within the JAR archive"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "Text encoding to use (default: utf-8)",
                        "default": "utf-8"
                    }
                },
                "required": ["jar_path", "file_path"]
            }
        ),
        Tool(
            name="get_jar_manifest",
            description="Get the MANIFEST.MF content from a JAR file",
            inputSchema={
                "type": "object",
                "properties": {
                    "jar_path": {
                        "type": "string",
                        "description": "Path to the JAR file"
                    }
                },
                "required": ["jar_path"]
            }
        ),
        Tool(
            name="extract_class_info",
            description="Get basic information about a class file in the JAR",
            inputSchema={
                "type": "object",
                "properties": {
                    "jar_path": {
                        "type": "string",
                        "description": "Path to the JAR file"
                    },
                    "class_path": {
                        "type": "string",
                        "description": "Path to the .class file within the JAR"
                    }
                },
                "required": ["jar_path", "class_path"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls for JAR file operations."""
    try:
        if name == "list_jar_contents":
            return await list_jar_contents(arguments)
        elif name == "read_jar_file":
            return await read_jar_file(arguments)
        elif name == "get_jar_manifest":
            return await get_jar_manifest(arguments)
        elif name == "extract_class_info":
            return await extract_class_info(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def list_jar_contents(arguments: dict) -> list[TextContent]:
    """List all files in a JAR archive."""
    jar_path = arguments["jar_path"]
    
    if not Path(jar_path).exists():
        return [TextContent(type="text", text=f"Error: JAR file not found: {jar_path}")]
    
    try:
        with zipfile.ZipFile(jar_path, 'r') as jar:
            files = jar.namelist()
            
            # Organize files by type
            directories = []
            class_files = []
            resource_files = []
            other_files = []
            
            for file in sorted(files):
                if file.endswith('/'):
                    directories.append(file)
                elif file.endswith('.class'):
                    class_files.append(file)
                elif file.startswith('META-INF/'):
                    resource_files.append(file)
                else:
                    other_files.append(file)
            
            result = f"JAR Contents: {jar_path}\n"
            result += f"Total entries: {len(files)}\n\n"
            
            if class_files:
                result += f"Class files ({len(class_files)}):\n"
                for f in class_files[:20]:  # Show first 20
                    result += f"  {f}\n"
                if len(class_files) > 20:
                    result += f"  ... and {len(class_files) - 20} more\n"
                result += "\n"
            
            if resource_files:
                result += f"META-INF files ({len(resource_files)}):\n"
                for f in resource_files:
                    result += f"  {f}\n"
                result += "\n"
            
            if other_files:
                result += f"Other files ({len(other_files)}):\n"
                for f in other_files[:10]:  # Show first 10
                    result += f"  {f}\n"
                if len(other_files) > 10:
                    result += f"  ... and {len(other_files) - 10} more\n"
            
            return [TextContent(type="text", text=result)]
    
    except zipfile.BadZipFile:
        return [TextContent(type="text", text=f"Error: Invalid JAR/ZIP file: {jar_path}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error reading JAR: {str(e)}")]


async def read_jar_file(arguments: dict) -> list[TextContent]:
    """Read a specific file from a JAR archive."""
    jar_path = arguments["jar_path"]
    file_path = arguments["file_path"]
    encoding = arguments.get("encoding", "utf-8")
    
    if not Path(jar_path).exists():
        return [TextContent(type="text", text=f"Error: JAR file not found: {jar_path}")]
    
    try:
        with zipfile.ZipFile(jar_path, 'r') as jar:
            if file_path not in jar.namelist():
                return [TextContent(
                    type="text", 
                    text=f"Error: File '{file_path}' not found in JAR archive"
                )]
            
            # Read file content
            content = jar.read(file_path)
            
            # Try to decode as text
            try:
                text_content = content.decode(encoding)
                result = f"File: {file_path}\n"
                result += f"Size: {len(content)} bytes\n"
                result += f"Encoding: {encoding}\n\n"
                result += "Content:\n"
                result += "=" * 80 + "\n"
                result += text_content
                return [TextContent(type="text", text=result)]
            except UnicodeDecodeError:
                # If not text, show hex dump preview
                hex_preview = content[:200].hex()
                result = f"File: {file_path}\n"
                result += f"Size: {len(content)} bytes\n"
                result += f"Type: Binary file\n\n"
                result += "Hex preview (first 200 bytes):\n"
                result += hex_preview
                return [TextContent(type="text", text=result)]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error reading file: {str(e)}")]


async def get_jar_manifest(arguments: dict) -> list[TextContent]:
    """Get the MANIFEST.MF content from a JAR."""
    jar_path = arguments["jar_path"]
    
    if not Path(jar_path).exists():
        return [TextContent(type="text", text=f"Error: JAR file not found: {jar_path}")]
    
    try:
        with zipfile.ZipFile(jar_path, 'r') as jar:
            manifest_path = "META-INF/MANIFEST.MF"
            
            if manifest_path not in jar.namelist():
                return [TextContent(
                    type="text",
                    text="No MANIFEST.MF found in this JAR file"
                )]
            
            manifest_content = jar.read(manifest_path).decode('utf-8')
            result = f"JAR Manifest: {jar_path}\n\n"
            result += manifest_content
            
            return [TextContent(type="text", text=result)]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error reading manifest: {str(e)}")]


async def extract_class_info(arguments: dict) -> list[TextContent]:
    """Get basic information about a class file."""
    jar_path = arguments["jar_path"]
    class_path = arguments["class_path"]
    
    if not Path(jar_path).exists():
        return [TextContent(type="text", text=f"Error: JAR file not found: {jar_path}")]
    
    try:
        with zipfile.ZipFile(jar_path, 'r') as jar:
            if class_path not in jar.namelist():
                return [TextContent(
                    type="text",
                    text=f"Error: Class file '{class_path}' not found in JAR"
                )]
            
            class_bytes = jar.read(class_path)
            
            # Basic class file format analysis
            # Java class files start with magic number 0xCAFEBABE
            if len(class_bytes) < 8:
                return [TextContent(type="text", text="Error: Invalid class file (too small)")]
            
            magic = int.from_bytes(class_bytes[0:4], byteorder='big')
            minor_version = int.from_bytes(class_bytes[4:6], byteorder='big')
            major_version = int.from_bytes(class_bytes[6:8], byteorder='big')
            
            result = f"Class File: {class_path}\n\n"
            
            if magic == 0xCAFEBABE:
                result += "✓ Valid Java class file\n"
                result += f"Magic Number: 0x{magic:X}\n"
                result += f"Minor Version: {minor_version}\n"
                result += f"Major Version: {major_version}\n"
                
                # Map major version to Java version
                java_version_map = {
                    45: "Java 1.1",
                    46: "Java 1.2",
                    47: "Java 1.3",
                    48: "Java 1.4",
                    49: "Java 5",
                    50: "Java 6",
                    51: "Java 7",
                    52: "Java 8",
                    53: "Java 9",
                    54: "Java 10",
                    55: "Java 11",
                    56: "Java 12",
                    57: "Java 13",
                    58: "Java 14",
                    59: "Java 15",
                    60: "Java 16",
                    61: "Java 17",
                    62: "Java 18",
                    63: "Java 19",
                    64: "Java 20",
                    65: "Java 21",
                }
                
                java_version = java_version_map.get(major_version, f"Unknown (major version {major_version})")
                result += f"Compiled for: {java_version}\n"
                result += f"File size: {len(class_bytes)} bytes\n"
            else:
                result += f"✗ Invalid class file (magic number: 0x{magic:X})\n"
            
            return [TextContent(type="text", text=result)]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error analyzing class file: {str(e)}")]


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
