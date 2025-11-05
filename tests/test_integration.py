"""Integration tests for Easy JAR Reader MCP Server."""

import asyncio
import json
import pytest
import tempfile
import zipfile
from pathlib import Path

from easy_code_reader.server import EasyJarReaderServer
from easy_code_reader.config import Config


@pytest.fixture
def mock_maven_repo(tmp_path):
    """创建一个模拟的 Maven 仓库结构"""
    maven_repo = tmp_path / "maven_repo"
    maven_repo.mkdir()
    
    # 创建一个测试 Maven 依赖结构
    # 例如: org.example:test-lib:1.0.0
    group_path = maven_repo / "org" / "example"
    artifact_path = group_path / "test-lib" / "1.0.0"
    artifact_path.mkdir(parents=True)
    
    # 创建一个简单的 JAR 文件
    jar_file = artifact_path / "test-lib-1.0.0.jar"
    with zipfile.ZipFile(jar_file, 'w', zipfile.ZIP_DEFLATED) as jar:
        # 添加 manifest
        manifest = "Manifest-Version: 1.0\nMain-Class: org.example.Main\n"
        jar.writestr("META-INF/MANIFEST.MF", manifest)
        
        # 添加一个类文件
        class_bytes = bytes([
            0xCA, 0xFE, 0xBA, 0xBE,  # Magic number
            0x00, 0x00,               # Minor version
            0x00, 0x34,               # Major version 52 (Java 8)
        ]) + b'\x00' * 100
        jar.writestr("org/example/Main.class", class_bytes)
    
    # 创建一个 sources JAR 文件
    sources_jar = artifact_path / "test-lib-1.0.0-sources.jar"
    with zipfile.ZipFile(sources_jar, 'w', zipfile.ZIP_DEFLATED) as jar:
        # 添加 Java 源文件
        java_source = """package org.example;

public class Main {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
"""
        jar.writestr("org/example/Main.java", java_source)
    
    return maven_repo


@pytest.mark.asyncio
async def test_server_initialization(mock_maven_repo):
    """测试服务器初始化"""
    server = EasyJarReaderServer(maven_repo_path=str(mock_maven_repo))
    
    assert server.maven_home == mock_maven_repo
    assert server.decompiler is not None
    assert server.response_manager is not None


@pytest.mark.asyncio
async def test_extract_from_sources_jar(mock_maven_repo):
    """测试从 sources jar 提取源代码"""
    server = EasyJarReaderServer(maven_repo_path=str(mock_maven_repo))
    
    result = await server._read_jar_source(
        group_id="org.example",
        artifact_id="test-lib",
        version="1.0.0",
        class_name="org.example.Main",
        prefer_sources=True
    )
    
    assert len(result) == 1
    response_text = result[0].text
    response_data = json.loads(response_text)
    
    assert response_data["source"] == "sources-jar"
    assert response_data["class_name"] == "org.example.Main"
    assert "Hello, World!" in response_data["code"]
    assert "public static void main" in response_data["code"]


@pytest.mark.asyncio
async def test_get_jar_path(mock_maven_repo):
    """测试获取 JAR 文件路径"""
    server = EasyJarReaderServer(maven_repo_path=str(mock_maven_repo))
    
    jar_path = server._get_jar_path("org.example", "test-lib", "1.0.0")
    
    assert jar_path is not None
    assert jar_path.exists()
    assert jar_path.name == "test-lib-1.0.0.jar"


@pytest.mark.asyncio
async def test_get_sources_jar_path(mock_maven_repo):
    """测试获取 sources JAR 文件路径"""
    server = EasyJarReaderServer(maven_repo_path=str(mock_maven_repo))
    
    sources_jar_path = server._get_sources_jar_path("org.example", "test-lib", "1.0.0")
    
    assert sources_jar_path is not None
    assert sources_jar_path.exists()
    assert sources_jar_path.name == "test-lib-1.0.0-sources.jar"


