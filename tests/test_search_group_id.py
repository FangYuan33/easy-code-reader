"""Tests for search_group_id tool in Easy Code Reader MCP Server."""

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


def create_test_artifact_with_package(maven_repo: Path, group_id: str, artifact_name: str, 
                                     version: str, package_path: str = None):
    """
    Create a test artifact (JAR file) with optional package structure.

    Args:
        maven_repo: Root directory of the Maven repository.
        group_id: Maven group ID (e.g., com.jdd.baozang).
        artifact_name: Maven artifact name (e.g., baozang-trade-export).
        version: Maven version (e.g., 1.2.2).
        package_path: Package path for class files (e.g., com.jdd.baozang.trade.export)

    Returns:
        Path to the created JAR file.
    """
    # Build directory structure
    group_path = group_id.replace('.', '/')
    artifact_dir = maven_repo / group_path / artifact_name / version
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # Create main JAR file
    jar_path = artifact_dir / f"{artifact_name}-{version}.jar"
    with zipfile.ZipFile(jar_path, 'w', zipfile.ZIP_DEFLATED) as jar:
        # Add manifest
        manifest = "Manifest-Version: 1.0\n"
        jar.writestr("META-INF/MANIFEST.MF", manifest)

        # Add a test class file with specified package
        if package_path:
            class_bytes = bytes([
                0xCA, 0xFE, 0xBA, 0xBE,  # Magic number
                0x00, 0x00,               # Minor version
                0x00, 0x34,               # Major version 52 (Java 8)
            ]) + b'\x00' * 100
            class_file_path = package_path.replace('.', '/') + '/Test.class'
            jar.writestr(class_file_path, class_bytes)
    return jar_path


@pytest.mark.asyncio
async def test_search_group_id_basic(temp_maven_repo):
    """测试基础搜索功能：找到一个 artifact"""
    # 创建测试 artifact，package 与 groupId 对齐（高置信度）
    create_test_artifact_with_package(
        temp_maven_repo, "com.example", "test-artifact", "1.0.0", "com.example.test"
    )
    
    # 创建服务器实例
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 执行搜索
    result = await server._search_group_id("test-artifact")
    
    # 解析返回结果
    assert len(result) == 1
    json_result = json.loads(result[0].text)
    
    # 验证结果
    assert json_result["artifact_name"] == "test-artifact"
    assert json_result["total_matches"] == 1
    assert len(json_result["matches"]) == 1
    
    match = json_result["matches"][0]
    assert match["group_id"] == "com.example"
    assert match["confidence"] == "high"  # package 与 groupId 对齐
    assert match["sample_package"] == "com.example.test"
    assert "1.0.0" in match["matched_versions"]
    assert match["total_versions"] == 1
    
    # 验证提示信息（唯一高置信度匹配）
    assert "✅ 找到唯一高置信度匹配" in json_result["hint"]
    assert "read_jar_source" in json_result["hint"]


@pytest.mark.asyncio
async def test_search_group_id_with_group_prefix(temp_maven_repo):
    """测试使用 group_prefix 过滤"""
    # 创建不同 groupId 的 artifact
    create_test_artifact_with_package(
        temp_maven_repo, "com.example", "shared-name", "1.0.0", "com.example.test"
    )
    create_test_artifact_with_package(
        temp_maven_repo, "org.springframework", "shared-name", "1.0.0", "org.springframework.core"
    )
    create_test_artifact_with_package(
        temp_maven_repo, "io.netty", "shared-name", "1.0.0", "io.netty.buffer"
    )
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 只搜索 org.springframework 下的
    result = await server._search_group_id("shared-name", group_prefix="org.springframework")
    json_result = json.loads(result[0].text)
    
    assert json_result["total_matches"] == 1
    assert json_result["matches"][0]["group_id"] == "org.springframework"


