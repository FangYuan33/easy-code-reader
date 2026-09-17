"""Source service and MCP contract integration tests."""

import asyncio
import json

import pytest
from mcp import types

from easy_code_reader.errors import ReaderError
from easy_code_reader.server import EasyCodeReaderServer
from easy_code_reader.source import JavaSource


@pytest.fixture
def server(reader_config):
    return EasyCodeReaderServer(config=reader_config)


async def call(server, name="read_jar_source", **arguments):
    request = types.CallToolRequest(method="tools/call", params=types.CallToolRequestParams(name=name, arguments=arguments))
    result = await server.server.request_handlers[types.CallToolRequest](request)
    return result.root


async def test_sources_full_text_has_minimal_fields(server, real_jar, jar_factory):
    text = "package org.example;\r\npublic class Outer {\r\n  int value() { return 42; }\r\n}\r\n"
    sources = jar_factory(real_jar.with_name("demo-1.0-sources.jar"), {"org/example/Outer.java": text})
    result = await call(server, group_id="org.example", artifact_id="demo", version="1.0", class_name="org.example.Outer")
    assert not result.isError
    payload = json.loads(result.content[0].text)
    assert payload["code"] == text
    assert payload["source_type"] == "sources.jar"
    assert set(payload) == {"class_name", "artifact", "source_type", "code"}


@pytest.mark.parametrize("start,end,expected", [(2, 3, "two\nthree\n"), (2, None, "two\nthree\nfour\n"),
                                               (None, 2, "one\ntwo\n"), (3, 99, "three\nfour\n")])
async def test_line_ranges(server, real_jar, jar_factory, start, end, expected):
    jar_factory(real_jar.with_name("demo-1.0-sources.jar"), {"org/example/Outer.java": "one\ntwo\nthree\nfour\n"})
    result = await server._read_jar_source("org.example", "demo", "1.0", "org.example.Outer", start_line=start, end_line=end)
    payload = json.loads(result[0].text)
    assert payload["code"] == expected
    assert payload["total_lines"] == 4
    assert payload["is_partial"]


@pytest.mark.parametrize("start,end", [(0, None), (2, 1), (True, None), (1.5, None), (99, None)])
async def test_bad_ranges_are_errors(server, real_jar, jar_factory, start, end):
    jar_factory(real_jar.with_name("demo-1.0-sources.jar"), {"org/example/Outer.java": "one\ntwo\n"})
    result = await call(server, group_id="org.example", artifact_id="demo", version="1.0",
                        class_name="org.example.Outer", start_line=start,
                        **({"end_line": end} if end is not None else {}))
    assert result.isError


async def test_missing_jar_is_mcp_error(server):
    result = await call(server, group_id="org.example", artifact_id="missing", version="1.0", class_name="org.example.Outer")
    assert result.isError
    assert json.loads(result.content[0].text)["error"]["code"] == "ARTIFACT_NOT_FOUND"


async def test_internal_class_uses_outer_source(server, real_jar, jar_factory):
    jar_factory(real_jar.with_name("demo-1.0-sources.jar"), {"org/example/Outer.java": "public class Outer { class Inner {} }"})
    result = await server._read_jar_source("org.example", "demo", "1.0", "org.example.Outer$Inner")
    payload = json.loads(result[0].text)
    assert payload["class_name"] == "org.example.Outer$Inner"
    assert "Outer.java" in payload["warnings"][0]
    assert "source_file" not in payload
    with pytest.raises(ReaderError) as error:
        await server._read_jar_source("org.example", "demo", "1.0", "org.example.Outer$Ghost")
    assert error.value.code == "CLASS_NOT_FOUND"


async def test_decode_failure_uses_selected_binary(server, real_jar, jar_factory, monkeypatch):
    jar_factory(real_jar.with_name("demo-1.0-sources.jar"), {"org/example/Outer.java": b"\xff"})
    async def decompile(path, name, cache_jar_name=None):
        assert path == real_jar
        return JavaSource("actual", "org/example/Outer.java", "decompiled")
    monkeypatch.setattr(server.decompiler, "decompile_class", decompile)
    payload = json.loads((await server._read_jar_source("org.example", "demo", "1.0", "org.example.Outer"))[0].text)
    assert payload["source_type"] == "decompiled"
    assert payload["warnings"]


async def test_source_only_decode_failure_is_error(server, reader_config, jar_factory):
    jar_factory(reader_config.maven_repo / "org/example/demo/1.0/demo-1.0-sources.jar", {"org/example/Outer.java": b"\xff"})
    with pytest.raises(ReaderError) as error:
        await server._read_jar_source("org.example", "demo", "1.0", "org.example.Outer")
    assert error.value.code == "SOURCE_DECODE_ERROR"


