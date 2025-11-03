#!/usr/bin/env python3
"""
Easy JAR Reader MCP Server

这是一个 Model Context Protocol (MCP) 服务器，用于从 Maven 依赖中读取 Java 源代码。

主要功能：
- 从 Maven 仓库读取 JAR 包源代码
- 支持从 sources jar 提取源码
- 支持反编译 class 文件
- 自动管理大型响应内容

Example usage with MCP client:
    The server provides the following tools:
    - read_jar_source: 读取 Maven 依赖中的 Java 类源代码
"""

import asyncio
import json
import logging
import os
import zipfile
from pathlib import Path
from typing import Any, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .config import Config
from .decompiler import JavaDecompiler
from .response_manager import ResponseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("easy-jar-reader")


class EasyJarReaderServer:
    """
    Easy JAR Reader MCP 服务器
    
    提供从 Maven 依赖中读取 Java 源代码的功能。
    """
    
    def __init__(self, maven_repo_path: Optional[str] = None):
        """
        初始化 Easy JAR Reader MCP 服务器
        
        参数:
            maven_repo_path: 自定义 Maven 仓库路径（可选）
        """
        logger.info("正在初始化 Easy JAR Reader MCP 服务器...")
        
        # 创建 MCP 服务器实例
        self.server = Server(Config.SERVER_NAME)
        
        # 设置 Maven 仓库路径
        if maven_repo_path:
            Config.set_maven_home(maven_repo_path)
        
        self.maven_home = Config.get_maven_home()
        logger.info(f"Maven 仓库位置: {self.maven_home}")
        
        # 检查 Maven 仓库是否存在
        if not self.maven_home.exists():
            logger.warning(f"在 {self.maven_home} 未找到 Maven 仓库")
        else:
            jar_count = len(list(self.maven_home.rglob("*.jar")))
            logger.info(f"在仓库中找到 {jar_count} 个 JAR 文件")
        
        # 初始化 Java 反编译器
        logger.info("正在初始化 Java 反编译器...")
        self.decompiler = JavaDecompiler()
        logger.info(f"可用的反编译器: {list(self.decompiler.available_decompilers.keys())}")
        
        # 初始化响应管理器
        self.response_manager = ResponseManager()
        
        # 设置 MCP 服务器处理程序
        self.setup_handlers()
        logger.info("Easy JAR Reader MCP 服务器初始化完成!")
    
    def setup_handlers(self):
        """设置 MCP 服务器处理程序"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """列出可用的工具"""
            return [
                Tool(
                    name="read_jar_source",
                    description="从 Maven 依赖中读取 Java 类的源代码（优先从 sources jar，否则反编译）",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string", 
                                "description": "Maven group ID (例如: org.springframework)"
                            },
                            "artifact_id": {
                                "type": "string", 
                                "description": "Maven artifact ID (例如: spring-core)"
                            },
                            "version": {
                                "type": "string", 
                                "description": "Maven version (例如: 5.3.21)"
                            },
                            "class_name": {
                                "type": "string", 
                                "description": "完全限定的类名 (例如: org.springframework.core.SpringVersion)"
                            },
                            "prefer_sources": {
                                "type": "boolean", 
                                "default": True,
                                "description": "优先使用 sources jar 而不是反编译"
                            },
                            "summarize_large_content": {
                                "type": "boolean", 
                                "default": True,
                                "description": "自动摘要大型内容"
                            },
                            "max_lines": {
                                "type": "integer", 
                                "default": 500,
                                "description": "返回的最大行数（0 表示全部）"
                            }
                        },
                        "required": ["group_id", "artifact_id", "version", "class_name"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Any) -> List[TextContent]:
            """处理工具调用"""
            logger.info(f"Tool called: {name} with arguments: {arguments}")
            try:
                if name == "read_jar_source":
                    return await self._read_jar_source(**arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error(f"Error handling tool {name}: {e}", exc_info=True)
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _read_jar_source(self, group_id: str, artifact_id: str, version: str,
                              class_name: str, prefer_sources: bool = True,
                              summarize_large_content: bool = True, 
                              max_lines: int = 500) -> List[TextContent]:
        """
        从 jar 中提取源代码或反编译
        
        参数:
            group_id: Maven group ID
            artifact_id: Maven artifact ID
            version: Maven version
            class_name: 完全限定的类名
            prefer_sources: 优先使用 sources jar
            summarize_large_content: 自动摘要大型内容
            max_lines: 最大行数（0 表示全部）
        """
        # 首先尝试从 sources jar 提取
        if prefer_sources:
            sources_jar = self._get_sources_jar_path(group_id, artifact_id, version)
            if sources_jar and sources_jar.exists():
                source_code = self._extract_from_sources_jar(sources_jar, class_name)
                if source_code:
                    # 限制行数
                    if max_lines > 0:
                        lines = source_code.split('\n')
                        if len(lines) > max_lines:
                            source_code = '\n'.join(lines[:max_lines])
                            source_code += f"\n\n// ... 省略 {len(lines) - max_lines} 行 ..."
                            source_code += f"\n// 使用 max_lines=0 参数获取完整内容"
                    
                    result = {
                        "source": "sources-jar",
                        "class_name": class_name,
                        "artifact": f"{group_id}:{artifact_id}:{version}",
                        "code": source_code
                    }
                    
                    if summarize_large_content and self.response_manager.should_summarize(result["code"]):
                        result["code"] = self.response_manager.summarize_large_text(result["code"])
                        result["summarized"] = True
                    
                    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
        
        # 回退到反编译
        jar_path = self._get_jar_path(group_id, artifact_id, version)
        if not jar_path or not jar_path.exists():
            return [TextContent(
                type="text", 
                text=f"未找到 JAR 文件: {group_id}:{artifact_id}:{version}\n" +
                     f"请确认 Maven 仓库路径正确: {self.maven_home}"
            )]
        
        try:
            decompiled_code = self.decompiler.decompile_class(jar_path, class_name)
            
            # 限制行数
            if max_lines > 0 and decompiled_code:
                lines = decompiled_code.split('\n')
                if len(lines) > max_lines:
                    decompiled_code = '\n'.join(lines[:max_lines])
                    decompiled_code += f"\n\n// ... 省略 {len(lines) - max_lines} 行 ..."
                    decompiled_code += f"\n// 使用 max_lines=0 参数获取完整内容"
            
            result = {
                "source": "decompiled",
                "class_name": class_name,
                "artifact": f"{group_id}:{artifact_id}:{version}",
                "code": decompiled_code or "反编译失败",
                "available_decompilers": list(self.decompiler.available_decompilers.keys())
            }
            
            if summarize_large_content and decompiled_code and self.response_manager.should_summarize(result["code"]):
                result["code"] = self.response_manager.summarize_large_text(result["code"])
                result["summarized"] = True
            
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
            
        except Exception as e:
            logger.error(f"Error extracting source code: {e}", exc_info=True)
            return [TextContent(type="text", text=f"提取源代码时出错: {str(e)}")]
    
    def _get_jar_path(self, group_id: str, artifact_id: str, version: str) -> Optional[Path]:
        """获取 jar 文件路径"""
        group_path = group_id.replace('.', os.sep)
        jar_dir = self.maven_home / group_path / artifact_id / version
        
        # 查找主 jar 文件
        main_jar = jar_dir / f"{artifact_id}-{version}.jar"
        if main_jar.exists():
            return main_jar
        
        # 查找目录中的任何 jar 文件
        if jar_dir.exists():
            jar_files = [f for f in jar_dir.glob("*.jar") 
                        if not f.name.endswith('-sources.jar') 
                        and not f.name.endswith('-javadoc.jar')]
            if jar_files:
                return jar_files[0]
        
        return None
    
    def _get_sources_jar_path(self, group_id: str, artifact_id: str, version: str) -> Optional[Path]:
        """获取 sources jar 文件路径"""
        group_path = group_id.replace('.', os.sep)
        jar_dir = self.maven_home / group_path / artifact_id / version
        sources_jar = jar_dir / f"{artifact_id}-{version}-sources.jar"
        return sources_jar if sources_jar.exists() else None
    
    def _extract_from_sources_jar(self, sources_jar: Path, class_name: str) -> Optional[str]:
        """从 sources jar 中提取源代码"""
        try:
            java_file = class_name.replace('.', '/') + '.java'
            with zipfile.ZipFile(sources_jar, 'r') as jar:
                if java_file in jar.namelist():
                    return jar.read(java_file).decode('utf-8', errors='ignore')
        except Exception as e:
            logger.warning(f"从 sources jar 提取失败: {e}")
        return None
    
    async def run(self):
        """运行 MCP 服务器"""
        logger.info("Starting Easy JAR Reader MCP Server...")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main(maven_repo_path: Optional[str] = None):
    """
    运行 MCP 服务器
    
    参数:
        maven_repo_path: 自定义 Maven 仓库路径（可选）
    """
    server = EasyJarReaderServer(maven_repo_path=maven_repo_path)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
