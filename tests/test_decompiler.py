"""Real decompiler, failure, cancellation and cache-reuse integration tests."""

import asyncio
import dataclasses
import os
import subprocess
import sys
import zipfile

import pytest

from easy_code_reader.decompiler import JavaDecompiler
from easy_code_reader.errors import ReaderError


async def test_real_decompilation_and_inner_class_cache(reader_config, real_jar, monkeypatch):
    decompiler = JavaDecompiler(reader_config)
    first = await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert first.source_type == "decompiled"
    assert "return 42" in first.code
    assert "ArrayList<String>" in first.code
    assert "hello" in first.code
    calls = []
    original = decompiler._run_process
    async def observe(command, **kwargs):
        calls.append(command)
        return await original(command, **kwargs)
    monkeypatch.setattr(decompiler, "_run_process", observe)
    inner = await decompiler.decompile_class(real_jar, "org.example.Outer$Inner")
    assert inner.source_type == "decompiled_cache"
    assert inner.source_file == "org/example/Outer.java"
    assert '"inner"' in inner.code
    assert calls == []  # Cache hits do not even start java -version.


async def test_missing_class_does_not_start_java(reader_config, real_jar, monkeypatch):
    decompiler = JavaDecompiler(reader_config)
    async def never(*args, **kwargs):
        pytest.fail("Missing class must not start Java")
    monkeypatch.setattr(decompiler, "_run_process", never)
    with pytest.raises(ReaderError) as error:
        await decompiler.decompile_class(real_jar, "org.example.Ghost")
    assert error.value.code == "CLASS_NOT_FOUND"
    assert not list(decompiler._cache_for(real_jar).root.glob("work-*"))


async def test_missing_decompilers_is_explicit(reader_config, real_jar):
    decompiler = JavaDecompiler(reader_config)
    decompiler.cfr_jar = decompiler.fernflower_jar = None
    with pytest.raises(ReaderError) as error:
        await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert error.value.code == "DECOMPILER_UNAVAILABLE"


async def test_compatible_fallback(reader_config, real_jar, monkeypatch):
    decompiler = JavaDecompiler(reader_config)
    async def detect():
        return 21
    attempts = []
    async def run(command, **kwargs):
        attempts.append(command)
        if "--outputdir" not in command:
            return 1, "", "forced fernflower error"
        output = command[-1] / "org/example"
        output.mkdir(parents=True)
        (output / "Outer.java").write_text("public class Outer { int value() { return 42; } }")
        return 0, "", ""
    monkeypatch.setattr(decompiler, "_detect_java_version", detect)
    monkeypatch.setattr(decompiler, "_run_process", run)
    result = await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert result.source_type == "decompiled"
    assert len(attempts) == 2


async def test_failure_never_returns_placeholder(reader_config, real_jar, monkeypatch):
    decompiler = JavaDecompiler(reader_config)
    async def run(command, **kwargs):
        if "-version" in command:
            return 0, "", 'openjdk version "11.0.1"'
        return 1, "", "bad bytecode"
    monkeypatch.setattr(decompiler, "_run_process", run)
    with pytest.raises(ReaderError) as error:
        await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert error.value.code == "DECOMPILE_FAILED"


@pytest.mark.parametrize("cancel", [False, True])
async def test_timeout_and_cancel_reap_real_child(reader_config, real_jar, monkeypatch, cancel):
    config = dataclasses.replace(reader_config, decompile_timeout=5 if cancel else 0.5)
    decompiler = JavaDecompiler(config)
    started = asyncio.Event()
    child_pid = []
    original = decompiler._run_process
    pid_file = real_jar.parent / "child.pid"
    async def run(command, **kwargs):
        if "-version" in command:
            return 0, "", 'openjdk version "11.0.1"'
        task = asyncio.create_task(original([sys.executable, "-c",
            "import os,time,pathlib; pathlib.Path(" + repr(str(pid_file)) + ").write_text(str(os.getpid())); time.sleep(60)"]))
        try:
            while not pid_file.exists():
                await asyncio.sleep(0.01)
            child_pid.append(int(pid_file.read_text()))
            started.set()
            return await task
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    monkeypatch.setattr(decompiler, "_run_process", run)
    task = asyncio.create_task(decompiler.decompile_class(real_jar, "org.example.Outer"))
    await asyncio.wait_for(started.wait(), 3)
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(ReaderError) as error:
            await task
        assert error.value.code == "DECOMPILE_TIMEOUT"
    assert not list(decompiler._cache_for(real_jar).root.glob("work-*"))
    if os.name == "posix":
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid[0], 0)


