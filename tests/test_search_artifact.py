"""Tests for search_artifact tool in Easy Code Reader MCP Server."""

import pytest
import json
import tempfile
import zipfile
from pathlib import Path
from easy_code_reader.server import EasyCodeReaderServer


@pytest.fixture
def temp_maven_repo():
    """创建临时 Maven 仓库用于测试"""
    with tempfile.TemporaryDirectory() as tmpdir:
        maven_repo = Path(tmpdir) / "repository"
        maven_repo.mkdir(parents=True, exist_ok=True)
        yield maven_repo


def create_test_artifact(maven_repo: Path, group_id: str, artifact_id: str, version: str):
    """
    在临时 Maven 仓库中创建测试 artifact
    
    参数:
        maven_repo: Maven 仓库根目录
        group_id: Maven group ID (如 org.springframework)
        artifact_id: Maven artifact ID (如 spring-core)
        version: Maven version (如 5.3.21)
    """
    # 构建目录结构
    group_path = group_id.replace('.', '/')
    artifact_dir = maven_repo / group_path / artifact_id / version
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建主 JAR 文件
    jar_path = artifact_dir / f"{artifact_id}-{version}.jar"
    with zipfile.ZipFile(jar_path, 'w', zipfile.ZIP_DEFLATED) as jar:
        # 添加 manifest
        manifest = "Manifest-Version: 1.0\n"
        jar.writestr("META-INF/MANIFEST.MF", manifest)
        
        # 添加一个测试类文件
        class_bytes = bytes([
            0xCA, 0xFE, 0xBA, 0xBE,  # Magic number
            0x00, 0x00,               # Minor version
            0x00, 0x34,               # Major version 52 (Java 8)
        ]) + b'\x00' * 100
        jar.writestr("com/example/Test.class", class_bytes)
    
    return jar_path


@pytest.mark.asyncio
async def test_search_artifact_basic(temp_maven_repo):
    """测试基础搜索功能：找到一个 artifact"""
    # 创建测试 artifact
    create_test_artifact(temp_maven_repo, "com.example", "test-artifact", "1.0.0")
    
    # 创建服务器实例
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 执行搜索
    result = await server._search_artifact("test-artifact")
    
    # 解析返回结果
    assert len(result) == 1
    json_result = json.loads(result[0].text)
    
    # 验证结果
    assert json_result["artifact_id"] == "test-artifact"
    assert json_result["total_matches"] == 1
    assert len(json_result["matches"]) == 1
    
    match = json_result["matches"][0]
    assert match["group_id"] == "com.example"
    assert match["artifact_id"] == "test-artifact"
    assert match["version"] == "1.0.0"
    assert match["coordinate"] == "com.example:test-artifact:1.0.0"
    assert match["jar_count"] == 1
    
    # 验证提示信息（唯一匹配）
    assert "✅ 找到唯一匹配" in json_result["hint"]
    assert "read_jar_source" in json_result["hint"]


