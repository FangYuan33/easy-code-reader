"""测试 SNAPSHOT 版本反编译行为"""

import tempfile
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from easy_code_reader.server import EasyCodeReaderServer
from easy_code_reader.decompiler import JavaDecompiler


def create_test_jar_with_class(jar_path: Path, class_name: str = "com.example.TestClass"):
    """创建一个包含类文件的测试 JAR"""
    with zipfile.ZipFile(jar_path, 'w', zipfile.ZIP_DEFLATED) as jar:
        # 添加 manifest
        manifest = "Manifest-Version: 1.0\n"
        jar.writestr("META-INF/MANIFEST.MF", manifest)
        
        # 添加一个类文件（带有正确的 magic number）
        class_bytes = bytes([
            0xCA, 0xFE, 0xBA, 0xBE,  # Magic number
            0x00, 0x00,               # Minor version
            0x00, 0x34,               # Major version 52 (Java 8)
        ]) + b'\x00' * 100
        class_file_path = class_name.replace('.', '/') + '.class'
        jar.writestr(class_file_path, class_bytes)


def create_decompiled_jar_with_source(jar_path: Path, class_name: str, source_code: str):
    """创建一个包含反编译源代码的 JAR（模拟 Fernflower 输出）"""
    with zipfile.ZipFile(jar_path, 'w', zipfile.ZIP_DEFLATED) as jar:
        java_file_path = class_name.replace('.', '/') + '.java'
        jar.writestr(java_file_path, source_code)


@pytest.mark.asyncio
async def test_snapshot_decompile_uses_snapshot_jar():
    """
    测试 SNAPSHOT 版本反编译时使用 -SNAPSHOT.jar 而不是带时间戳的 jar
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        maven_repo = Path(tmpdir)
        
        # 创建 SNAPSHOT 版本目录结构
        jar_dir = maven_repo / "com" / "example" / "test-artifact" / "1.0.11-SNAPSHOT"
        jar_dir.mkdir(parents=True)
        
        # 创建两个 jar 文件
        # 1. 带时间戳的 jar（用于版本检查）
        timestamped_jar = jar_dir / "test-artifact-1.0.11-20251030.085053-2.jar"
        create_test_jar_with_class(timestamped_jar, "com.example.TestClass")
        
        # 2. 通用 SNAPSHOT jar（应该用于反编译）
        snapshot_jar = jar_dir / "test-artifact-1.0.11-SNAPSHOT.jar"
        create_test_jar_with_class(snapshot_jar, "com.example.TestClass")
        
        # 创建服务器实例
        server = EasyCodeReaderServer(maven_repo_path=str(maven_repo))
        
        # Mock Fernflower 反编译过程
        original_run = __import__('subprocess').run
        
        def mock_subprocess_run(cmd, **kwargs):
            """模拟 Fernflower 反编译"""
            if 'java' in cmd and '-jar' in cmd:
                # 检查传入的 jar 路径
                jar_arg = cmd[-2]
                output_dir_arg = cmd[-1]
                
                jar_path = Path(jar_arg)
                output_dir = Path(output_dir_arg)
                
                # 验证：应该使用 SNAPSHOT jar 进行反编译
                assert jar_path.name == "test-artifact-1.0.11-SNAPSHOT.jar", \
                    f"期望使用 SNAPSHOT jar 反编译，但实际使用了 {jar_path.name}"
                
                # 模拟 Fernflower 输出：创建反编译后的 jar
                output_dir.mkdir(parents=True, exist_ok=True)
                decompiled_jar = output_dir / jar_path.name
                
                source_code = """package com.example;

