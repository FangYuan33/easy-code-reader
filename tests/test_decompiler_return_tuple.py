"""
测试 decompiler.py 中 decompile_class 方法的返回值格式
确保所有分支都返回 (code, source_type) 元组
"""

import pytest
import tempfile
import zipfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from easy_code_reader.decompiler import JavaDecompiler


def create_test_jar_with_class(jar_path: Path, class_name: str = "com.test.TestClass"):
    """创建一个测试 JAR 文件，包含编译后的类"""
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
        
        class_path = class_name.replace('.', '/') + '.class'
        jar.writestr(class_path, class_bytes)


class TestDecompilerReturnTuple:
    """测试 decompile_class 方法在各种场景下都返回正确的元组格式"""
    
    def test_return_tuple_from_cache(self):
        """测试从缓存读取时返回 (code, source_type) 元组"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # 创建测试 JAR
            test_jar = tmp_path / "test.jar"
            create_test_jar_with_class(test_jar)
            
            # 创建缓存的反编译 JAR
            cache_dir = tmp_path / "easy-code-reader"
            cache_dir.mkdir(parents=True)
            decompiled_jar = cache_dir / "test.jar"
            
            java_source = """package com.test;

public class TestClass {
    public static void main(String[] args) {
        System.out.println("Cached!");
    }
}
"""
            with zipfile.ZipFile(decompiled_jar, 'w') as zf:
                zf.writestr("com/test/TestClass.java", java_source)
            
            # 调用 decompile_class
            decompiler = JavaDecompiler()
            result = decompiler.decompile_class(test_jar, "com.test.TestClass")
            
            # 验证返回值是元组
            assert isinstance(result, tuple), f"应该返回元组，但得到 {type(result)}"
            assert len(result) == 2, f"元组应该有 2 个元素，但得到 {len(result)}"
            
            code, source_type = result
            assert isinstance(code, str), f"code 应该是字符串，但得到 {type(code)}"
            assert isinstance(source_type, str), f"source_type 应该是字符串，但得到 {type(source_type)}"
            assert source_type == "decompiled_cache", f"应该是 'decompiled_cache'，但得到 '{source_type}'"
            assert "Cached!" in code
    
    def test_return_tuple_from_cfr_decompilation(self):
        """测试 CFR 反编译成功时返回 (code, source_type) 元组"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # 创建测试 JAR
            test_jar = tmp_path / "test.jar"
            create_test_jar_with_class(test_jar)
            
            decompiler = JavaDecompiler()
            
            # 模拟 CFR 反编译成功
            with patch.object(decompiler, '_decompile_with_cfr') as mock_cfr:
                expected_code = "public class TestClass { }"
                mock_cfr.return_value = (expected_code, "decompiled")
                
                # 强制使用 CFR
                with patch.object(decompiler, '_choose_decompiler', return_value=(decompiler.cfr_jar, 'cfr')):
                    result = decompiler.decompile_class(test_jar, "com.test.TestClass")
                    
                    # 验证返回值
                    assert isinstance(result, tuple), f"应该返回元组，但得到 {type(result)}"
                    assert len(result) == 2, f"元组应该有 2 个元素，但得到 {len(result)}"
                    
                    code, source_type = result
                    assert code == expected_code
                    assert source_type == "decompiled"
    
    def test_return_tuple_from_fernflower_decompilation(self):
        """测试 Fernflower 反编译成功时返回 (code, source_type) 元组"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # 创建测试 JAR
            test_jar = tmp_path / "test.jar"
            create_test_jar_with_class(test_jar)
            
            # 创建输出目录（但不预先创建反编译输出，以触发真实反编译流程）
            output_dir = tmp_path / "easy-code-reader"
            output_dir.mkdir(parents=True)
            
            java_source = """package com.test;

