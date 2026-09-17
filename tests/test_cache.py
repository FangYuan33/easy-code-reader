"""Cache contents must match the selected input, never old workspaces."""

import asyncio
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

from easy_code_reader.cache import SourceCache, _FORMAT
from easy_code_reader.decompiler import JavaDecompiler
from easy_code_reader.errors import ReaderError


async def test_same_size_jar_with_new_mtime_invalidates_cache(reader_config, real_jar, jar_factory):
    decompiler = JavaDecompiler(reader_config)
    first = await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert "return 42" in first.code
    with zipfile.ZipFile(real_jar) as jar:
        entries = {entry.filename: jar.read(entry) for entry in jar.infolist()}
    # javac uses bipush 42 for this method; changing it to 43 preserves class length.
    bytecode = entries["org/example/Outer.class"]
    assert b"\x10\x2a\xac" in bytecode
    entries["org/example/Outer.class"] = bytecode.replace(b"\x10\x2a\xac", b"\x10\x2b\xac")
    # ZIP_STORED makes equal bytecode lengths result in equal archive lengths.
    def rewrite(values):
        with zipfile.ZipFile(real_jar, "w", compression=zipfile.ZIP_STORED) as jar:
            for name, value in values.items():
                jar.writestr(name, value)
    original = dict(entries)
    original["org/example/Outer.class"] = bytecode
    rewrite(original)
    await decompiler.decompile_class(real_jar, "org.example.Outer")
    before = real_jar.stat()
    rewrite(entries)
    os.utime(real_jar, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
    assert real_jar.stat().st_size == before.st_size
    updated = await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert updated.source_type == "decompiled"
    assert "return 43" in updated.code


async def test_corrupt_cache_regenerated(reader_config, real_jar):
    decompiler = JavaDecompiler(reader_config)
    await decompiler.decompile_class(real_jar, "org.example.Outer")
    cache = next(decompiler._cache_for(real_jar).root.glob("*.jar"))
    cache.write_bytes(b"broken")
    result = await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert result.source_type == "decompiled"
    assert "return 42" in result.code


async def test_legacy_cache_and_temp_cannot_supply_source(reader_config, real_jar, jar_factory):
    legacy = jar_factory(real_jar.parent / "easy-code-reader/demo-1.0.jar",
                         {"org/example/Outer.java": "WRONG_OLD_CACHE"})
    ghost = real_jar.parent / "easy-code-reader/cfr_temp/org/example/Ghost.java"
    ghost.parent.mkdir(parents=True)
    ghost.write_text("STALE_GHOST")
    decompiler = JavaDecompiler(reader_config)
    result = await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert "WRONG" not in result.code
    with pytest.raises(ReaderError) as error:
        await decompiler.decompile_class(real_jar, "org.example.Ghost")
    assert error.value.code == "CLASS_NOT_FOUND"
    assert legacy.exists() and ghost.exists()  # Existing user caches are not deleted.
    assert not list(decompiler._cache_for(real_jar).root.glob("work-*"))


async def test_two_processes_publish_complete_archives(reader_config, real_jar):
    script = '''import asyncio,json,sys
from pathlib import Path
from easy_code_reader.config import Config
from easy_code_reader.decompiler import JavaDecompiler
async def main():
    d=JavaDecompiler(Config(Path(sys.argv[1])))
    r=await d.decompile_class(Path(sys.argv[2]),"org.example.Outer")
    print(json.dumps({"type":r.source_type,"valid":"return 42" in r.code}))
asyncio.run(main())
'''
    processes = [await asyncio.create_subprocess_exec(
        sys.executable, "-c", script, str(reader_config.maven_repo), str(real_jar),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE) for _ in range(2)]
    replies = await asyncio.gather(*(process.communicate() for process in processes))
    results = []
    for process, (stdout, stderr) in zip(processes, replies):
        assert process.returncode == 0, stderr.decode()
        results.append(json.loads(stdout))
    assert all(result["type"] in {"decompiled", "decompiled_cache"} for result in results)
    cache_path = real_jar.parent / "easy-code-reader" / real_jar.name
    with zipfile.ZipFile(cache_path) as archive:
        assert archive.testzip() is None
        assert b"return 42" in archive.read("org/example/Outer.java")
    assert not list(cache_path.parent.glob("*.lock"))
    assert all(result["valid"] for result in results)


def test_lru_pruning_preserves_current_and_legacy_files(tmp_path, jar_factory):
    cache = SourceCache(tmp_path)
    cache.prepare()
    sizes = []
    for index, name in enumerate(("old", "recent", "current")):
        path = jar_factory(cache.root / f"{name}.jar", {
            "META-INF/easy-code-reader.json": json.dumps({"format": _FORMAT}),
            "Example.java": "public class Example {}",
        })
        os.utime(path, (index + 1, index + 1))
        sizes.append(path.stat().st_size)
    legacy = jar_factory(cache.root / "legacy.jar", {"Example.java": "legacy"})
    cache.budget = sum(sizes[1:])
    cache.prune("current.jar")
    assert not (cache.root / "old.jar").exists()
    assert (cache.root / "recent.jar").exists()
    assert (cache.root / "current.jar").exists()
    assert legacy.exists()


async def test_unwritable_maven_cache_is_reported(reader_config, real_jar, monkeypatch):
    def blocked(cache):
        assert cache.root == real_jar.parent / "easy-code-reader"
        raise PermissionError("read-only Maven directory")
    monkeypatch.setattr(SourceCache, "prepare", blocked)
    with pytest.raises(ReaderError) as error:
        await JavaDecompiler(reader_config).decompile_class(real_jar, "org.example.Outer")
    assert error.value.code == "CACHE_UNAVAILABLE"
    assert "Maven 版本目录" in error.value.hint


async def test_cache_is_beside_original_jar(reader_config, real_jar):
    decompiler = JavaDecompiler(reader_config)
    result = await decompiler.decompile_class(real_jar, "org.example.Outer")
    cache_root = real_jar.parent / "easy-code-reader"
    assert result.source_type == "decompiled"
    assert (cache_root / real_jar.name).is_file()
    assert not list(cache_root.glob("*.lock"))
    assert not list(cache_root.glob("work-*"))
    cached = await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert cached.source_type == "decompiled_cache"


async def test_concurrent_versions_keep_separate_caches(reader_config, real_jar, jar_factory, compiled_classes):
    second = jar_factory(real_jar.parent.parent / "2.0/demo-2.0.jar", compiled_classes)
    decompiler = JavaDecompiler(reader_config)
    results = await asyncio.gather(*(decompiler.decompile_class(path, "org.example.Outer")
                                     for path in (real_jar, second)))
    assert all(result.source_type == "decompiled" for result in results)
    for path in (real_jar, second):
        assert list((path.parent / "easy-code-reader").glob("*.jar"))
        assert not list((path.parent / "easy-code-reader").glob("work-*"))


async def test_timestamp_jars_have_separate_named_caches(reader_config, jar_factory, compiled_classes):
    directory = reader_config.maven_repo / "org/example/demo/1.0-SNAPSHOT"
    first = jar_factory(directory / "demo-1.0-20260915.120000-9.jar", compiled_classes)
    second = jar_factory(directory / "demo-1.0-20260915.120000-10.jar", compiled_classes)
    decompiler = JavaDecompiler(reader_config)
    for jar in (first, second):
        await decompiler.decompile_class(jar, "org.example.Outer")
        assert (directory / "easy-code-reader" / jar.name).exists()
    assert (await decompiler.decompile_class(second, "org.example.Outer")).source_type == "decompiled_cache"


async def test_cache_hit_does_not_create_workspace(reader_config, real_jar, monkeypatch):
    import easy_code_reader.decompiler as module
    decompiler = JavaDecompiler(reader_config)
    await decompiler.decompile_class(real_jar, "org.example.Outer")
    def never(*args, **kwargs):
        pytest.fail("A cache hit must not create a workspace")
    monkeypatch.setattr(module, "temporary_directory", never)
    result = await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert result.source_type == "decompiled_cache"


async def test_input_updated_during_decompilation_is_not_published(reader_config, real_jar, monkeypatch):
    decompiler = JavaDecompiler(reader_config)
    async def run(command, **kwargs):
        if "-version" in command:
            return 0, "", 'openjdk version "11.0.1"'
        before = real_jar.stat()
        os.utime(real_jar, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
        output = command[-1] / "org/example"
        output.mkdir(parents=True)
        (output / "Outer.java").write_text("public class Outer {}")
        return 0, "", ""
    monkeypatch.setattr(decompiler, "_run_process", run)
    with pytest.raises(ReaderError) as error:
        await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert error.value.code == "INPUT_CHANGED"
    assert not (real_jar.parent / "easy-code-reader" / real_jar.name).exists()


async def test_cache_before_generic_signature_fix_is_regenerated(reader_config, real_jar, jar_factory):
    stat = real_jar.stat()
    cache_path = real_jar.parent / "easy-code-reader" / real_jar.name
    jar_factory(cache_path, {
        "META-INF/easy-code-reader.json": json.dumps({
            "format": 2, "source_size": stat.st_size, "source_mtime_ns": stat.st_mtime_ns,
        }),
        "org/example/Outer.java": "public class Outer extends java.util.ArrayList {}",
    })
    result = await JavaDecompiler(reader_config).decompile_class(real_jar, "org.example.Outer")
    assert result.source_type == "decompiled"
    assert "ArrayList<String>" in result.code
    with zipfile.ZipFile(cache_path) as archive:
        assert json.loads(archive.read("META-INF/easy-code-reader.json"))["format"] == _FORMAT
