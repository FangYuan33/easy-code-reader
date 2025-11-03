#!/usr/bin/env python3
"""
Simple integration test to verify the MCP server tools work correctly.

This demonstrates the core functionality without needing a full MCP client.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from easy_jar_reader.server import (
    list_jar_contents,
    read_jar_file,
    get_jar_manifest,
    extract_class_info
)


async def main():
    """Run integration tests with the sample JAR."""
    sample_jar = Path(__file__).parent / "sample.jar"
    
    if not sample_jar.exists():
        print("❌ Sample JAR not found. Please run: python examples/create_sample_jar.py")
        return 1
    
    print("=" * 80)
    print("Easy JAR Reader - Integration Test")
    print("=" * 80)
    print(f"\nUsing sample JAR: {sample_jar}\n")
    
    # Test 1: List JAR contents
    print("Test 1: Listing JAR contents")
    print("-" * 80)
    result = await list_jar_contents({"jar_path": str(sample_jar)})
    print(result[0].text)
    print()
    
    # Test 2: Get manifest
    print("Test 2: Reading JAR manifest")
    print("-" * 80)
    result = await get_jar_manifest({"jar_path": str(sample_jar)})
    print(result[0].text)
    print()
    
    # Test 3: Read a text file
    print("Test 3: Reading README.txt from JAR")
    print("-" * 80)
    result = await read_jar_file({
        "jar_path": str(sample_jar),
        "file_path": "README.txt",
        "encoding": "utf-8"
    })
    print(result[0].text)
    print()
    
    # Test 4: Extract class info
    print("Test 4: Extracting class file information")
    print("-" * 80)
    result = await extract_class_info({
        "jar_path": str(sample_jar),
        "class_path": "com/example/Main.class"
    })
    print(result[0].text)
    print()
    
    print("=" * 80)
    print("✓ All integration tests completed successfully!")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