@pytest.mark.asyncio
async def test_search_artifact_multiple_versions(temp_maven_repo):
    """测试搜索多个版本的同一 artifact"""
    # 创建多个版本
    create_test_artifact(temp_maven_repo, "com.example", "multi-version", "1.0.0")
    create_test_artifact(temp_maven_repo, "com.example", "multi-version", "1.1.0")
    create_test_artifact(temp_maven_repo, "com.example", "multi-version", "2.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("multi-version")
    
    json_result = json.loads(result[0].text)
    
    assert json_result["total_matches"] == 3
    assert len(json_result["matches"]) == 3
    
    # 验证版本排序（倒序）
    versions = [m["version"] for m in json_result["matches"]]
    assert versions == sorted(versions, reverse=True)
    
    # 验证提示信息（少量匹配）
    assert "3 个匹配" in json_result["hint"]


@pytest.mark.asyncio
async def test_search_artifact_with_version_pattern(temp_maven_repo):
    """测试使用版本模式过滤"""
    # 创建多个版本
    create_test_artifact(temp_maven_repo, "com.example", "version-filter", "1.0.0")
    create_test_artifact(temp_maven_repo, "com.example", "version-filter", "1.1.0")
    create_test_artifact(temp_maven_repo, "com.example", "version-filter", "2.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 搜索版本包含 "1." 的
    result = await server._search_artifact("version-filter", version_pattern="1.")
    json_result = json.loads(result[0].text)
    
    assert json_result["total_matches"] == 2
    versions = [m["version"] for m in json_result["matches"]]
    assert "1.0.0" in versions
    assert "1.1.0" in versions
    assert "2.0.0" not in versions


@pytest.mark.asyncio
async def test_search_artifact_with_group_id_hint(temp_maven_repo):
    """测试使用 group_id_hint 过滤"""
    # 创建不同 groupId 的 artifact
    create_test_artifact(temp_maven_repo, "com.example", "shared-name", "1.0.0")
    create_test_artifact(temp_maven_repo, "org.springframework", "shared-name", "1.0.0")
    create_test_artifact(temp_maven_repo, "io.netty", "shared-name", "1.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 只搜索 org.springframework 下的
    result = await server._search_artifact("shared-name", group_id_hint="springframework")
    json_result = json.loads(result[0].text)
    
    assert json_result["total_matches"] == 1
    assert json_result["matches"][0]["group_id"] == "org.springframework"


@pytest.mark.asyncio
async def test_search_artifact_not_found(temp_maven_repo):
    """测试搜索不存在的 artifact"""
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("nonexistent-artifact")
    
    json_result = json.loads(result[0].text)
    
    assert json_result["total_matches"] == 0
    assert len(json_result["matches"]) == 0
    
    # 验证错误提示
    assert "❌ 未找到" in json_result["hint"]
    assert "可能原因" in json_result["hint"]
    assert "建议操作" in json_result["hint"]


@pytest.mark.asyncio
async def test_search_artifact_empty_input(temp_maven_repo):
    """测试空输入验证"""
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 测试空字符串
    result = await server._search_artifact("")
    assert "错误: artifact_id 不能为空" in result[0].text
    
    # 测试只有空格
    result = await server._search_artifact("   ")
    assert "错误: artifact_id 不能为空" in result[0].text


@pytest.mark.asyncio
async def test_search_artifact_case_insensitive_filters(temp_maven_repo):
    """测试过滤器不区分大小写"""
    create_test_artifact(temp_maven_repo, "Com.Example", "test-case", "1.0.0-SNAPSHOT")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # group_id_hint 不区分大小写
    result = await server._search_artifact("test-case", group_id_hint="example")
    json_result = json.loads(result[0].text)
    assert json_result["total_matches"] == 1
    
    # version_pattern 不区分大小写
    result = await server._search_artifact("test-case", version_pattern="snapshot")
    json_result = json.loads(result[0].text)
    assert json_result["total_matches"] == 1


@pytest.mark.asyncio
async def test_search_artifact_combined_filters(temp_maven_repo):
    """测试组合使用多个过滤器"""
    # 创建多个测试 artifact
    create_test_artifact(temp_maven_repo, "com.example", "combined-test", "1.0.0")
    create_test_artifact(temp_maven_repo, "com.example", "combined-test", "1.1.0")
    create_test_artifact(temp_maven_repo, "com.other", "combined-test", "1.0.0")
    create_test_artifact(temp_maven_repo, "com.other", "combined-test", "2.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 同时使用 group_id_hint 和 version_pattern
    result = await server._search_artifact(
        "combined-test",
        group_id_hint="example",
        version_pattern="1."
    )
    json_result = json.loads(result[0].text)
    
    assert json_result["total_matches"] == 2
    for match in json_result["matches"]:
        assert "example" in match["group_id"]
        assert match["version"].startswith("1.")


@pytest.mark.asyncio
async def test_search_artifact_snapshot_versions(temp_maven_repo):
    """测试搜索 SNAPSHOT 版本"""
    # 创建 SNAPSHOT 版本
    create_test_artifact(temp_maven_repo, "com.example", "snapshot-test", "1.0.0-SNAPSHOT")
    create_test_artifact(temp_maven_repo, "com.example", "snapshot-test", "1.0.1-SNAPSHOT")
    create_test_artifact(temp_maven_repo, "com.example", "snapshot-test", "1.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 只搜索 SNAPSHOT 版本
    result = await server._search_artifact("snapshot-test", version_pattern="SNAPSHOT")
    json_result = json.loads(result[0].text)
    
    assert json_result["total_matches"] == 2
    for match in json_result["matches"]:
        assert "SNAPSHOT" in match["version"]


@pytest.mark.asyncio
async def test_search_artifact_jar_file_details(temp_maven_repo):
    """测试 JAR 文件详情返回"""
    create_test_artifact(temp_maven_repo, "com.example", "jar-details", "1.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("jar-details")
    
    json_result = json.loads(result[0].text)
    match = json_result["matches"][0]
    
    # 验证 JAR 文件详情
    assert "jar_files" in match
    assert len(match["jar_files"]) > 0
    
    jar_file = match["jar_files"][0]
    assert "name" in jar_file
    assert "size_mb" in jar_file
    assert jar_file["name"].endswith(".jar")
    assert isinstance(jar_file["size_mb"], (int, float))


@pytest.mark.asyncio
async def test_search_artifact_excludes_sources_javadoc(temp_maven_repo):
    """测试排除 sources 和 javadoc JAR"""
    # 创建 artifact 目录
    artifact_dir = temp_maven_repo / "com" / "example" / "exclude-test" / "1.0.0"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建多种 JAR 文件
    for jar_name in ["exclude-test-1.0.0.jar", 
                     "exclude-test-1.0.0-sources.jar",
                     "exclude-test-1.0.0-javadoc.jar"]:
        jar_path = artifact_dir / jar_name
        with zipfile.ZipFile(jar_path, 'w') as jar:
            jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("exclude-test")
    
    json_result = json.loads(result[0].text)
    match = json_result["matches"][0]
    
    # 应该只统计主 JAR，排除 sources 和 javadoc
    assert match["jar_count"] == 1
    assert match["jar_files"][0]["name"] == "exclude-test-1.0.0.jar"


@pytest.mark.asyncio
async def test_search_artifact_many_results_hint(temp_maven_repo):
    """测试大量结果时的提示信息"""
    # 创建超过 5 个匹配
    for i in range(10):
        create_test_artifact(temp_maven_repo, f"com.example{i}", "many-results", f"{i}.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("many-results")
    
    json_result = json.loads(result[0].text)
    
    assert json_result["total_matches"] == 10
    
    # 验证大量结果的提示信息
    assert "建议通过以下方式缩小范围" in json_result["hint"]
    assert "version_pattern" in json_result["hint"]
    assert "group_id_hint" in json_result["hint"]


@pytest.mark.asyncio
async def test_search_artifact_performance_metrics(temp_maven_repo):
    """测试性能指标返回"""
    create_test_artifact(temp_maven_repo, "com.example", "perf-test", "1.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("perf-test")
    
    json_result = json.loads(result[0].text)
    
    # 验证性能指标
    assert "searched_dirs" in json_result
    assert "elapsed_seconds" in json_result
    assert isinstance(json_result["searched_dirs"], int)
    assert isinstance(json_result["elapsed_seconds"], (int, float))
    assert json_result["searched_dirs"] > 0
    assert json_result["elapsed_seconds"] >= 0


@pytest.mark.asyncio
async def test_search_artifact_invalid_maven_repo():
    """测试 Maven 仓库不存在的情况"""
    # 使用不存在的路径
    server = EasyCodeReaderServer(maven_repo_path="/nonexistent/path/to/maven/repo")
    result = await server._search_artifact("test-artifact")
    
    # 应该返回错误信息
    assert "错误: Maven 仓库不存在" in result[0].text


@pytest.mark.asyncio
async def test_search_artifact_path_format(temp_maven_repo):
    """测试返回的路径格式正确"""
    create_test_artifact(temp_maven_repo, "com.example.test", "path-test", "1.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("path-test")
    
    json_result = json.loads(result[0].text)
    match = json_result["matches"][0]
    
    # 验证路径格式
    assert "path" in match
    path = Path(match["path"])
    assert path.name == "1.0.0"
    assert path.parent.name == "path-test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
