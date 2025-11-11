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
    """测试少量结果的提示信息准确性"""
    # 创建包含数字和字符串版本的测试数据
    versions = ["2.0.0", "1.10.0", "1.9.0", "latest", "dev"]
    for version in versions:
        create_test_artifact(temp_maven_repo, "com.example", "test-artifact", version)
    
    server = EasyCodeReaderServer(maven_repo_path=str(temp_maven_repo))
    result = await server._search_artifact("test-artifact")
    
    json_result = json.loads(result[0].text)
    hint = json_result["hint"]
    
    # 验证提示信息中提到了正确的排序规则
    assert "数字版本" in hint, "提示信息应该提到数字版本"
    assert "语义版本" in hint or "语义" in hint, "提示信息应该说明语义版本排序"
    assert "字符串版本" in hint, "提示信息应该提到字符串版本"
    
    # 验证实际排序确实符合提示
    returned_versions = [m["version"] for m in json_result["matches"]]
    
    # 数字版本应该在前面
    numeric_versions = [v for v in returned_versions if v[0].isdigit()]
    string_versions = [v for v in returned_versions if not v[0].isdigit()]
    
    # 所有数字版本的索引应该小于所有字符串版本的索引
    if numeric_versions and string_versions:
        last_numeric_idx = returned_versions.index(numeric_versions[-1])
        first_string_idx = returned_versions.index(string_versions[0])
        assert last_numeric_idx < first_string_idx, \
            "数字版本应该排在字符串版本之前（如提示所说）"
    
    # 数字版本应该按语义版本降序排列
    expected_numeric_order = ["2.0.0", "1.10.0", "1.9.0"]
    assert numeric_versions == expected_numeric_order, \
        f"数字版本排序应该符合语义版本规则（如提示所说）: 期望 {expected_numeric_order}, 实际 {numeric_versions}"


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
    
    # 验证提示信息的描述与实际行为一致
    # 1. 数字版本在前
    numeric_versions = ["3.0.0", "2.5.0", "2.0.0", "1.0.0"]
    string_versions = ["stable", "latest"]
    
    for nv in numeric_versions:
        for sv in string_versions:
            nv_idx = returned_versions.index(nv)
            sv_idx = returned_versions.index(sv)
            assert nv_idx < sv_idx, \
                f"数字版本 {nv} 应该在字符串版本 {sv} 之前（符合提示描述）"
    
    # 2. 数字版本按语义版本降序
    numeric_in_result = [v for v in returned_versions if v in numeric_versions]
    assert numeric_in_result == sorted(numeric_versions, reverse=True, 
                                      key=lambda x: tuple(map(int, x.split('.')))), \
        "数字版本应该按语义版本降序排列（符合提示描述）"
    
    print(f"\n实际排序: {returned_versions}")
    print(f"提示信息正确性验证通过！")


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