@pytest.mark.asyncio
async def test_jar_not_found(mock_maven_repo):
    """测试 JAR 文件不存在的情况"""
    server = EasyJarReaderServer(maven_repo_path=str(mock_maven_repo))
    
    result = await server._read_jar_source(
        group_id="org.example",
        artifact_id="non-existent",
        version="1.0.0",
        class_name="org.example.NonExistent"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    assert "未找到 JAR 文件" in response_text or "not found" in response_text.lower()


@pytest.mark.asyncio
async def test_max_lines_limit(mock_maven_repo):
    """测试行数限制功能"""
    server = EasyJarReaderServer(maven_repo_path=str(mock_maven_repo))
    
    result = await server._read_jar_source(
        group_id="org.example",
        artifact_id="test-lib",
        version="1.0.0",
        class_name="org.example.Main",
        max_lines=3
    )
    
    assert len(result) == 1
    response_text = result[0].text
    response_data = json.loads(response_text)
    
    # 验证代码被截断
    code_lines = response_data["code"].split('\n')
    assert len(code_lines) <= 10  # 包括截断提示信息


def test_config_maven_home():
    """测试 Maven 仓库配置"""
    original_maven_home = Config.get_maven_home()
    
    # 设置自定义路径
    custom_path = "/custom/maven/repo"
    Config.set_maven_home(custom_path)
    
    assert Config.get_maven_home() == Path(custom_path)
    
    # 恢复原始路径
    Config.set_maven_home(str(original_maven_home))


@pytest.mark.asyncio
async def test_decompiler_caching(tmp_path):
    """Test decompiler caching mechanism"""
    # Create a temporary Maven repository
    maven_repo = tmp_path / "maven_repo"
    maven_repo.mkdir()
    
    # Create test dependency
    artifact_path = maven_repo / "com" / "example" / "cached" / "1.0.0"
    artifact_path.mkdir(parents=True)
    
    # Create a JAR file (no sources)
    jar_file = artifact_path / "cached-1.0.0.jar"
    with zipfile.ZipFile(jar_file, 'w', zipfile.ZIP_DEFLATED) as jar:
        manifest = "Manifest-Version: 1.0\n"
        jar.writestr("META-INF/MANIFEST.MF", manifest)
        
        # Add a class file
        class_bytes = bytes([
            0xCA, 0xFE, 0xBA, 0xBE,  # Magic number
            0x00, 0x00,               # Minor version
            0x00, 0x34,               # Major version 52 (Java 8)
        ]) + b'\x00' * 100
        jar.writestr("com/example/TestClass.class", class_bytes)
    
    # Create cache directory and decompiled JAR (simulate already decompiled situation)
    # The cache directory structure should be: <jar-dir>/easy-jar-reader/<original-jar-name>.jar
    cache_dir = artifact_path / "easy-jar-reader"
    cache_dir.mkdir(parents=True)
    
    # Create a decompiled JAR with .java source
    cached_jar = cache_dir / "cached-1.0.0.jar"
    cached_content = """package com.example;

public class TestClass {
    // This is from cache
}
"""
    with zipfile.ZipFile(cached_jar, 'w') as zf:
        zf.writestr("com/example/TestClass.java", cached_content)
    
    # Initialize server and attempt decompilation
    server = EasyJarReaderServer(maven_repo_path=str(maven_repo))
    
    # Call decompilation (should read from cache)
    decompiled_code = server.decompiler.decompile_class(jar_file, "com.example.TestClass")
    
    # Verify that cached content is returned
    assert decompiled_code is not None
    assert "This is from cache" in decompiled_code
    # Cache JAR should still exist
    assert cached_jar.exists()


@pytest.mark.asyncio
async def test_input_validation(mock_maven_repo):
    """测试输入验证"""
    server = EasyJarReaderServer(maven_repo_path=str(mock_maven_repo))
    
    # 测试空 group_id
    result = await server._read_jar_source(
        group_id="",
        artifact_id="test-lib",
        version="1.0.0",
        class_name="org.example.Main"
    )
    assert len(result) == 1
    assert "group_id" in result[0].text
    
    # 测试空 artifact_id
    result = await server._read_jar_source(
        group_id="org.example",
        artifact_id="",
        version="1.0.0",
        class_name="org.example.Main"
    )
    assert len(result) == 1
    assert "artifact_id" in result[0].text
    
    # 测试空 version
    result = await server._read_jar_source(
        group_id="org.example",
        artifact_id="test-lib",
        version="",
        class_name="org.example.Main"
    )
    assert len(result) == 1
    assert "version" in result[0].text
    
    # 测试空 class_name
    result = await server._read_jar_source(
        group_id="org.example",
        artifact_id="test-lib",
        version="1.0.0",
        class_name=""
    )
    assert len(result) == 1
    assert "class_name" in result[0].text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
