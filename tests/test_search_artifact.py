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
    Create a test artifact (JAR file) in a temporary Maven repository.

    Args:
        maven_repo: Root directory of the Maven repository.
        group_id: Maven group ID (e.g., org.springframework).
        artifact_id: Maven artifact ID (e.g., spring-core).
        version: Maven version (e.g., 5.3.21).

    Returns:
        Path to the created JAR file.
    """
    # Build directory structure
    group_path = group_id.replace('.', '/')
    artifact_dir = maven_repo / group_path / artifact_id / version
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # Create main JAR file
    jar_path = artifact_dir / f"{artifact_id}-{version}.jar"
    with zipfile.ZipFile(jar_path, 'w', zipfile.ZIP_DEFLATED) as jar:
        # Add manifest
        manifest = "Manifest-Version: 1.0\n"
        jar.writestr("META-INF/MANIFEST.MF", manifest)

        # Add a test class file
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
    
    # 验证 jar_files 格式（字符串数组）
    assert "jar_files" in match
    assert isinstance(match["jar_files"], list)
    assert len(match["jar_files"]) == 1
    assert match["jar_files"][0] == "test-artifact-1.0.0.jar"
    
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
    """测试 JAR 文件详情返回 - 新格式：字符串数组"""
    create_test_artifact(temp_maven_repo, "com.example", "jar-details", "1.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("jar-details")
    
    json_result = json.loads(result[0].text)
    match = json_result["matches"][0]
    
    # 验证 JAR 文件详情 - 新格式
    assert "jar_files" in match
    assert isinstance(match["jar_files"], list)
    assert len(match["jar_files"]) > 0
    
    # 验证是字符串而非对象
    jar_file = match["jar_files"][0]
    assert isinstance(jar_file, str)
    assert jar_file.endswith(".jar")
    # 不应包含 size_mb 字段（因为是字符串而非对象）
    assert jar_file == "jar-details-1.0.0.jar"


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
    assert len(match["jar_files"]) == 1
    assert match["jar_files"][0] == "exclude-test-1.0.0.jar"


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


@pytest.mark.asyncio
async def test_search_artifact_performance_optimization(temp_maven_repo):
    """
    测试搜索性能优化：验证使用 rglob(artifact_id) 而非 rglob('*')
    
    创建复杂的目录结构来验证：
    - 搜索次数应该只计数匹配的 artifact 目录
    - 不应该遍历所有不相关的目录和文件
    """
    # 创建目标 artifact
    create_test_artifact(temp_maven_repo, "com.example", "target-artifact", "1.0.0")
    
    # 创建大量干扰目录和文件（在不同的 groupId 下）
    noise_groups = ["org.apache", "io.netty", "com.google"]
    noise_artifacts = ["noise-1", "noise-2", "noise-3", "noise-4", "noise-5"]
    
    for group in noise_groups:
        for artifact in noise_artifacts:
            create_test_artifact(temp_maven_repo, group, artifact, "1.0.0")
            # 再创建一些版本目录增加复杂度
            create_test_artifact(temp_maven_repo, group, artifact, "2.0.0")
    
    # 执行搜索
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("target-artifact")
    
    json_result = json.loads(result[0].text)
    
    # 验证找到目标
    assert json_result["total_matches"] == 1
    assert json_result["matches"][0]["artifact_id"] == "target-artifact"
    
    # 验证性能：searched_dirs 应该远小于总目录数
    # 如果使用 rglob('*')，会遍历所有目录（3 groups * 5 artifacts * 2 versions = 30+ 个版本目录，加上中间路径会更多）
    # 如果使用 rglob(artifact_id)，只会检查匹配的目录（应该只有几个）
    searched_dirs = json_result["searched_dirs"]
    
    # 由于优化后只搜索名为 target-artifact 的目录，searched_dirs 应该很小
    # 在这个测试中，应该远小于 30（实际干扰目录数）
    assert searched_dirs < 10, f"搜索了 {searched_dirs} 个目录，优化可能未生效（预期 < 10）"
    
    # 验证搜索时间合理
    assert json_result["elapsed_seconds"] < 5, "搜索时间过长，可能存在性能问题"


@pytest.mark.asyncio
async def test_search_artifact_deep_nested_structure(temp_maven_repo):
    """测试深层嵌套结构的搜索"""
    # 创建深层嵌套的 groupId
    create_test_artifact(temp_maven_repo, "com.example.very.deep.nested", "deep-artifact", "1.0.0")
    create_test_artifact(temp_maven_repo, "org.another.deep.structure", "deep-artifact", "2.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("deep-artifact")
    
    json_result = json.loads(result[0].text)
    
    # 验证能找到所有深层嵌套的 artifact
    assert json_result["total_matches"] == 2
    
    # 验证 groupId 格式正确（应该包含所有层级）
    group_ids = [m["group_id"] for m in json_result["matches"]]
    assert "com.example.very.deep.nested" in group_ids
    assert "org.another.deep.structure" in group_ids


@pytest.mark.asyncio
async def test_search_artifact_early_filtering_with_group_hint(temp_maven_repo):
    """
    测试 group_id_hint 早期过滤优化
    
    验证：
    1. 当提供带完整路径的 group_id_hint 时，应该跳过不匹配的顶级目录
    2. searched_dirs 应该显著减少
    3. 结果应该只包含匹配 hint 的 artifacts
    """
    # 创建多个顶级 group 下的同名 artifact
    create_test_artifact(temp_maven_repo, "com.example", "common-name", "1.0.0")
    create_test_artifact(temp_maven_repo, "com.other", "common-name", "1.0.0")
    create_test_artifact(temp_maven_repo, "org.springframework", "common-name", "1.0.0")
    create_test_artifact(temp_maven_repo, "org.apache", "common-name", "1.0.0")
    create_test_artifact(temp_maven_repo, "io.netty", "common-name", "1.0.0")
    
    # 创建更多干扰项（在不同的顶级目录）
    for i in range(5):
        create_test_artifact(temp_maven_repo, f"com.noise{i}", "noise-artifact", "1.0.0")
        create_test_artifact(temp_maven_repo, f"io.noise{i}", "noise-artifact", "1.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 不使用 hint 搜索（基准）
    result_no_hint = await server._search_artifact("common-name")
    json_no_hint = json.loads(result_no_hint[0].text)
    searched_no_hint = json_no_hint["searched_dirs"]
    
    # 使用完整的 group_id_hint="org.springframework" 搜索（带点号，可以早期过滤）
    result_with_hint = await server._search_artifact("common-name", group_id_hint="org.springframework")
    json_with_hint = json.loads(result_with_hint[0].text)
    
    # 验证结果正确性
    assert json_with_hint["total_matches"] == 1
    assert json_with_hint["matches"][0]["group_id"] == "org.springframework"
    
    # 验证性能优化：使用完整路径 hint 时搜索的目录数应该更少
    # 因为会跳过 com/ 和 io/ 目录，只搜索 org/ 目录
    searched_with_hint = json_with_hint["searched_dirs"]
    assert searched_with_hint < searched_no_hint, \
        f"早期过滤未生效: hint搜索了 {searched_with_hint} 个目录, 无hint搜索了 {searched_no_hint} 个目录"
    
    # 更强的断言：应该只搜索 org/ 目录下的匹配项
    # org/ 下有 2 个 common-name（org.springframework 和 org.apache）
    assert searched_with_hint <= 2, \
        f"早期过滤优化可能未充分生效: 搜索了 {searched_with_hint} 个目录（预期 ≤ 2，因为只应搜索 org/ 分支）"


@pytest.mark.asyncio
async def test_search_artifact_hint_with_dot_notation(temp_maven_repo):
    """测试使用点号分隔的 group_id_hint"""
    # 创建测试数据
    create_test_artifact(temp_maven_repo, "com.example.project", "test-artifact", "1.0.0")
    create_test_artifact(temp_maven_repo, "org.example.other", "test-artifact", "1.0.0")
    create_test_artifact(temp_maven_repo, "net.other", "test-artifact", "1.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 使用包含点号的 hint
    result = await server._search_artifact("test-artifact", group_id_hint="com.example")
    json_result = json.loads(result[0].text)
    
    # 应该只找到 com.example.* 下的
    assert json_result["total_matches"] == 1
    assert json_result["matches"][0]["group_id"] == "com.example.project"


@pytest.mark.asyncio
async def test_search_artifact_hint_partial_match(temp_maven_repo):
    """测试 group_id_hint 部分匹配行为"""
    # 创建不同的 group
    create_test_artifact(temp_maven_repo, "com.example.spring", "test", "1.0.0")
    create_test_artifact(temp_maven_repo, "org.springframework.boot", "test", "1.0.0")
    create_test_artifact(temp_maven_repo, "io.spring.framework", "test", "1.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    # 使用 "spring" 作为 hint，应该匹配所有包含 spring 的 group
    result = await server._search_artifact("test", group_id_hint="spring")
    json_result = json.loads(result[0].text)
    
    # 应该找到所有包含 "spring" 的 group
    assert json_result["total_matches"] == 3
    
    group_ids = [m["group_id"] for m in json_result["matches"]]
    assert "com.example.spring" in group_ids
    assert "org.springframework.boot" in group_ids
    assert "io.spring.framework" in group_ids


@pytest.mark.asyncio
async def test_search_artifact_version_sorting(temp_maven_repo):
    """
    测试版本号正确排序（修复字符串排序 bug）
    
    验证：
    1. 版本号应该按语义版本排序，不是字母顺序
    2. 1.10.0 > 1.9.0 > 1.2.0 > 1.1.0（正确）
    3. 不应该是 1.9.0 > 1.10.0（字母顺序，错误）
    """
    # 创建多个版本，故意使用会导致字母排序错误的版本号
    versions = ["1.0.0", "1.1.0", "1.2.0", "1.9.0", "1.10.0", "2.0.0"]
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.example", "version-sort-test", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("version-sort-test")
    
    json_result = json.loads(result[0].text)
    
    # 验证找到所有版本
    assert json_result["total_matches"] == 6
    
    # 提取返回的版本号列表
    returned_versions = [m["version"] for m in json_result["matches"]]
    
    # 验证排序：应该是降序（最新版本在前）
    # 正确顺序：2.0.0, 1.10.0, 1.9.0, 1.2.0, 1.1.0, 1.0.0
    expected_order = ["2.0.0", "1.10.0", "1.9.0", "1.2.0", "1.1.0", "1.0.0"]
    assert returned_versions == expected_order, \
        f"版本排序错误:\n  实际: {returned_versions}\n  期望: {expected_order}"
    
    # 特别验证关键问题：1.10.0 应该在 1.9.0 之前（不是字母顺序）
    idx_1_10 = returned_versions.index("1.10.0")
    idx_1_9 = returned_versions.index("1.9.0")
    assert idx_1_10 < idx_1_9, \
        f"版本排序 bug: 1.10.0 (索引 {idx_1_10}) 应该在 1.9.0 (索引 {idx_1_9}) 之前"


@pytest.mark.asyncio
async def test_search_artifact_version_sorting_with_suffixes(temp_maven_repo):
    """测试带后缀的版本号排序（SNAPSHOT, RELEASE, RC 等）"""
    # 创建带各种后缀的版本
    versions = ["1.0.0", "1.0.0-SNAPSHOT", "1.0.0-RC1", "1.0.0-RC2", "1.1.0-SNAPSHOT", "1.1.0"]
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.example", "suffix-test", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("suffix-test")
    
    json_result = json.loads(result[0].text)
    
    # 验证找到所有版本
    assert json_result["total_matches"] == 6
    
    # 提取版本号
    returned_versions = [m["version"] for m in json_result["matches"]]
    
    # 验证 1.1.0 应该在所有 1.0.x 之前
    idx_1_1_0 = returned_versions.index("1.1.0")
    idx_1_0_0 = returned_versions.index("1.0.0")
    assert idx_1_1_0 < idx_1_0_0, \
        "1.1.0 应该排在 1.0.0 之前（更新的版本）"


@pytest.mark.asyncio  
async def test_search_artifact_version_sorting_multi_group(temp_maven_repo):
    """测试多个 groupId 时，每个 group 内版本正确排序"""
    # 为不同的 groupId 创建版本
    for group in ["com.example", "org.test"]:
        for version in ["1.0.0", "1.9.0", "1.10.0", "2.0.0"]:
            create_test_artifact(temp_maven_repo, group, "multi-group", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("multi-group")
    
    json_result = json.loads(result[0].text)
    
    # 验证总数
    assert json_result["total_matches"] == 8
    
    # 按 groupId 分组检查
    matches_by_group = {}
    for match in json_result["matches"]:
        group_id = match["group_id"]
        if group_id not in matches_by_group:
            matches_by_group[group_id] = []
        matches_by_group[group_id].append(match["version"])
    
    # 验证每个 group 内的版本排序
    expected_version_order = ["2.0.0", "1.10.0", "1.9.0", "1.0.0"]
    
    for group_id, versions in matches_by_group.items():
        assert versions == expected_version_order, \
            f"{group_id} 的版本排序错误:\n  实际: {versions}\n  期望: {expected_version_order}"


@pytest.mark.asyncio
async def test_search_artifact_snapshot_with_main_jar(temp_maven_repo):
    """测试 SNAPSHOT 版本：存在主 SNAPSHOT JAR 时，只返回主 JAR"""
    # 创建 SNAPSHOT 版本目录
    artifact_dir = temp_maven_repo / "com" / "example" / "snapshot-main" / "1.0.0-SNAPSHOT"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建主 SNAPSHOT JAR 和多个带时间戳的 JAR
    for jar_name in [
        "snapshot-main-1.0.0-SNAPSHOT.jar",
        "snapshot-main-1.0.0-20251029.100000-1.jar",
        "snapshot-main-1.0.0-20251030.085053-2.jar",
        "snapshot-main-1.0.0-20251031.120000-3.jar"
    ]:
        jar_path = artifact_dir / jar_name
        with zipfile.ZipFile(jar_path, 'w') as jar:
            jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("snapshot-main")
    
    json_result = json.loads(result[0].text)
    match = json_result["matches"][0]
    
    # 应该只返回主 SNAPSHOT JAR，忽略所有带时间戳的 JAR
    assert len(match["jar_files"]) == 1
    assert match["jar_files"][0] == "snapshot-main-1.0.0-SNAPSHOT.jar"


@pytest.mark.asyncio
async def test_search_artifact_snapshot_without_main_jar(temp_maven_repo):
    """测试 SNAPSHOT 版本：不存在主 SNAPSHOT JAR 时，返回最新的带时间戳 JAR"""
    # 创建 SNAPSHOT 版本目录
    artifact_dir = temp_maven_repo / "com" / "example" / "snapshot-timestamped" / "1.0.0-SNAPSHOT"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    # 只创建带时间戳的 JAR（没有主 SNAPSHOT JAR）
    for jar_name in [
        "snapshot-timestamped-1.0.0-20251029.100000-1.jar",
        "snapshot-timestamped-1.0.0-20251030.085053-2.jar",
        "snapshot-timestamped-1.0.0-20251031.120000-3.jar"
    ]:
        jar_path = artifact_dir / jar_name
        with zipfile.ZipFile(jar_path, 'w') as jar:
            jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("snapshot-timestamped")
    
    json_result = json.loads(result[0].text)
    match = json_result["matches"][0]
    
    # 应该只返回最新的带时间戳的 JAR
    assert len(match["jar_files"]) == 1
    # 按文件名排序，最新的应该是 20251031
    assert match["jar_files"][0] == "snapshot-timestamped-1.0.0-20251031.120000-3.jar"


@pytest.mark.asyncio
async def test_search_artifact_snapshot_mixed_versions(temp_maven_repo):
    """测试混合 SNAPSHOT 和非 SNAPSHOT 版本"""
    # 创建非 SNAPSHOT 版本
    create_test_artifact(temp_maven_repo, "com.example", "mixed-test", "1.0.0")
    
    # 创建 SNAPSHOT 版本（带时间戳 JAR）
    snapshot_dir = temp_maven_repo / "com" / "example" / "mixed-test" / "1.0.1-SNAPSHOT"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for jar_name in [
        "mixed-test-1.0.1-20251030.085053-1.jar",
        "mixed-test-1.0.1-20251031.120000-2.jar"
    ]:
        jar_path = snapshot_dir / jar_name
        with zipfile.ZipFile(jar_path, 'w') as jar:
            jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("mixed-test")
    
    json_result = json.loads(result[0].text)
    
    # 应该找到两个版本
    assert json_result["total_matches"] == 2
    
    # 检查每个版本的 JAR 文件
    for match in json_result["matches"]:
        if match["version"] == "1.0.0":
            # 非 SNAPSHOT 版本，返回所有 JAR
            assert len(match["jar_files"]) == 1
            assert match["jar_files"][0] == "mixed-test-1.0.0.jar"
        elif match["version"] == "1.0.1-SNAPSHOT":
            # SNAPSHOT 版本，只返回最新的带时间戳 JAR
            assert len(match["jar_files"]) == 1
            assert match["jar_files"][0] == "mixed-test-1.0.1-20251031.120000-2.jar"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