async def test_long_decompile_does_not_block_event_loop(reader_config, real_jar, monkeypatch):
    decompiler = JavaDecompiler(reader_config)
    started, finish = asyncio.Event(), asyncio.Event()
    async def run(command, **kwargs):
        if "-version" in command:
            return 0, "", 'openjdk version "11.0.1"'
        started.set()
        await finish.wait()
        return 1, "", "done"
    monkeypatch.setattr(decompiler, "_run_process", run)
    task = asyncio.create_task(decompiler.decompile_class(real_jar, "org.example.Outer"))
    await asyncio.wait_for(started.wait(), 3)
    await asyncio.wait_for(asyncio.sleep(0.01), 0.2)
    finish.set()
    with pytest.raises(ReaderError):
        await task


async def test_invalid_fernflower_output_falls_back(reader_config, real_jar, monkeypatch):
    decompiler = JavaDecompiler(reader_config)
    async def detect():
        return 21
    async def run(command, **kwargs):
        if "--outputdir" not in command:
            (command[-1] / real_jar.name).write_bytes(b"not a zip")
        else:
            output = command[-1] / "org/example"
            output.mkdir(parents=True)
            (output / "Outer.java").write_text("public class Outer { int value() { return 42; } }")
        return 0, "", ""
    monkeypatch.setattr(decompiler, "_detect_java_version", detect)
    monkeypatch.setattr(decompiler, "_run_process", run)
    result = await decompiler.decompile_class(real_jar, "org.example.Outer")
    assert result.source_type == "decompiled"
    assert "return 42" in result.code


async def test_four_requests_start_without_waiting(reader_config, real_jar, monkeypatch):
    decompiler = JavaDecompiler(reader_config)
    all_started, finish = asyncio.Event(), asyncio.Event()
    started = 0
    async def run(command, **kwargs):
        nonlocal started
        if "-version" in command:
            return 0, "", 'openjdk version "11.0.1"'
        started += 1
        if started == 4:
            all_started.set()
        await finish.wait()
        return 1, "", "controlled completion"
    monkeypatch.setattr(decompiler, "_run_process", run)
    tasks = [asyncio.create_task(decompiler.decompile_class(real_jar, "org.example.Outer"))
             for _ in range(4)]
    try:
        await asyncio.wait_for(all_started.wait(), 3)
        assert all(not task.done() for task in tasks)
    finally:
        finish.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(result, ReaderError) and result.code == "DECOMPILE_FAILED" for result in results)
    assert not list(decompiler._cache_for(real_jar).root.glob("work-*"))


@pytest.mark.parametrize("engine", ["cfr", "fernflower"])
@pytest.mark.parametrize("relative_path", [False, True])
async def test_decompilers_read_original_jar(reader_config, real_jar, tmp_path, monkeypatch, engine, relative_path):
    from pathlib import Path
    decompiler = JavaDecompiler(reader_config)
    original_bytes = real_jar.read_bytes()
    async def detect():
        return 21 if engine == "fernflower" else 11
    async def run(command, **kwargs):
        assert command[3] == real_jar.resolve()
        assert not list(Path(kwargs["cwd"]).rglob("*.jar"))
        code = "package org.example; public class Outer { public int value() { return 42; } }"
        if engine == "cfr":
            assert "--outputdir" in command
            output = command[-1] / "org/example"
            output.mkdir(parents=True)
            (output / "Outer.java").write_text(code)
        else:
            assert "--outputdir" not in command
            with zipfile.ZipFile(command[-1] / real_jar.name, "w") as archive:
                archive.writestr("org/example/Outer.java", code)
        return 0, "", ""
    monkeypatch.setattr(decompiler, "_detect_java_version", detect)
    monkeypatch.setattr(decompiler, "_run_process", run)
    monkeypatch.chdir(tmp_path)
    input_path = real_jar.relative_to(tmp_path) if relative_path else real_jar
    result = await decompiler.decompile_class(input_path, "org.example.Outer")
    assert "return 42" in result.code
    assert real_jar.read_bytes() == original_bytes
    assert (real_jar.parent / "easy-code-reader" / real_jar.name).exists()
    assert not list(decompiler._cache_for(real_jar).root.glob("work-*"))