public class TestClass {
    public void testMethod() {
        System.out.println("Test");
    }
}
"""
                create_decompiled_jar_with_source(decompiled_jar, "com.example.TestClass", source_code)
                
                # 返回成功结果
                result = MagicMock()
                result.returncode = 0
                result.stderr = ""
                return result
            
            return original_run(cmd, **kwargs)
        
        with patch('subprocess.run', side_effect=mock_subprocess_run):
            # 调用 _read_jar_source
            result = await server._read_jar_source(
                group_id="com.example",
                artifact_id="test-artifact",
                version="1.0.11-SNAPSHOT",
                class_name="com.example.TestClass",
                prefer_sources=False  # 强制使用反编译
            )
            
            # 验证结果
            assert len(result) == 1
            assert "TestClass" in result[0].text
            assert "testMethod" in result[0].text
            
            # 验证缓存文件使用带时间戳的名称
            cache_dir = jar_dir / "easy-code-reader"
            assert cache_dir.exists()
            
            # 缓存应该使用带时间戳的 jar 名称
            cached_jar = cache_dir / "test-artifact-1.0.11-20251030.085053-2.jar"
            assert cached_jar.exists(), f"缓存 jar 应该使用时间戳名称: {cached_jar}"


@pytest.mark.asyncio
async def test_snapshot_decompile_fallback_to_timestamped_jar():
    """
    测试如果 -SNAPSHOT.jar 不存在，回退到使用带时间戳的 jar
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        maven_repo = Path(tmpdir)
        
        # 创建 SNAPSHOT 版本目录结构
        jar_dir = maven_repo / "com" / "example" / "test-artifact" / "1.0.11-SNAPSHOT"
        jar_dir.mkdir(parents=True)
        
        # 只创建带时间戳的 jar（没有通用 SNAPSHOT jar）
        timestamped_jar = jar_dir / "test-artifact-1.0.11-20251030.085053-2.jar"
        create_test_jar_with_class(timestamped_jar, "com.example.TestClass")
        
        # 创建服务器实例
        server = EasyCodeReaderServer(maven_repo_path=str(maven_repo))
        
        # Mock Fernflower 反编译过程
        original_run = __import__('subprocess').run
        
        def mock_subprocess_run(cmd, **kwargs):
            """模拟 Fernflower 反编译"""
            if 'java' in cmd and '-jar' in cmd:
                jar_arg = cmd[-2]
                output_dir_arg = cmd[-1]
                
                jar_path = Path(jar_arg)
                output_dir = Path(output_dir_arg)
                
                # 如果没有 SNAPSHOT jar，应该回退到使用带时间戳的 jar
                assert jar_path.name == "test-artifact-1.0.11-20251030.085053-2.jar", \
                    f"SNAPSHOT jar 不存在时应该使用时间戳 jar，但实际使用了 {jar_path.name}"
                
                # 模拟 Fernflower 输出
                output_dir.mkdir(parents=True, exist_ok=True)
                decompiled_jar = output_dir / jar_path.name
                
                source_code = """package com.example;

public class TestClass {
    public void testMethod() {
        System.out.println("Test");
    }
}
"""
                create_decompiled_jar_with_source(decompiled_jar, "com.example.TestClass", source_code)
                
                result = MagicMock()
                result.returncode = 0
                result.stderr = ""
                return result
            
            return original_run(cmd, **kwargs)
        
        with patch('subprocess.run', side_effect=mock_subprocess_run):
            result = await server._read_jar_source(
                group_id="com.example",
                artifact_id="test-artifact",
                version="1.0.11-SNAPSHOT",
                class_name="com.example.TestClass",
                prefer_sources=False
            )
            
            # 验证结果
            assert len(result) == 1
            assert "TestClass" in result[0].text


def test_get_snapshot_jar_path():
    """测试 _get_snapshot_jar_path 方法"""
    with tempfile.TemporaryDirectory() as tmpdir:
        maven_repo = Path(tmpdir)
        
        # 创建 SNAPSHOT 版本目录
        jar_dir = maven_repo / "com" / "example" / "test-artifact" / "1.0.11-SNAPSHOT"
        jar_dir.mkdir(parents=True)
        
        # 创建 SNAPSHOT jar
        snapshot_jar = jar_dir / "test-artifact-1.0.11-SNAPSHOT.jar"
        snapshot_jar.touch()
        
        # 创建服务器实例
        server = EasyCodeReaderServer(maven_repo_path=str(maven_repo))
        
        # 测试获取 SNAPSHOT jar 路径
        result = server._get_snapshot_jar_path("com.example", "test-artifact", "1.0.11-SNAPSHOT")
        
        assert result is not None
        assert result == snapshot_jar
        assert result.name == "test-artifact-1.0.11-SNAPSHOT.jar"


def test_get_snapshot_jar_path_for_non_snapshot():
    """测试非 SNAPSHOT 版本返回 None"""
    with tempfile.TemporaryDirectory() as tmpdir:
        maven_repo = Path(tmpdir)
        
        # 创建服务器实例
        server = EasyCodeReaderServer(maven_repo_path=str(maven_repo))
        
        # 测试非 SNAPSHOT 版本
        result = server._get_snapshot_jar_path("com.example", "test-artifact", "1.0.0")
        
        assert result is None
