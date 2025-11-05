"""Tests for decompiler package data inclusion."""

import pytest
from pathlib import Path
from easy_jar_reader.decompiler import JavaDecompiler


def test_decompiler_found_in_package():
    """Test that Fernflower JAR is found in the package directory.
    
    This test verifies the fix for the issue where the decompiler was not
    found when the package was installed from PyPI. The JAR file should now
    be included as package data in src/easy_jar_reader/decompilers/
    """
    decompiler = JavaDecompiler()
    
    # Fernflower should be detected
    assert decompiler.fernflower_jar is not None, "Fernflower JAR should be detected"
    assert decompiler.fernflower_jar.exists(), "Fernflower JAR file should exist"
    
    # The JAR should be in the package directory (for PyPI distribution)
    # or in the project root (for development)
    jar_path_str = str(decompiler.fernflower_jar)
    assert 'decompilers/fernflower.jar' in jar_path_str, \
        f"JAR should be in decompilers directory, got: {jar_path_str}"
    
    # Verify the JAR is accessible
    assert decompiler.fernflower_jar.is_file(), "JAR should be a file"
    assert decompiler.fernflower_jar.stat().st_size > 0, "JAR should not be empty"


def test_package_data_location_priority():
    """Test that package data location has priority over project root.
    
    When installed from PyPI, only the package location will exist.
    In development, both locations exist, and package location should be preferred.
    """
    decompiler = JavaDecompiler()
    
    # Get the path to the decompiler module
    decompiler_module_path = Path(__file__).parent.parent / "src" / "easy_jar_reader" / "decompiler.py"
    if decompiler_module_path.exists():
        # We're in development mode
        package_jar_path = decompiler_module_path.parent / "decompilers" / "fernflower.jar"
        
        if package_jar_path.exists():
            # Package location exists, it should be used
            assert str(package_jar_path) in str(decompiler.fernflower_jar), \
                "Package location should be preferred when it exists"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