@pytest.mark.asyncio
async def test_search_group_id_with_version_hint(temp_maven_repo):
    """测试使用 version_hint 过滤"""
    # 创建多个版本
    create_test_artifact_with_package(
        temp_maven_repo, "com.example", "version-test", "1.0.0", "com.example.test"
    )
    create_test_artifact_with_package(
        temp_maven_repo, "com.example", "version-test", "1.1.0", "com.example.test"
    )
    create_test_artifact_with_package(
        temp_maven_repo, "com.example", "version-test", "2.0.0", "com.example.test"
    )
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 搜索版本包含 "1." 的
    result = await server._search_group_id("version-test", version_hint="1.")
    json_result = json.loads(result[0].text)
    
    assert json_result["total_matches"] == 1
    match = json_result["matches"][0]
    assert match["group_id"] == "com.example"
    # 应该找到两个版本：1.0.0 和 1.1.0
    assert len(match["matched_versions"]) == 2
    assert "1.0.0" in match["matched_versions"]
    assert "1.1.0" in match["matched_versions"]
    assert "2.0.0" not in match["matched_versions"]


@pytest.mark.asyncio
async def test_search_group_id_confidence_high(temp_maven_repo):
    """测试高置信度：package 以 groupId 开头"""
    create_test_artifact_with_package(
        temp_maven_repo, "com.jdd.baozang", "test-artifact", "1.0.0", 
        "com.jdd.baozang.trade.export"
    )
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_group_id("test-artifact")
    json_result = json.loads(result[0].text)
    
    match = json_result["matches"][0]
    assert match["confidence"] == "high"
    assert match["sample_package"] == "com.jdd.baozang.trade.export"


@pytest.mark.asyncio
async def test_search_group_id_confidence_medium(temp_maven_repo):
    """测试中等置信度：package 以 group_prefix 开头"""
    create_test_artifact_with_package(
        temp_maven_repo, "com.jdd.internal", "test-artifact", "1.0.0", 
        "com.jdd.other.package"
    )
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_group_id("test-artifact", group_prefix="com.jdd")
    json_result = json.loads(result[0].text)
    
    match = json_result["matches"][0]
    # package 以 group_prefix 开头，但不以完整 groupId 开头
    assert match["confidence"] == "medium"


@pytest.mark.asyncio
async def test_search_group_id_confidence_low(temp_maven_repo):
    """测试低置信度：无法验证 package 对齐"""
    create_test_artifact_with_package(
        temp_maven_repo, "com.example", "test-artifact", "1.0.0", 
        "org.other.package"  # package 与 groupId 不对齐
    )
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_group_id("test-artifact")
    json_result = json.loads(result[0].text)
    
    match = json_result["matches"][0]
    assert match["confidence"] == "low"


@pytest.mark.asyncio
async def test_search_group_id_multiple_matches(temp_maven_repo):
    """测试多个匹配，按置信度排序"""
    # 创建不同置信度的匹配
    create_test_artifact_with_package(
        temp_maven_repo, "com.example.low", "test", "1.0.0", "org.other.package"
    )
    create_test_artifact_with_package(
        temp_maven_repo, "com.example.high", "test", "1.0.0", "com.example.high.service"
    )
    create_test_artifact_with_package(
        temp_maven_repo, "com.example.medium", "test", "1.0.0", "com.example.other"
    )
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_group_id("test", group_prefix="com.example")
    json_result = json.loads(result[0].text)
    
    matches = json_result["matches"]
    assert len(matches) == 3
    
    # 验证排序：high > medium > low
    assert matches[0]["confidence"] == "high"
    assert matches[0]["group_id"] == "com.example.high"
    assert matches[1]["confidence"] == "medium"
    assert matches[2]["confidence"] == "low"


@pytest.mark.asyncio
async def test_search_group_id_not_found(temp_maven_repo):
    """测试搜索不存在的 artifact"""
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_group_id("nonexistent-artifact")
    
    json_result = json.loads(result[0].text)
    
    assert json_result["total_matches"] == 0
    assert len(json_result["matches"]) == 0
    
    # 验证错误提示
    assert "❌ 未找到" in json_result["hint"]
    assert "可能原因" in json_result["hint"]


@pytest.mark.asyncio
async def test_search_group_id_empty_input(temp_maven_repo):
    """测试空输入验证"""
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 测试空字符串
    result = await server._search_group_id("")
    assert "错误: artifact_name 不能为空" in result[0].text
    
    # 测试只有空格
    result = await server._search_group_id("   ")
    assert "错误: artifact_name 不能为空" in result[0].text


