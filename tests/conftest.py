"""Test configuration and fixtures."""

import pytest


@pytest.fixture
def sample_jar_content():
    """Sample JAR file content for testing."""
    return {
        "manifest": "Manifest-Version: 1.0\nMain-Class: com.example.Main\n",
        "text_file": "Hello from JAR!",
        "properties": "app.name=Test\napp.version=1.0\n"
    }
