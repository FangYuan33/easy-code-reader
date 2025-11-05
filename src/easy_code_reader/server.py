#!/usr/bin/env python3
"""
Easy Code Reader MCP Server

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
import zipfile
from pathlib import Path
from typing import Any, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .config import Config
from .decompiler import JavaDecompiler
from .response_manager import ResponseManager

# 配置日志系统
import os
log_file = os.path.join(os.path.dirname(__file__), "easy_code_reader.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # 写入日志文件
        logging.FileHandler(log_file),
        # 同时输出到控制台（非 MCP 服务器模式时）
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EasyCodeReaderServer:
    """
    Easy Code Reader MCP 服务器
    
    提供从 Maven 依赖中读取 Java 源代码的功能。
    """
    
    def __init__(self, maven_repo_path: Optional[str] = None, project_dir: Optional[str] = None):
        """
        初始化 Easy Code Reader MCP 服务器
        
        参数:
            maven_repo_path: 自定义 Maven 仓库路径（可选）
            project_dir: 项目目录路径（可选）
        """
        logger.info("正在初始化 Easy Code Reader MCP 服务器...")
        
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
        
        # 设置项目目录路径
        self.project_dir = Path(project_dir) if project_dir else None
        if self.project_dir:
            logger.info(f"项目目录位置: {self.project_dir}")
            if not self.project_dir.exists():
                logger.warning(f"在 {self.project_dir} 未找到项目目录")
        
        # 初始化 Java 反编译器
        logger.info("正在初始化 Java 反编译器...")
        self.decompiler = JavaDecompiler()
        if self.decompiler.fernflower_jar:
            logger.info(f"Fernflower 反编译器已就绪")
        else:
            logger.warning("Fernflower 反编译器不可用")
        
        # 初始化响应管理器
        self.response_manager = ResponseManager()
        
        # 设置 MCP 服务器处理程序
        self.setup_handlers()
        logger.info("Easy Code Reader MCP 服务器初始化完成!")
    
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
                            }
                        },
                        "required": ["group_id", "artifact_id", "version", "class_name"]
                    }
                ),
                Tool(
                    name="read_project_code",
                    description="从本地项目目录中读取指定项目的代码类源代码",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_name": {
                                "type": "string",
                                "description": "项目名称（例如: my-project）"
                            },
                            "class_name": {
                                "type": "string",
                                "description": "完全限定的类名或相对路径（例如: com.example.MyClass 或 src/main/java/com/example/MyClass.java）"
                            },
                            "project_dir": {
                                "type": "string",
                                "description": "项目目录路径（可选，如果未提供则使用启动时配置的路径）"
                            }
                        },
                        "required": ["project_name", "class_name"]
                    }
                ),
                Tool(
                    name="list_all_project",
                    description="列举项目目录下所有的项目文件夹名称",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_dir": {
                                "type": "string",
                                "description": "项目目录路径（可选，如果未提供则使用启动时配置的路径）"
                            }
                        },
                        "required": []
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
                elif name == "read_project_code":
                    return await self._read_project_code(**arguments)
                elif name == "list_all_project":
                    return await self._list_all_project(**arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error(f"Error handling tool {name}: {e}", exc_info=True)
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _read_jar_source(self, group_id: str, artifact_id: str, version: str,
                              class_name: str, prefer_sources: bool = True) -> List[TextContent]:
        """
        从 jar 中提取源代码或反编译
        
        参数:
            group_id: Maven group ID
            artifact_id: Maven artifact ID
            version: Maven version
            class_name: 完全限定的类名
            prefer_sources: 优先使用 sources jar
        """
        # 输入验证
        if not group_id or not group_id.strip():
            return [TextContent(type="text", text="错误: group_id 不能为空")]
        if not artifact_id or not artifact_id.strip():
            return [TextContent(type="text", text="错误: artifact_id 不能为空")]
        if not version or not version.strip():
            return [TextContent(type="text", text="错误: version 不能为空")]
        if not class_name or not class_name.strip():
            return [TextContent(type="text", text="错误: class_name 不能为空")]
        
        # 首先尝试从 sources jar 提取
        if prefer_sources:
            sources_jar = self._get_sources_jar_path(group_id, artifact_id, version)
            if sources_jar and sources_jar.exists():
                source_code = self._extract_from_sources_jar(sources_jar, class_name)
                if source_code:
                    result = {
                        "class_name": class_name,
                        "artifact": f"{group_id}:{artifact_id}:{version}",
                        "code": source_code
                    }
                    
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
            
            result = {
                "class_name": class_name,
                "artifact": f"{group_id}:{artifact_id}:{version}",
                "code": decompiled_code or "反编译失败"
            }
            
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
            
        except Exception as e:
            logger.error(f"Error extracting source code: {e}", exc_info=True)
            return [TextContent(type="text", text=f"提取源代码时出错: {str(e)}")]
    
    async def _read_project_code(self, project_name: str, class_name: str, 
                                 project_dir: Optional[str] = None) -> List[TextContent]:
        """
        从本地项目目录中读取代码
        
        参数:
            project_name: 项目名称
            class_name: 完全限定的类名或相对路径
            project_dir: 项目目录路径（可选）
        """
        # 输入验证
        if not project_name or not project_name.strip():
            return [TextContent(type="text", text="错误: project_name 不能为空")]
        if not class_name or not class_name.strip():
            return [TextContent(type="text", text="错误: class_name 不能为空")]
        
        # 确定使用的项目目录
        target_dir = None
        if project_dir:
            target_dir = Path(project_dir)
        elif self.project_dir:
            target_dir = self.project_dir
        else:
            return [TextContent(type="text", text="错误: 项目目录信息为空，请在启动时使用 --project-dir 参数或在调用时传入 project_dir 参数")]
        
        # 检查项目目录是否存在
        if not target_dir.exists():
            return [TextContent(type="text", text=f"错误: 项目目录不存在: {target_dir}")]
        
        # 检查项目是否存在
        project_path = target_dir / project_name
        if not project_path.exists() or not project_path.is_dir():
            return [TextContent(
                type="text", 
                text=f"错误: {project_name} 项目不存在，请执行 list_all_project tool 检查项目是否存在"
            )]
        
        # 尝试查找文件
        # 1. 如果 class_name 看起来像是路径（包含 / 或常见文件扩展名），直接使用
        if '/' in class_name or class_name.endswith('.java') or class_name.endswith('.kt'):
            file_path = project_path / class_name
            if file_path.exists() and file_path.is_file():
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        code = f.read()
                    result = {
                        "project_name": project_name,
                        "class_name": class_name,
                        "file_path": str(file_path),
                        "code": code
                    }
                    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
                except Exception as e:
                    logger.error(f"Error reading file: {e}", exc_info=True)
                    return [TextContent(type="text", text=f"读取文件时出错: {str(e)}")]
        
        # 2. 将类名转换为路径，搜索可能的源文件
        # 支持 Java 类名格式: com.example.MyClass -> com/example/MyClass.java
        class_path = class_name.replace('.', '/')
        
        # 常见的源代码路径模式
        search_patterns = [
            f"src/main/java/{class_path}.java",
            f"src/{class_path}.java",
            f"{class_path}.java",
            f"src/main/kotlin/{class_path}.kt",
            f"src/{class_path}.kt",
            f"{class_path}.kt",
        ]
        
        # 尝试各种路径模式
        for pattern in search_patterns:
            file_path = project_path / pattern
            if file_path.exists() and file_path.is_file():
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        code = f.read()
                    result = {
                        "project_name": project_name,
                        "class_name": class_name,
                        "file_path": str(file_path),
                        "code": code
                    }
                    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
                except Exception as e:
                    logger.error(f"Error reading file: {e}", exc_info=True)
                    return [TextContent(type="text", text=f"读取文件时出错: {str(e)}")]
        
        # 如果找不到文件，返回错误信息
        return [TextContent(
            type="text",
            text=f"错误: 在项目 {project_name} 中未找到类 {class_name}，尝试的路径包括: {', '.join(search_patterns)}"
        )]
    
    async def _list_all_project(self, project_dir: Optional[str] = None) -> List[TextContent]:
        """
        列举项目目录下所有的项目文件夹
        
        参数:
            project_dir: 项目目录路径（可选）
        """
        # 确定使用的项目目录
        target_dir = None
        if project_dir:
            target_dir = Path(project_dir)
        elif self.project_dir:
            target_dir = self.project_dir
        else:
            return [TextContent(type="text", text="错误: 项目目录信息为空，请在启动时使用 --project-dir 参数或在调用时传入 project_dir 参数")]
        
        # 检查项目目录是否存在
        if not target_dir.exists():
            return [TextContent(type="text", text=f"错误: 项目目录不存在: {target_dir}")]
        
        # 获取所有子目录（项目）
        try:
            projects = [d.name for d in target_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
            projects.sort()
            
            result = {
                "project_dir": str(target_dir),
                "project_count": len(projects),
                "projects": projects
            }
            
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
        except Exception as e:
            logger.error(f"Error listing projects: {e}", exc_info=True)
            return [TextContent(type="text", text=f"列举项目时出错: {str(e)}")]
    
    def _get_jar_path(self, group_id: str, artifact_id: str, version: str) -> Optional[Path]:
        """获取 jar 文件路径"""
        group_path = group_id.replace('.', os.sep)
        jar_dir = self.maven_home / group_path / artifact_id / version
        
        # 对于 SNAPSHOT 版本，优先使用带时间戳的版本
        if version.endswith('-SNAPSHOT'):
            if jar_dir.exists():
                # 查找带时间戳的 jar 文件，格式如: artifact-1.0.0-20251030.085053-1.jar
                # 排除 sources 和 javadoc jar
                timestamped_jars = [
                    f for f in jar_dir.glob(f"{artifact_id}-*.jar")
                    if not f.name.endswith('-sources.jar')
                    and not f.name.endswith('-javadoc.jar')
                    and not f.name.endswith('-SNAPSHOT.jar')
                    and f.name.startswith(artifact_id)
                ]
                
                if timestamped_jars:
                    # 按文件名排序，获取最新的（时间戳最大的）
                    timestamped_jars.sort(reverse=True)
                    logger.info(f"找到 SNAPSHOT 带时间戳的 jar: {timestamped_jars[0]}")
                    return timestamped_jars[0]
        
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
        
        # 对于 SNAPSHOT 版本，优先使用带时间戳的 sources jar
        if version.endswith('-SNAPSHOT'):
            if jar_dir.exists():
                # 查找带时间戳的 sources jar 文件
                timestamped_sources = [
                    f for f in jar_dir.glob(f"{artifact_id}-*-sources.jar")
                    if not f.name.endswith('-SNAPSHOT-sources.jar')
                ]
                
                if timestamped_sources:
                    # 按文件名排序，获取最新的
                    timestamped_sources.sort(reverse=True)
                    logger.info(f"找到 SNAPSHOT 带时间戳的 sources jar: {timestamped_sources[0]}")
                    return timestamped_sources[0]
        
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
        logger.info("Starting Easy Code Reader MCP Server...")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main(maven_repo_path: Optional[str] = None, project_dir: Optional[str] = None):
    """
    运行 MCP 服务器
    
    参数:
        maven_repo_path: 自定义 Maven 仓库路径（可选）
        project_dir: 项目目录路径（可选）
    """
    server = EasyCodeReaderServer(maven_repo_path=maven_repo_path, project_dir=project_dir)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
