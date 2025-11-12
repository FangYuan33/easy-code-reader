"""测试提示信息的准确性"""

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
async def test_hint_message_for_few_results(temp_maven_repo):
    """测试少量结果的提示信息准确性（不再验证排序）"""
    # 创建包含数字和字符串版本的测试数据
    versions = ["2.0.0", "1.10.0", "1.9.0", "latest", "dev"]
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.example", "test-artifact", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("test-artifact")
    
    json_result = json.loads(result[0].text)
    hint = json_result["hint"]
    
    # 验证提示信息存在且包含关键内容
    assert hint, "应该有提示信息"
    assert "匹配" in hint or "结果" in hint, "提示信息应该提到匹配结果"
    
    # 验证返回的版本完整性
    returned_versions = [m["version"] for m in json_result["matches"]]
    assert set(returned_versions) == set(versions), \
        "返回的版本不完整"


@pytest.mark.asyncio
async def test_hint_message_for_many_results(temp_maven_repo):
    """测试大量结果的提示信息准确性"""
    # 创建超过5个结果
    for i in range(10):
        create_test_artifact(temp_maven_repo, f"com.example{i}", "many-artifact", "1.0.0")
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("many-artifact")
    
    json_result = json.loads(result[0].text)
    hint = json_result["hint"]
    
    # 验证提示信息详细说明了排序规则
    assert "数字版本" in hint, "大量结果的提示应该说明数字版本排序"
    assert "语义版本" in hint, "提示应该明确提到语义版本排序"
    assert "1.10.0 > 1.9.0" in hint, "提示应该给出具体的语义版本排序示例"
    assert "字符串版本" in hint, "提示应该说明字符串版本的处理"
    assert "按字母顺序" in hint, "提示应该说明字符串版本的排序方式"


@pytest.mark.asyncio
async def test_hint_accuracy_with_mixed_versions(temp_maven_repo):
    """测试混合版本时提示的准确性"""
    # 创建混合版本
    versions = ["3.0.0", "2.5.0", "2.0.0", "stable", "latest", "1.0.0"]
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.test", "mixed", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("mixed")
    
    json_result = json.loads(result[0].text)
    returned_versions = [m["version"] for m in json_result["matches"]]
    hint = json_result["hint"]
    
    # 验证提示信息存在（不再验证排序相关描述）
    assert hint, "应该有提示信息"
    
    # 验证所有版本都被返回（不验证顺序）
    assert set(returned_versions) == set(versions), \
        "返回的版本不完整"
    
    print(f"\n实际返回: {returned_versions}")
    print(f"版本返回完整性验证通过！")


@pytest.mark.asyncio
async def test_hint_does_not_claim_alphabetical_sorting(temp_maven_repo):
    """测试提示信息不再声称使用字母排序"""
    versions = ["1.10.0", "1.9.0", "2.0.0"]
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.test", "version-test", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("version-test")
    
    json_result = json.loads(result[0].text)
    hint = json_result["hint"]
    
    # 确保提示不再错误地声称按字母排序
    # （之前的bug是说"最新版本在前"但实际是字母排序）
    assert "字母顺序排列" not in hint or "字符串版本" in hint, \
        "如果提到字母排序，应该明确说明是针对字符串版本"
    
    # 验证实际行为：1.10.0 应该在 1.9.0 之前（不是字母顺序）
    returned_versions = [m["version"] for m in json_result["matches"]]
    idx_1_10 = returned_versions.index("1.10.0")
    idx_1_9 = returned_versions.index("1.9.0")
    
    assert idx_1_10 < idx_1_9, \
        "1.10.0 应该在 1.9.0 之前（语义版本排序，不是字母排序）"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
