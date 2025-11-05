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

from easy_code_reader.server import (
    read_jar_file
)


async def main():
    """Run integration tests with the sample JAR."""
    sample_jar = Path(__file__).parent / "sample.jar"
    
    if not sample_jar.exists():
        print("❌ Sample JAR not found. Please run: python examples/create_sample_jar.py")
        return 1
    
    print("=" * 80)
    print("Easy Code Reader - Integration Test")
    print("=" * 80)
    print(f"\nUsing sample JAR: {sample_jar}\n")
    
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

    print(result[0].text)
    print()
    
    print("=" * 80)
    print("✓ All integration tests completed successfully!")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
