#!/usr/bin/env python3
"""
演示 Easy JAR Reader 的功能

这个脚本展示如何使用 Easy JAR Reader 从 Maven 依赖中读取源代码。
"""

import asyncio
import json
import tempfile
import zipfile
from pathlib import Path

from easy_jar_reader.server import EasyJarReaderServer


def create_demo_maven_repo():
    """创建一个演示用的 Maven 仓库"""
    tmp_dir = Path(tempfile.mkdtemp())
    maven_repo = tmp_dir / "maven_repo"
    maven_repo.mkdir()
    
    # 创建示例依赖: com.example:demo:1.0.0
    artifact_path = maven_repo / "com" / "example" / "demo" / "1.0.0"
    artifact_path.mkdir(parents=True)
    
    # 创建 JAR 文件
    jar_file = artifact_path / "demo-1.0.0.jar"
    with zipfile.ZipFile(jar_file, 'w') as jar:
        manifest = "Manifest-Version: 1.0\n"
        jar.writestr("META-INF/MANIFEST.MF", manifest)
        
        # 添加简单的字节码
        class_bytes = bytes([0xCA, 0xFE, 0xBA, 0xBE, 0x00, 0x00, 0x00, 0x34]) + b'\x00' * 100
        jar.writestr("com/example/demo/Calculator.class", class_bytes)
    
    # 创建 sources JAR
    sources_jar = artifact_path / "demo-1.0.0-sources.jar"
    with zipfile.ZipFile(sources_jar, 'w') as jar:
        java_source = """package com.example.demo;

/**
 * 一个简单的计算器类
 * 
 * 演示从 Maven sources JAR 中提取源代码
 */
public class Calculator {
    
    /**
     * 加法运算
     * 
     * @param a 第一个数
     * @param b 第二个数
     * @return 两数之和
     */
    public int add(int a, int b) {
        return a + b;
    }
    
    /**
     * 减法运算
     * 
     * @param a 被减数
     * @param b 减数
     * @return 差
     */
    public int subtract(int a, int b) {
        return a - b;
    }
    
    /**
     * 乘法运算
     * 
     * @param a 第一个数
     * @param b 第二个数
     * @return 两数之积
     */
    public int multiply(int a, int b) {
        return a * b;
    }
    
    /**
     * 除法运算
     * 
     * @param a 被除数
     * @param b 除数
     * @return 商
     * @throws ArithmeticException 如果除数为0
     */
    public double divide(int a, int b) {
        if (b == 0) {
            throw new ArithmeticException("除数不能为0");
        }
        return (double) a / b;
    }
}
"""
        jar.writestr("com/example/demo/Calculator.java", java_source)
    
    return maven_repo


async def demo_read_source():
    """演示读取源代码"""
    print("=" * 70)
    print("Easy JAR Reader 功能演示")
    print("=" * 70)
    print()
    
    # 创建演示用的 Maven 仓库
    print("1. 创建演示用的 Maven 仓库...")
    maven_repo = create_demo_maven_repo()
    print(f"   Maven 仓库位置: {maven_repo}")
    print()
    
    # 初始化服务器
    print("2. 初始化 Easy JAR Reader 服务器...")
    server = EasyJarReaderServer(maven_repo_path=str(maven_repo))
    print(f"   可用的反编译器: {list(server.decompiler.available_decompilers.keys())}")
    print()
    
    # 读取源代码
    print("3. 从 sources JAR 中读取 Calculator 类的源代码...")
    result = await server._read_jar_source(
        group_id="com.example",
        artifact_id="demo",
        version="1.0.0",
        class_name="com.example.demo.Calculator",
        prefer_sources=True,
        max_lines=0  # 不限制行数
    )
    
    print()
    print("4. 提取结果:")
    print("-" * 70)
    
    response_data = json.loads(result[0].text)
    print(f"   源码来源: {response_data['source']}")
    print(f"   类名: {response_data['class_name']}")
    print(f"   依赖: {response_data['artifact']}")
    print()
    print("   源代码:")
    print("-" * 70)
    print(response_data['code'])
    print("-" * 70)
    print()
    
    # 测试行数限制
    print("5. 测试行数限制功能（max_lines=10）...")
    result_limited = await server._read_jar_source(
        group_id="com.example",
        artifact_id="demo",
        version="1.0.0",
        class_name="com.example.demo.Calculator",
        prefer_sources=True,
        max_lines=10
    )
    
    response_limited = json.loads(result_limited[0].text)
    print("   前10行内容:")
    print("-" * 70)
    print(response_limited['code'])
    print("-" * 70)
    print()
    
    print("演示完成! ✅")
    print()
    
    # 清理
    import shutil
    shutil.rmtree(maven_repo.parent)


if __name__ == "__main__":
    asyncio.run(demo_read_source())
