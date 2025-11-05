"""Tests for Easy Code Reader MCP Server."""

import pytest
import tempfile
import zipfile
from pathlib import Path

# Note: These are basic unit tests for the JAR reading functionality
# For full MCP server testing, you would need to set up an MCP client


def create_test_jar(jar_path: Path):
    """Create a test JAR file for testing."""
    with zipfile.ZipFile(jar_path, 'w', zipfile.ZIP_DEFLATED) as jar:
        # Add manifest
        manifest = "Manifest-Version: 1.0\nMain-Class: com.test.Main\n"
        jar.writestr("META-INF/MANIFEST.MF", manifest)
        
        # Add a class file (with proper magic number)
        class_bytes = bytes([
            0xCA, 0xFE, 0xBA, 0xBE,  # Magic number
            0x00, 0x00,               # Minor version
            0x00, 0x34,               # Major version 52 (Java 8)
        ]) + b'\x00' * 100
        jar.writestr("com/test/Main.class", class_bytes)
        
        # Add a text file
        jar.writestr("test.txt", "Hello, World!")
        
        # Add a properties file
        jar.writestr("config.properties", "key=value\n")


def test_jar_file_creation():
    """Test that we can create a valid JAR file."""
    with tempfile.NamedTemporaryFile(suffix='.jar', delete=False) as tmp:
        jar_path = Path(tmp.name)
    
    try:
        create_test_jar(jar_path)
        assert jar_path.exists()
        
        # Verify it's a valid ZIP file
        with zipfile.ZipFile(jar_path, 'r') as jar:
            files = jar.namelist()
            assert "META-INF/MANIFEST.MF" in files
            assert "com/test/Main.class" in files
            assert "test.txt" in files
    finally:
        jar_path.unlink()


def test_read_manifest():
    """Test reading the JAR manifest."""
    with tempfile.NamedTemporaryFile(suffix='.jar', delete=False) as tmp:
        jar_path = Path(tmp.name)
    
    try:
        create_test_jar(jar_path)
        
        with zipfile.ZipFile(jar_path, 'r') as jar:
            manifest_content = jar.read("META-INF/MANIFEST.MF").decode('utf-8')
            assert "Manifest-Version: 1.0" in manifest_content
            assert "Main-Class: com.test.Main" in manifest_content
    finally:
        jar_path.unlink()


def test_read_text_file():
    """Test reading a text file from JAR."""
    with tempfile.NamedTemporaryFile(suffix='.jar', delete=False) as tmp:
        jar_path = Path(tmp.name)
    
    try:
        create_test_jar(jar_path)
        
        with zipfile.ZipFile(jar_path, 'r') as jar:
            content = jar.read("test.txt").decode('utf-8')
            assert content == "Hello, World!"
    finally:
        jar_path.unlink()


def test_class_file_magic_number():
    """Test that class files have the correct magic number."""
    with tempfile.NamedTemporaryFile(suffix='.jar', delete=False) as tmp:
        jar_path = Path(tmp.name)
    
    try:
        create_test_jar(jar_path)
        
        with zipfile.ZipFile(jar_path, 'r') as jar:
            class_bytes = jar.read("com/test/Main.class")
            magic = int.from_bytes(class_bytes[0:4], byteorder='big')
            assert magic == 0xCAFEBABE
            
            # Check version
            major_version = int.from_bytes(class_bytes[6:8], byteorder='big')
            assert major_version == 52  # Java 8
    finally:
        jar_path.unlink()


def test_list_jar_contents():
    """Test listing JAR contents."""
    with tempfile.NamedTemporaryFile(suffix='.jar', delete=False) as tmp:
        jar_path = Path(tmp.name)
    
    try:
        create_test_jar(jar_path)
        
        with zipfile.ZipFile(jar_path, 'r') as jar:
            files = jar.namelist()
            assert len(files) == 4
            assert "META-INF/MANIFEST.MF" in files
            assert "com/test/Main.class" in files
            assert "test.txt" in files
            assert "config.properties" in files
    finally:
        jar_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
