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


@pytest.fixture(scope="session")
def compiled_classes(tmp_path_factory):
    """Use real Java bytecode for decompiler assertions, compiled once per session."""
    import shutil
    import subprocess
    if not shutil.which("javac"):
        pytest.skip("A JDK is required for real decompiler tests")
    root = tmp_path_factory.mktemp("javac")
    source = root / "Outer.java"
    source.write_text('''package org.example;
import java.util.function.Supplier;
public class Outer extends java.util.ArrayList<String> {
    public int value() { return 42; }
    public String greeting() { Supplier<String> s = () -> "hello"; return s.get(); }
    public static class Inner { public String message() { return "inner"; } }
}
''', encoding="utf-8")
    subprocess.run(["javac", "--release", "8", "-d", str(root), str(source)], check=True, capture_output=True)
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*.class")}


@pytest.fixture
def jar_factory():
    import zipfile
    def create(path, entries=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, value in (entries or {"META-INF/MANIFEST.MF": "Manifest-Version: 1.0\n"}).items():
                archive.writestr(name, value)
        return path
    return create


@pytest.fixture
def real_jar(tmp_path, compiled_classes, jar_factory):
    return jar_factory(tmp_path / "repo/org/example/demo/1.0/demo-1.0.jar", compiled_classes)


@pytest.fixture
def reader_config(tmp_path):
    from easy_code_reader.config import Config
    return Config(maven_repo=tmp_path / "repo")