@pytest.mark.asyncio
async def test_search_group_id_search_stats(temp_maven_repo):
    """测试搜索统计信息"""
    create_test_artifact_with_package(
        temp_maven_repo, "com.example", "stats-test", "1.0.0", "com.example.test"
    )
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_group_id("stats-test")
    
    json_result = json.loads(result[0].text)
    
    # 验证统计信息
    assert "search_stats" in json_result
    stats = json_result["search_stats"]
    assert "scanned_groups" in stats
    assert "scanned_jars" in stats
    assert "elapsed_seconds" in stats
    assert isinstance(stats["scanned_groups"], int)
    assert isinstance(stats["scanned_jars"], int)
    assert isinstance(stats["elapsed_seconds"], (int, float))


@pytest.mark.asyncio
async def test_search_group_id_no_package_in_jar(temp_maven_repo):
    """测试 JAR 中没有 .class 文件的情况"""
    # 创建空 JAR（只有 manifest）
    group_path = "com/example"
    artifact_dir = temp_maven_repo / group_path / "empty-jar" / "1.0.0"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    jar_path = artifact_dir / "empty-jar-1.0.0.jar"
    with zipfile.ZipFile(jar_path, 'w') as jar:
        jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_group_id("empty-jar")
    
    json_result = json.loads(result[0].text)
    match = json_result["matches"][0]
    
    # 没有 package 信息，应该是低置信度
    assert match["confidence"] == "low"
    assert match["sample_package"] is None


@pytest.mark.asyncio
async def test_search_group_id_hint_scenarios(temp_maven_repo):
    """测试不同场景的提示信息"""
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 场景1：未找到匹配
    result = await server._search_group_id("not-found")
    json_result = json.loads(result[0].text)
    assert "❌" in json_result["hint"]
    assert "建议操作" in json_result["hint"]
    
    # 场景2：唯一高置信度匹配
    create_test_artifact_with_package(
        temp_maven_repo, "com.example", "unique", "1.0.0", "com.example.service"
    )
    result = await server._search_group_id("unique")
    json_result = json.loads(result[0].text)
    assert "✅ 找到唯一高置信度匹配" in json_result["hint"]
    
    # 场景3：多个候选
    create_test_artifact_with_package(
        temp_maven_repo, "com.example.a", "multiple", "1.0.0", "com.example.a.service"
    )
    create_test_artifact_with_package(
        temp_maven_repo, "com.example.b", "multiple", "1.0.0", "com.example.b.service"
    )
    result = await server._search_group_id("multiple")
    json_result = json.loads(result[0].text)
    assert "🎯 找到" in json_result["hint"]
    assert "建议选择" in json_result["hint"]


@pytest.mark.asyncio
async def test_search_group_id_version_hint_warning(temp_maven_repo):
    """测试 version_hint 在提示中的警告"""
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 使用 version_hint 但未找到匹配
    result = await server._search_group_id("test", version_hint="1.2.2")
    json_result = json.loads(result[0].text)
    
    # 应该包含关于 version_hint 可能导致查不到的警告
    assert "version_hint" in json_result["hint"]
    assert "AI 可能产生幻觉" in json_result["hint"] or "过滤过严" in json_result["hint"]


@pytest.mark.asyncio
async def test_search_group_id_matched_versions_limit(temp_maven_repo):
    """测试 matched_versions 最多返回10个版本"""
    # 创建超过10个版本
    for i in range(15):
        create_test_artifact_with_package(
            temp_maven_repo, "com.example", "many-versions", f"{i}.0.0", "com.example.test"
        )
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_group_id("many-versions")
    
    json_result = json.loads(result[0].text)
    match = json_result["matches"][0]
    
    # 应该只返回最多10个版本
    assert len(match["matched_versions"]) <= 10
    assert match["total_versions"] == 15


@pytest.mark.asyncio
async def test_search_group_id_case_insensitive(temp_maven_repo):
    """测试不区分大小写的过滤"""
    create_test_artifact_with_package(
        temp_maven_repo, "Com.Example", "test-case", "1.0.0-SNAPSHOT", "com.example.test"
    )
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # group_prefix 不区分大小写
    result = await server._search_group_id("test-case", group_prefix="example")
    json_result = json.loads(result[0].text)
    assert json_result["total_matches"] == 1
    
    # version_hint 不区分大小写
    result = await server._search_group_id("test-case", version_hint="snapshot")
    json_result = json.loads(result[0].text)
    assert json_result["total_matches"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
