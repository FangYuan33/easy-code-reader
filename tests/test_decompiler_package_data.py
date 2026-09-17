"""Tests for decompiler package data inclusion."""

import pytest
from pathlib import Path
from easy_code_reader.decompiler import JavaDecompiler


def test_decompiler_found_in_package():
    """Test that Fernflower JAR is found in the package directory.
    
    This test verifies the fix for the issue where the decompiler was not
    found when the package was installed from PyPI. The JAR file should now
    be included as package data in src/easy_code_reader/decompilers/
    """
    decompiler = JavaDecompiler()
    
    # Fernflower should be detected
    assert decompiler.fernflower_jar is not None, "Fernflower JAR should be detected"
    assert decompiler.fernflower_jar.exists(), "Fernflower JAR file should exist"
    
    # Compare path components so the check works with Windows separators too.
    jar_path = decompiler.fernflower_jar
    assert jar_path.parts[-2:] == ("decompilers", "fernflower.jar"), \
        f"JAR should be in decompilers directory, got: {jar_path}"
    
    # Verify the JAR is accessible
    assert decompiler.fernflower_jar.is_file(), "JAR should be a file"
    assert decompiler.fernflower_jar.stat().st_size > 0, "JAR should not be empty"


def test_package_data_location_priority():
    """Test that package data location has priority over project root.
    
    When installed from PyPI, only the package location will exist.
    In development, both locations exist, and package location should be preferred.
    """
    import importlib.util
    
    decompiler = JavaDecompiler()
    
    # Get the path to the decompiler module dynamically
    spec = importlib.util.find_spec('easy_code_reader.decompiler')
    if spec and spec.origin:
        # We can locate the module
        decompiler_module_path = Path(spec.origin)
        package_jar_path = decompiler_module_path.parent / "decompilers" / "fernflower.jar"
        
        if package_jar_path.exists():
            # Package location exists, it should be used
            assert package_jar_path.resolve() == decompiler.fernflower_jar.resolve(), \
                "Package location should be preferred when it exists"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
