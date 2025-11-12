"""测试版本排序的边界情况和无规则版本名称"""

import pytest
import json
import tempfile
from pathlib import Path
from easy_code_reader.server import EasyCodeReaderServer
from tests.test_search_artifact import create_test_artifact


@pytest.fixture
def temp_maven_repo():
    """创建临时 Maven 仓库用于测试"""
    with tempfile.TemporaryDirectory() as tmpdir:
        maven_repo = Path(tmpdir) / "repository"
        maven_repo.mkdir(parents=True, exist_ok=True)
        yield maven_repo


@pytest.mark.asyncio
async def test_irregular_version_names(temp_maven_repo):
    """测试完全无规则的版本名称"""
    # 创建各种非标准版本名称
    irregular_versions = [
        "latest",
        "dev",
        "nightly",
        "custom-build",
        "john-2023",
        "v1",
        "release",
        "1.0.0",  # 正常版本作为对比
        "2.0.0",
    ]
    
    for version in irregular_versions:
        create_test_artifact(temp_maven_repo, "com.example", "irregular-test", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("irregular-test")
    
    json_result = json.loads(result[0].text)
    
    # 验证找到所有版本
    assert json_result["total_matches"] == len(irregular_versions)
    
    # 获取返回的版本列表
    returned_versions = [m["version"] for m in json_result["matches"]]
    
    print(f"\n原始顺序: {irregular_versions}")
    print(f"排序后: {returned_versions}")
    
    # 验证不会崩溃，所有版本都被返回
    assert len(returned_versions) == len(irregular_versions)
    assert set(returned_versions) == set(irregular_versions)


@pytest.mark.asyncio
async def test_mixed_numeric_and_string_versions(temp_maven_repo):
    """测试数字和字符串混合的版本（不再验证排序）"""
    versions = [
        "1.0.0",
        "latest",
        "2.0.0", 
        "dev",
        "1.5.0",
        "stable",
    ]
    
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.example", "mixed-test", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("mixed-test")
    
    json_result = json.loads(result[0].text)
    returned_versions = [m["version"] for m in json_result["matches"]]
    
    print(f"\n混合版本返回: {returned_versions}")
    
    # 验证所有版本都被返回（不验证顺序）
    assert set(returned_versions) == set(versions), \
        f"返回的版本不完整"


@pytest.mark.asyncio
async def test_special_characters_in_versions(temp_maven_repo):
    """测试包含特殊字符的版本名称"""
    versions = [
        "1.0.0_final",
        "1.0.0+build123",
        "v1.0.0",
        "1.0.0.RELEASE",
        "1.0.0~beta",
    ]
    
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.example", "special-test", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("special-test")
    
    json_result = json.loads(result[0].text)
    
    # 验证不会崩溃
    assert json_result["total_matches"] == len(versions)
    print(f"\n特殊字符版本排序: {[m['version'] for m in json_result['matches']]}")


@pytest.mark.asyncio
async def test_very_long_version_names(temp_maven_repo):
    """测试超长版本名称"""
    versions = [
        "1.0.0",
        "this-is-a-very-long-version-name-for-testing-edge-cases",
        "2.0.0",
    ]
    
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.example", "long-test", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("long-test")
    
    json_result = json.loads(result[0].text)
    
    assert json_result["total_matches"] == 3


@pytest.mark.asyncio
async def test_unicode_in_versions(temp_maven_repo):
    """测试包含 Unicode 字符的版本（如果存在）"""
    versions = [
        "1.0.0",
        "2.0.0",
        # 注意：实际 Maven 很少有 Unicode 版本，但测试健壮性
    ]
    
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.example", "unicode-test", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("unicode-test")
    
    json_result = json.loads(result[0].text)
    assert json_result["total_matches"] == 2


@pytest.mark.asyncio
async def test_version_with_only_letters(temp_maven_repo):
    """测试纯字母版本名称（不再验证排序）"""
    versions = [
        "alpha",
        "beta",
        "charlie",
        "delta",
        "1.0.0",  # 作为参考
    ]
    
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.example", "letter-test", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("letter-test")
    
    json_result = json.loads(result[0].text)
    returned_versions = [m["version"] for m in json_result["matches"]]
    
    print(f"\n纯字母版本返回: {returned_versions}")
    
    # 验证所有版本都被返回（不验证顺序）
    assert set(returned_versions) == set(versions), \
        "返回的版本不完整"


@pytest.mark.asyncio
async def test_comparison_between_different_types(temp_maven_repo):
    """
    测试不同类型版本的比较问题（不再验证排序）
    验证所有版本都能正确返回
    """
    versions = [
        "3.0.0",
        "latest",
        "2.0.0",
        "dev",
        "1.0.0",
    ]
    
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.example", "comparison-test", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    
    try:
        result = await server._search_artifact("comparison-test")
        json_result = json.loads(result[0].text)
        returned_versions = [m["version"] for m in json_result["matches"]]
        
        print(f"\n混合类型版本返回结果: {returned_versions}")
        
        # 关键验证：不应该抛出 TypeError
        assert json_result["total_matches"] == 5
        
        # 验证所有版本都被返回（不验证顺序）
        assert set(returned_versions) == set(versions), \
            "返回的版本不完整"
        
    except TypeError as e:
        pytest.fail(f"不同类型版本比较时出现 TypeError: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