async def test_normalized_input_uses_timestamp_cache_name(server, reader_config, compiled_classes, jar_factory, monkeypatch):
    directory = reader_config.maven_repo / "org/example/demo/1.0-SNAPSHOT"
    timestamp = jar_factory(directory / "demo-1.0-20260915.120000-2.jar", compiled_classes)
    ordinary = jar_factory(directory / "demo-1.0-SNAPSHOT.jar", compiled_classes)
    async def decompile(path, name, cache_jar_name=None):
        assert path == ordinary
        assert cache_jar_name == timestamp.name
        return JavaSource("actual", "org/example/Outer.java", "decompiled")
    monkeypatch.setattr(server.decompiler, "decompile_class", decompile)
    payload = json.loads((await server._read_jar_source("org.example", "demo", "1.0-SNAPSHOT", "org.example.Outer", prefer_sources=False))[0].text)
    assert payload["code"] == "actual"
    assert set(payload) == {"class_name", "artifact", "source_type", "code"}


async def test_exactly_two_tools_and_guide(server):
    result = await server.server.request_handlers[types.ListToolsRequest](types.ListToolsRequest(method="tools/list"))
    assert {tool.name for tool in result.root.tools} == {"read_jar_source", "search_group_id"}
    tools = {tool.name: tool for tool in result.root.tools}
    assert "start_line" in tools["read_jar_source"].inputSchema["properties"]
    assert "refresh" not in tools["search_group_id"].inputSchema["properties"]
    assert "MAVEN_HOME/M2_HOME" in server._get_guide_content()


async def test_unknown_tool_and_extra_arguments(server):
    assert (await call(server, name="unknown")).isError
    assert (await call(server, name="search_group_id", artifact_id="demo", unexpected=1)).isError


async def test_schema_error_has_stable_error_code(server):
    result = await call(server, name="search_group_id", artifact_id=123)
    assert result.isError
    assert json.loads(result.content[0].text)["error"]["code"] == "INVALID_ARGUMENT"


async def test_mcp_waits_for_decompilation_result(server, real_jar, monkeypatch):
    started, finish = asyncio.Event(), asyncio.Event()
    async def decompile(path, name, cache_jar_name=None):
        started.set()
        await finish.wait()
        return JavaSource("completed source", "org/example/Outer.java", "decompiled")
    monkeypatch.setattr(server.decompiler, "decompile_class", decompile)
    task = asyncio.create_task(call(server, group_id="org.example", artifact_id="demo", version="1.0",
                                    class_name="org.example.Outer", prefer_sources=False))
    try:
        await asyncio.wait_for(started.wait(), 3)
        assert not task.done()
    finally:
        finish.set()
    result = await task
    assert not result.isError
    assert json.loads(result.content[0].text)["code"] == "completed source"


async def test_snapshot_cache_uses_timestamp_label_and_actual_input_stats(server, reader_config, compiled_classes, jar_factory, monkeypatch):
    import os
    import zipfile
    directory = reader_config.maven_repo / "org/example/demo/1.0-SNAPSHOT"
    timestamp = jar_factory(directory / "demo-1.0-20260915.120000-9.jar", compiled_classes)
    ordinary = jar_factory(directory / "demo-1.0-SNAPSHOT.jar", compiled_classes)
    inputs = []
    original_run = server.decompiler._run_process
    async def observe(command, **kwargs):
        if "-jar" in command:
            inputs.append(command[3])
        return await original_run(command, **kwargs)
    monkeypatch.setattr(server.decompiler, "_run_process", observe)
    async def read():
        response = await server._read_jar_source("org.example", "demo", "1.0-SNAPSHOT", "org.example.Outer", prefer_sources=False)
        return json.loads(response[0].text)
    assert (await read())["source_type"] == "decompiled"
    cache_path = directory / "easy-code-reader" / timestamp.name
    assert cache_path.exists()
    assert not (cache_path.parent / ordinary.name).exists()
    assert inputs == [ordinary.resolve()]
    assert (await read())["source_type"] == "decompiled_cache"
    assert len(inputs) == 1
    before = ordinary.stat()
    os.utime(ordinary, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
    assert (await read())["source_type"] == "decompiled"
    with zipfile.ZipFile(cache_path) as archive:
        metadata = json.loads(archive.read("META-INF/easy-code-reader.json"))
    assert metadata["source_mtime_ns"] == ordinary.stat().st_mtime_ns
    assert metadata["source_size"] == ordinary.stat().st_size
    newer = jar_factory(directory / "demo-1.0-20260915.120000-10.jar", compiled_classes)
    assert (await read())["source_type"] == "decompiled"
    assert (cache_path.parent / newer.name).exists()
    assert inputs == [ordinary.resolve()] * 3


async def test_read_normalized_sources_before_timestamp_sources(server, reader_config, compiled_classes, jar_factory):
    directory = reader_config.maven_repo / "org/example/demo/1.0-SNAPSHOT"
    jar_factory(directory / "demo-1.0-20260915.120000-2.jar", compiled_classes)
    jar_factory(directory / "demo-1.0-SNAPSHOT.jar", compiled_classes)
    jar_factory(directory / "demo-1.0-20260915.120000-2-sources.jar", {"org/example/Outer.java": "timestamp sources"})
    jar_factory(directory / "demo-1.0-SNAPSHOT-sources.jar", {"org/example/Outer.java": "normalized sources"})
    response = await server._read_jar_source("org.example", "demo", "1.0-SNAPSHOT", "org.example.Outer")
    result = json.loads(response[0].text)
    assert result["code"] == "normalized sources"
    assert result["source_type"] == "sources.jar"
    assert not (directory / "easy-code-reader").exists()
