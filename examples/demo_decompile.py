#!/usr/bin/env python3
"""
演示反编译功能

这个脚本展示当 sources JAR 不可用时，如何使用反编译器获取源代码。
"""

import asyncio
import json
import tempfile
import zipfile
from pathlib import Path
import subprocess

from easy_jar_reader.server import EasyJarReaderServer


def create_compiled_class_jar():
    """创建一个包含已编译类的 JAR（无 sources）"""
    tmp_dir = Path(tempfile.mkdtemp())
    maven_repo = tmp_dir / "maven_repo"
    maven_repo.mkdir()
    
    # 创建示例依赖
    artifact_path = maven_repo / "com" / "example" / "compiled" / "1.0.0"
    artifact_path.mkdir(parents=True)
    
    # 创建一个简单的 Java 源文件并编译它
    java_source = """
package com.example.compiled;

public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello from compiled class!");
    }
    
    public String greet(String name) {
        return "Hello, " + name + "!";
    }
}
"""
    
    # 创建临时目录来编译
    compile_dir = tmp_dir / "compile"
    compile_dir.mkdir()
    
    # 写入 Java 源文件
    src_dir = compile_dir / "com" / "example" / "compiled"
    src_dir.mkdir(parents=True)
    java_file = src_dir / "HelloWorld.java"
    java_file.write_text(java_source)
    
    # 编译 Java 文件
    try:
        result = subprocess.run(
            ["javac", str(java_file)],
            capture_output=True,
            text=True,
            cwd=compile_dir
        )
        if result.returncode != 0:
            print(f"编译失败: {result.stderr}")
            # 如果编译失败，使用预生成的字节码
            class_bytes = bytes([0xCA, 0xFE, 0xBA, 0xBE, 0x00, 0x00, 0x00, 0x34]) + b'\x00' * 100
            class_file = src_dir / "HelloWorld.class"
            class_file.write_bytes(class_bytes)
    except FileNotFoundError:
        print("javac 未找到，使用简单的字节码")
        class_bytes = bytes([0xCA, 0xFE, 0xBA, 0xBE, 0x00, 0x00, 0x00, 0x34]) + b'\x00' * 100
        class_file = src_dir / "HelloWorld.class"
        class_file.write_bytes(class_bytes)
    
    # 创建 JAR 文件（不包含 sources）
    jar_file = artifact_path / "compiled-1.0.0.jar"
    with zipfile.ZipFile(jar_file, 'w') as jar:
        manifest = "Manifest-Version: 1.0\nMain-Class: com.example.compiled.HelloWorld\n"
        jar.writestr("META-INF/MANIFEST.MF", manifest)
        
        # 添加编译后的 class 文件
        class_file = src_dir / "HelloWorld.class"
        if class_file.exists():
            jar.write(class_file, "com/example/compiled/HelloWorld.class")
    
    return maven_repo, tmp_dir


async def demo_decompilation():
    """演示反编译功能"""
    print("=" * 70)
    print("Easy JAR Reader 反编译功能演示")
    print("=" * 70)
    print()
    
    # 创建演示用的 Maven 仓库
    print("1. 创建包含已编译类的 JAR（无 sources JAR）...")
    maven_repo, tmp_dir = create_compiled_class_jar()
    print(f"   Maven 仓库位置: {maven_repo}")
    print()
    
    # 初始化服务器
    print("2. 初始化 Easy JAR Reader 服务器...")
    server = EasyJarReaderServer(maven_repo_path=str(maven_repo))
    if server.decompiler.fernflower_jar:
        print(f"   Fernflower 反编译器已就绪")
    else:
        print(f"   警告: Fernflower 反编译器不可用")
    print()
    
    # 尝试读取源代码（将使用反编译）
    print("3. 尝试读取 HelloWorld 类（将使用反编译器）...")
    result = await server._read_jar_source(
        group_id="com.example",
        artifact_id="compiled",
        version="1.0.0",
        class_name="com.example.compiled.HelloWorld",
        prefer_sources=True,  # 优先 sources，但不存在时会回退到反编译
        max_lines=0
    )
    
    print()
    print("4. 反编译结果:")
    print("-" * 70)
    
    response_data = json.loads(result[0].text)
    print(f"   源码来源: {response_data['source']}")
    print(f"   类名: {response_data['class_name']}")
    print(f"   依赖: {response_data['artifact']}")
    
    print()
    print("   反编译代码:")
    print("-" * 70)
    print(response_data['code'])
    print("-" * 70)
    print()
    
    print("演示完成! ✅")
    print()
    
    # 清理
    import shutil
    shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    asyncio.run(demo_decompilation())