public class TestClass {
    public static void main(String[] args) {
        System.out.println("Fernflower decompiled!");
    }
}
"""
            
            decompiler = JavaDecompiler()
            
            # 模拟 Fernflower 反编译过程
            def mock_subprocess_run(*args, **kwargs):
                # 在 subprocess.run 被调用时创建 Fernflower 输出
                fernflower_output = output_dir / test_jar.name
                with zipfile.ZipFile(fernflower_output, 'w') as zf:
                    zf.writestr("com/test/TestClass.java", java_source)
                return Mock(returncode=0, stderr="", stdout="")
            
            with patch('subprocess.run', side_effect=mock_subprocess_run):
                # 强制使用 Fernflower
                with patch.object(decompiler, '_choose_decompiler', 
                                return_value=(decompiler.fernflower_jar, 'fernflower')):
                    result = decompiler.decompile_class(test_jar, "com.test.TestClass")
                    
                    # 验证返回值是元组
                    assert isinstance(result, tuple), f"应该返回元组，但得到 {type(result)}"
                    assert len(result) == 2, f"元组应该有 2 个元素，但得到 {len(result)}"
                    
                    code, source_type = result
                    assert isinstance(code, str), f"code 应该是字符串，但得到 {type(code)}"
                    assert isinstance(source_type, str), f"source_type 应该是字符串，但得到 {type(source_type)}"
                    assert source_type == "decompiled", f"应该是 'decompiled'，但得到 '{source_type}'"
                    assert "Fernflower decompiled!" in code
    
    def test_return_tuple_from_fernflower_failure(self):
        """测试 Fernflower 反编译失败时返回 (code, source_type) 元组"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # 创建测试 JAR
            test_jar = tmp_path / "test.jar"
            create_test_jar_with_class(test_jar)
            
            decompiler = JavaDecompiler()
            
            # 模拟 Fernflower 反编译失败
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=1, stderr="Decompilation failed", stdout="")
                
                # 强制使用 Fernflower
                with patch.object(decompiler, '_choose_decompiler', 
                                return_value=(decompiler.fernflower_jar, 'fernflower')):
                    result = decompiler.decompile_class(test_jar, "com.test.TestClass")
                    
                    # 验证返回值是元组
                    assert isinstance(result, tuple), f"应该返回元组，但得到 {type(result)}"
                    assert len(result) == 2, f"元组应该有 2 个元素，但得到 {len(result)}"
                    
                    code, source_type = result
                    assert isinstance(code, str), f"code 应该是字符串，但得到 {type(code)}"
                    assert isinstance(source_type, str), f"source_type 应该是字符串，但得到 {type(source_type)}"
                    assert source_type == "decompiled"
                    # 应该返回 fallback 信息
                    assert "反编译" in code or "com.test.TestClass" in code
    
    def test_return_tuple_from_cfr_failure(self):
        """测试 CFR 反编译失败时返回 (code, source_type) 元组"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # 创建测试 JAR
            test_jar = tmp_path / "test.jar"
            create_test_jar_with_class(test_jar)
            
            decompiler = JavaDecompiler()
            
            # 模拟 CFR 反编译失败
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=1, stderr="CFR error", stdout="")
                
                # 强制使用 CFR
                with patch.object(decompiler, '_choose_decompiler', 
                                return_value=(decompiler.cfr_jar, 'cfr')):
                    result = decompiler.decompile_class(test_jar, "com.test.TestClass")
                    
                    # 验证返回值是元组
                    assert isinstance(result, tuple), f"应该返回元组，但得到 {type(result)}"
                    assert len(result) == 2, f"元组应该有 2 个元素，但得到 {len(result)}"
                    
                    code, source_type = result
                    assert isinstance(code, str)
                    assert isinstance(source_type, str)
                    assert source_type == "decompiled"
    
    def test_return_tuple_no_decompiler_available(self):
        """测试没有可用反编译器时返回 (code, source_type) 元组"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # 创建测试 JAR
            test_jar = tmp_path / "test.jar"
            create_test_jar_with_class(test_jar)
            
            decompiler = JavaDecompiler()
            
            # 模拟没有可用的反编译器
            with patch.object(decompiler, '_choose_decompiler', return_value=(None, None)):
                result = decompiler.decompile_class(test_jar, "com.test.TestClass")
                
                # 验证返回值是元组
                assert isinstance(result, tuple), f"应该返回元组，但得到 {type(result)}"
                assert len(result) == 2, f"元组应该有 2 个元素，但得到 {len(result)}"
                
                code, source_type = result
                assert isinstance(code, str)
                assert isinstance(source_type, str)
                assert source_type == "decompiled"
                # 应该包含基本类信息
                assert "com.test.TestClass" in code
    
    def test_unpacking_in_server_context(self):
        """模拟 server.py 中的使用场景，测试解包操作"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # 创建测试 JAR
            test_jar = tmp_path / "test.jar"
            create_test_jar_with_class(test_jar)
            
            # 创建缓存
            cache_dir = tmp_path / "easy-code-reader"
            cache_dir.mkdir(parents=True)
            decompiled_jar = cache_dir / "test.jar"
            
            with zipfile.ZipFile(decompiled_jar, 'w') as zf:
                zf.writestr("com/test/TestClass.java", "public class TestClass { }")
            
            decompiler = JavaDecompiler()
            
            # 模拟 server.py 中的调用方式
            try:
                decompiled_code, source_type = decompiler.decompile_class(
                    test_jar, "com.test.TestClass"
                )
                
                # 如果能成功解包，测试通过
                assert isinstance(decompiled_code, str)
                assert isinstance(source_type, str)
                assert source_type in ["sources.jar", "decompiled", "decompiled_cache"]
                
            except ValueError as e:
                # 如果出现 "too many values to unpack" 错误，测试失败
                pytest.fail(f"解包失败: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
