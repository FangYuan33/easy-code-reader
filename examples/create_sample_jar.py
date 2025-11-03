#!/usr/bin/env python3
"""
Create a sample JAR file for testing the MCP server.

This script creates a simple JAR file with some test content.
"""

import zipfile
from pathlib import Path

# Create a temporary directory for our sample JAR
output_dir = Path(__file__).parent
jar_path = output_dir / "sample.jar"

print(f"Creating sample JAR file: {jar_path}")

# Create the JAR file
with zipfile.ZipFile(jar_path, 'w', zipfile.ZIP_DEFLATED) as jar:
    # Add a manifest
    manifest_content = """Manifest-Version: 1.0
Created-By: Easy JAR Reader Example
Main-Class: com.example.Main
Implementation-Version: 1.0.0
"""
    jar.writestr("META-INF/MANIFEST.MF", manifest_content)
    
    # Add a sample Java class file (simplified, not real bytecode)
    # This is a mock - real class files would have proper bytecode
    class_header = bytes([
        0xCA, 0xFE, 0xBA, 0xBE,  # Magic number
        0x00, 0x00,               # Minor version: 0
        0x00, 0x34,               # Major version: 52 (Java 8)
    ])
    # Add some random bytes to simulate class content
    class_content = class_header + b'\x00' * 200
    jar.writestr("com/example/Main.class", class_content)
    jar.writestr("com/example/Helper.class", class_content)
    
    # Add a properties file
    properties_content = """
# Application Configuration
app.name=Sample Application
app.version=1.0.0
app.author=Easy JAR Reader
"""
    jar.writestr("application.properties", properties_content)
    
    # Add a text file
    readme_content = """
Sample JAR File
===============

This is a sample JAR file created for testing the Easy JAR Reader MCP Server.

Contents:
- META-INF/MANIFEST.MF - JAR manifest
- com/example/Main.class - Main class
- com/example/Helper.class - Helper class
- application.properties - Configuration file
- README.txt - This file
"""
    jar.writestr("README.txt", readme_content)
    
    # Add a resource file
    jar.writestr("resources/icon.txt", "This would be an icon file in a real application")

print("Sample JAR file created successfully!")
print("\nYou can now test the MCP server with this JAR file using commands like:")
print(f"  - List contents: list_jar_contents('{jar_path}')")
print(f"  - Read manifest: get_jar_manifest('{jar_path}')")
print(f"  - Read file: read_jar_file('{jar_path}', 'README.txt')")
print(f"  - Class info: extract_class_info('{jar_path}', 'com/example/Main.class')")
