"""测试 SNAPSHOT 版本处理"""

import tempfile
import pytest
from pathlib import Path
from easy_code_reader.server import EasyCodeReaderServer
from easy_code_reader.decompiler import JavaDecompiler


def test_is_timestamped_snapshot():
    """测试时间戳 SNAPSHOT 版本识别"""
    decompiler = JavaDecompiler()
    
    # 应该识别为时间戳 SNAPSHOT
    assert decompiler._is_timestamped_snapshot("athena-bugou-trade-export-1.0.11-20251030.085053-1")
    assert decompiler._is_timestamped_snapshot("my-artifact-2.3.4-20231225.123456-10")
    
    # 不应该识别为时间戳 SNAPSHOT
    assert not decompiler._is_timestamped_snapshot("athena-bugou-trade-export-1.0.11-SNAPSHOT")
    assert not decompiler._is_timestamped_snapshot("my-artifact-1.0.0")
    assert not decompiler._is_timestamped_snapshot("my-artifact-1.0.0-RC1")


@pytest.mark.asyncio
async def test_get_jar_path_snapshot_with_timestamp():
    """测试获取带时间戳的 SNAPSHOT jar 路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        maven_repo = Path(tmpdir)
        
        # 创建 SNAPSHOT 版本目录结构
        jar_dir = maven_repo / "com" / "example" / "test-artifact" / "1.0.11-SNAPSHOT"
        jar_dir.mkdir(parents=True)
        
        # 创建多个 jar 文件（模拟 SNAPSHOT 的不同时间戳版本）
        older_jar = jar_dir / "test-artifact-1.0.11-20251029.100000-1.jar"
        newer_jar = jar_dir / "test-artifact-1.0.11-20251030.085053-2.jar"
        snapshot_jar = jar_dir / "test-artifact-1.0.11-SNAPSHOT.jar"
        
        older_jar.touch()
        newer_jar.touch()
        snapshot_jar.touch()
        
        # 创建服务器实例
        server = EasyCodeReaderServer(maven_repo_path=str(maven_repo))
        
        # 应该返回最新的带时间戳的 jar
        result = server._get_jar_path("com.example", "test-artifact", "1.0.11-SNAPSHOT")
        
        assert result is not None
        assert result == newer_jar
        assert "20251030.085053-2" in result.name


@pytest.mark.asyncio
async def test_get_jar_path_snapshot_fallback():
    """测试 SNAPSHOT 版本回退到通用 jar"""
    with tempfile.TemporaryDirectory() as tmpdir:
        maven_repo = Path(tmpdir)
        
        # 创建 SNAPSHOT 版本目录结构
        jar_dir = maven_repo / "com" / "example" / "test-artifact" / "1.0.11-SNAPSHOT"
        jar_dir.mkdir(parents=True)
        
        # 只创建通用的 SNAPSHOT jar
        snapshot_jar = jar_dir / "test-artifact-1.0.11-SNAPSHOT.jar"
        snapshot_jar.touch()
        
        # 创建服务器实例
        server = EasyCodeReaderServer(maven_repo_path=str(maven_repo))
        
        # 应该返回通用的 SNAPSHOT jar
        result = server._get_jar_path("com.example", "test-artifact", "1.0.11-SNAPSHOT")
        
        assert result is not None
        assert result == snapshot_jar


@pytest.mark.asyncio
async def test_get_sources_jar_path_snapshot_with_timestamp():
    """测试获取带时间戳的 SNAPSHOT sources jar 路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        maven_repo = Path(tmpdir)
        
        # 创建 SNAPSHOT 版本目录结构
        jar_dir = maven_repo / "com" / "example" / "test-artifact" / "1.0.11-SNAPSHOT"
        jar_dir.mkdir(parents=True)
        
        # 创建多个 sources jar 文件
        older_sources = jar_dir / "test-artifact-1.0.11-20251029.100000-1-sources.jar"
        newer_sources = jar_dir / "test-artifact-1.0.11-20251030.085053-2-sources.jar"
        snapshot_sources = jar_dir / "test-artifact-1.0.11-SNAPSHOT-sources.jar"
        
        older_sources.touch()
        newer_sources.touch()
        snapshot_sources.touch()
        
        # 创建服务器实例
        server = EasyCodeReaderServer(maven_repo_path=str(maven_repo))
        
        # 应该返回最新的带时间戳的 sources jar
        result = server._get_sources_jar_path("com.example", "test-artifact", "1.0.11-SNAPSHOT")
        
        assert result is not None
        assert result == newer_sources
        assert "20251030.085053-2" in result.name


def test_cleanup_old_snapshot_cache():
    """测试清理旧的 SNAPSHOT 缓存"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_base_dir = Path(tmpdir)
        
        # 创建多个 SNAPSHOT 缓存目录
        old_cache1 = cache_base_dir / "test-artifact-1.0.11-20251028.120000-1"
        old_cache2 = cache_base_dir / "test-artifact-1.0.11-20251029.100000-5"
        current_cache = cache_base_dir / "test-artifact-1.0.11-20251030.085053-10"
        
        old_cache1.mkdir()
        old_cache2.mkdir()
        current_cache.mkdir()
        
        # 在每个目录中创建文件以验证删除
        (old_cache1 / "test.txt").touch()
        (old_cache2 / "test.txt").touch()
        (current_cache / "test.txt").touch()
        
        # 执行清理
        decompiler = JavaDecompiler()
        decompiler._cleanup_old_snapshot_cache(cache_base_dir, "test-artifact-1.0.11-20251030.085053-10")
        
        # 验证旧缓存被删除，当前缓存保留
        assert not old_cache1.exists()
        assert not old_cache2.exists()
        assert current_cache.exists()
        assert (current_cache / "test.txt").exists()


@pytest.mark.asyncio
async def test_get_jar_path_regular_version():
    """测试获取非 SNAPSHOT 版本 jar 路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        maven_repo = Path(tmpdir)
        
        # 创建普通版本目录结构
        jar_dir = maven_repo / "com" / "example" / "test-artifact" / "1.0.0"
        jar_dir.mkdir(parents=True)
        
        # 创建 jar 文件
        jar_file = jar_dir / "test-artifact-1.0.0.jar"
        jar_file.touch()
        
        # 创建服务器实例
        server = EasyCodeReaderServer(maven_repo_path=str(maven_repo))
        
        # 应该返回普通的 jar
        result = server._get_jar_path("com.example", "test-artifact", "1.0.0")
        
        assert result is not None
        assert result == jar_file
