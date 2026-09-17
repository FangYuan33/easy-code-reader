#!/usr/bin/env python3
"""Verify an installed wheel over real MCP stdio; run from any working directory."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "Demo.java"
        source.write_text('package smoke;\npublic class Demo { public int value() { return 42; } }\n', encoding="utf-8")
        subprocess.run(["javac", "--release", "8", "-d", str(root), str(source)], check=True, capture_output=True)
        repo = root / "repo"
        directory = repo / "smoke/demo/1.0"
        directory.mkdir(parents=True)
        with zipfile.ZipFile(directory / "demo-1.0.jar", "w") as jar:
            jar.write(root / "smoke/Demo.class", "smoke/Demo.class")
        with zipfile.ZipFile(directory / "demo-1.0-sources.jar", "w") as jar:
            jar.writestr("smoke/Demo.java", source.read_text(encoding="utf-8"))
        server = StdioServerParameters(command=sys.executable, args=["-m", "easy_code_reader",
            "--maven-repo", str(repo)], env=dict(os.environ))
        timings = {}
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                assert {tool.name for tool in (await client.list_tools()).tools} == {"read_jar_source", "search_group_id"}
                for label in ("cold_search", "repeat_search"):
                    start = time.perf_counter()
                    result = await client.call_tool("search_group_id", {"artifact_id": "demo", "group_prefix": "smoke"})
                    assert not result.isError
                    assert json.loads(result.content[0].text)["total_matches"] == 1
                    timings[label] = time.perf_counter() - start
                arguments = {"group_id": "smoke", "artifact_id": "demo", "version": "1.0", "class_name": "smoke.Demo"}
                result = await client.call_tool("read_jar_source", arguments)
                assert not result.isError
                payload = json.loads(result.content[0].text)
                assert payload["code"] == source.read_text(encoding="utf-8")
                assert set(payload) == {"class_name", "artifact", "source_type", "code"}
                assert not (directory / "easy-code-reader").exists()
                partial = await client.call_tool("read_jar_source", {**arguments, "start_line": 2, "end_line": 2})
                assert json.loads(partial.content[0].text)["is_partial"]
                for label, expected in (("cold_decompile", "decompiled"), ("cached_read", "decompiled_cache")):
                    start = time.perf_counter()
                    result = await client.call_tool("read_jar_source", {**arguments, "prefer_sources": False})
                    timings[label] = time.perf_counter() - start
                    assert not result.isError, result
                    payload = json.loads(result.content[0].text)
                    assert payload["source_type"] == expected
                    assert "return 42" in payload["code"]
                    timings[label + "_response_bytes"] = len(result.content[0].text.encode())
                error = await client.call_tool("read_jar_source", {**arguments, "artifact_id": "missing"})
                assert error.isError
                assert json.loads(error.content[0].text)["error"]["code"] == "ARTIFACT_NOT_FOUND"
                resources = await client.list_resources()
                await client.read_resource(resources.resources[0].uri)
        assert (directory / "easy-code-reader/demo-1.0.jar").is_file()
        assert not list((directory / "easy-code-reader").glob("*.lock"))
        print(json.dumps({"smoke": "passed", "measurements": timings}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
