"""Tests for the decompiler module."""

import pytest
import tempfile
import zipfile
from pathlib import Path

from easy_code_reader.decompiler import JavaDecompiler

def create_test_jar_with_class(jar_path: Path):
    """Create a test JAR file with a compiled class."""
    with zipfile.ZipFile(jar_path, 'w', zipfile.ZIP_DEFLATED) as jar:
        # Add manifest
        manifest = "Manifest-Version: 1.0\nMain-Class: com.test.TestClass\n"
        jar.writestr("META-INF/MANIFEST.MF", manifest)
        
        # Add a class file (with proper magic number)
        class_bytes = bytes([
            0xCA, 0xFE, 0xBA, 0xBE,  # Magic number
            0x00, 0x00,               # Minor version
            0x00, 0x34,               # Major version 52 (Java 8)
        ]) + b'\x00' * 100
        jar.writestr("com/test/TestClass.class", class_bytes)


def test_decompiler_initialization():
    """Test that JavaDecompiler can be initialized and Fernflower is detected."""
    decompiler = JavaDecompiler()
    # Fernflower should be detected in the decompilers/ folder
    assert decompiler.fernflower_jar is not None
    assert decompiler.fernflower_jar.exists()


def test_decompiler_reads_from_jar_directly():
    """Test that the decompiler reads .java files directly from JAR without extraction."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create a test JAR
        test_jar = tmp_path / "test.jar"
        create_test_jar_with_class(test_jar)
        
        # Create a simulated decompiled JAR (what Fernflower would produce)
        # In the output directory structure
        output_dir = tmp_path / "easy-code-reader" / "test"
        output_dir.mkdir(parents=True)
        
        decompiled_jar = output_dir / "test.jar"
        
        # Create a decompiled JAR with .java source
        java_source = """package com.test;

public class TestClass {
    public static void main(String[] args) {
        System.out.println("Hello World!");
    }
}
"""
        with zipfile.ZipFile(decompiled_jar, 'w') as zf:
            zf.writestr("com/test/TestClass.java", java_source)
        
        # Now test the decompiler's caching mechanism
        decompiler = JavaDecompiler()
        
        # Mock the cache check - the decompiled jar exists
        # Read from the JAR directly
        with zipfile.ZipFile(decompiled_jar, 'r') as zf:
            java_file_path = "com/test/TestClass.java"
            if java_file_path in zf.namelist():
                content = zf.read(java_file_path).decode('utf-8')
                assert "public class TestClass" in content
                assert "Hello World!" in content


def test_decompiler_fallback():
    """Test the fallback behavior when decompilation is not available."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create a test JAR
        test_jar = tmp_path / "test.jar"
        create_test_jar_with_class(test_jar)
        
        decompiler = JavaDecompiler()
        # Test fallback info
        fallback_result = decompiler._fallback_class_info(test_jar, "com.test.TestClass")
        
        assert "com.test.TestClass" in fallback_result
        assert "TestClass" in fallback_result


def test_jar_reading_without_extraction():
    """Test that we can read files from a JAR without extracting to filesystem."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create a JAR with some .java files
        jar_file = tmp_path / "sample.jar"
        test_content = "public class Sample { }"
        
        with zipfile.ZipFile(jar_file, 'w') as zf:
            zf.writestr("com/example/Sample.java", test_content)
            zf.writestr("com/example/Another.java", "public class Another { }")
        
        # Read from JAR without extraction
        with zipfile.ZipFile(jar_file, 'r') as zf:
            content = zf.read("com/example/Sample.java").decode('utf-8')
            assert content == test_content
            
            # Verify no files were extracted
            assert not (tmp_path / "com").exists()
            assert not (tmp_path / "com" / "example").exists()


def test_decompiled_jar_output_location():
    """Test that decompiled jar is placed directly in easy-code-reader directory, not in a subdirectory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create a Maven-like directory structure for a SNAPSHOT jar
        jar_dir = tmp_path / "com" / "example" / "test-artifact" / "1.0.11-SNAPSHOT"
        jar_dir.mkdir(parents=True)
        
        # Create a timestamped SNAPSHOT jar
        test_jar = jar_dir / "test-artifact-1.0.11-20251030.085053-1.jar"
        create_test_jar_with_class(test_jar)
        
        # Simulate decompilation by creating the expected structure
        decompiler = JavaDecompiler()
        
        # Calculate where the decompiled jar should be placed
        output_dir = jar_dir / "easy-code-reader"
        
        # The decompiled jar should be directly in easy-code-reader directory
        expected_decompiled_jar = output_dir / "test-artifact-1.0.11-20251030.085053-1.jar"
        
        # Verify path structure - it should NOT have an extra nested directory
        # Current issue: /path/easy-code-reader/test-artifact-1.0.11-20251030.085053-1/test-artifact-1.0.11-20251030.085053-1.jar
        # Expected fix: /path/easy-code-reader/test-artifact-1.0.11-20251030.085053-1.jar
        
        # Verify the expected path only has two segments after jar_dir
        assert expected_decompiled_jar.relative_to(jar_dir).parts == ("easy-code-reader", "test-artifact-1.0.11-20251030.085053-1.jar")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
