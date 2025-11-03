#!/usr/bin/env python3
"""
Maven Decoder MCP Server - Maven JAR 文件分析 MCP 服务器

这是一个用于分析本地 Maven 仓库（~/.m2）中 JAR 文件的 MCP 服务器。
为 Java 项目的智能代码辅助提供全面的工具支持。

主要功能：
- 分析 Maven JAR 文件结构和内容
- 提取 Java 类信息和方法签名
- 反编译字节码获取源代码
- 分析 Maven 依赖关系
- 搜索和查找类文件
- 版本比较和依赖树分析
"""

import asyncio
import json
import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging
import tempfile
import subprocess
import re

# MCP 服务器相关导入
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel,
    ServerCapabilities,
    ToolsCapability
)
from pydantic import BaseModel
import xmltodict

# 导入自定义模块
from .decompiler import JavaDecompiler
from .maven_analyzer import MavenDependencyAnalyzer

# 配置日志系统
import os
log_file = os.path.join(os.path.dirname(__file__), "maven_decoder_server.log")
logging.basicConfig(
    level=logging.INFO,  # 设置为 INFO 级别
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),  # 写入日志文件
        logging.StreamHandler()  # 同时输出到控制台（非 MCP 服务器模式时）
    ]
)
logger = logging.getLogger(__name__)

class ResponseManager:
    """
    响应管理器 - 管理大型响应的分页和摘要功能
    
    该类负责处理可能很大的响应数据，通过分页和内容摘要来确保
    响应大小在合理范围内，避免超出 MCP 协议的限制。
    
    主要功能：
    - 自动分页处理大量数据
    - 智能摘要长文本内容
    - 响应大小控制和优化
    """
    
    def __init__(self, max_response_size: Optional[int] = None, max_items_per_page: Optional[int] = None,
                 max_text_length: Optional[int] = None, max_lines: Optional[int] = None):
        """
        初始化响应管理器
        
        参数:
            max_response_size: 最大响应大小（字节），默认 50000
            max_items_per_page: 每页最大项目数，默认 20
            max_text_length: 最大文本长度，默认 10000
            max_lines: 最大行数，默认 500
        """
        self.max_response_size = max_response_size or int(os.getenv('MCP_MAX_RESPONSE_SIZE', '50000'))
        self.max_items_per_page = max_items_per_page or int(os.getenv('MCP_MAX_ITEMS_PER_PAGE', '20'))
        self.max_text_length = max_text_length or int(os.getenv('MCP_MAX_TEXT_LENGTH', '10000'))
        self.max_lines = max_lines or int(os.getenv('MCP_MAX_LINES', '500'))
    
    def paginate_response(self, data: Dict[str, Any], page: int = 1,
                         items_per_page: Optional[int] = None) -> Dict[str, Any]:
        """
        分页响应数据
        
        将包含大量项目的响应数据进行分页处理，避免一次性返回过多数据。
        支持多种数据结构：classes、matches、dependencies 等。
        
        参数:
            data: 要分页的数据字典
            page: 页码（从1开始）
            items_per_page: 每页项目数，默认使用配置值
            
        返回:
            包含分页信息的数据字典，包括分页元数据
        """
        if items_per_page is None:
            items_per_page = self.max_items_per_page
        
        # 处理不同的数据结构
        if 'classes' in data:
            items = data['classes']
            key = 'classes'
        elif 'matches' in data:
            items = data['matches']
            key = 'matches'
        elif 'dependencies' in data:
            items = data['dependencies']
            key = 'dependencies'
        else:
            # 如果没有已知结构，直接返回原数据
            return data
        
        # 计算分页参数
        total_items = len(items)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        
        # 提取当前页的项目
        paginated_items = items[start_idx:end_idx]
        
        # 构建分页响应
        result = data.copy()
        result[key] = paginated_items
        result['pagination'] = {
            'page': page,
            'total_pages': total_pages,
            'items_per_page': items_per_page,
            'total_items': total_items,
            'showing_items': f"{start_idx + 1}-{min(end_idx, total_items)}"
        }
        
        return result
    
    def summarize_large_text(self, text: str, max_length: Optional[int] = None) -> str:
        """
        摘要大型文本内容
        
        对于过长的文本（特别是 Java 源代码），生成智能摘要以保留关键信息。
        优先保留包声明、导入语句、类声明、方法签名和结束部分。
        
        参数:
            text: 要摘要的文本内容
            max_length: 最大长度限制，默认使用配置值
            
        返回:
            摘要后的文本，如果原文本不超长则返回原文本
        """
        if max_length is None:
            max_length = self.max_text_length
            
        if len(text) <= max_length:
            return text
        
        # 对于 Java 代码，尝试保留重要部分
        lines = text.split('\n')
        if len(lines) <= self.max_lines:
            return text
        
        # 保留前20行（通常是包声明、导入、类声明）
        # 保留后10行（通常是结束大括号）
        # 保留中间的方法签名
        summary_lines = []
        
        # 添加摘要头部信息
        summary_lines.append("// 摘要: 大型类内容（显示关键部分）")
        summary_lines.append(f"// 总行数: {len(lines)}")
        summary_lines.append("// 显示内容: 包声明/导入、方法签名、结束大括号")
        summary_lines.append("")
        
        # 添加前20行
        summary_lines.extend(lines[:20])
        
        # 查找方法签名（包含 public/private/protected 的行）
        method_lines = []
        for i, line in enumerate(lines[20:-10]):
            stripped = line.strip()
            if (re.match(r'^\s*(public|private|protected|static|final)\s+', stripped) and
                '(' in stripped and ')' in stripped and
                not stripped.startswith('//') and not stripped.startswith('/*')):
                method_lines.append((i + 20, line))
        
        # 添加一些方法签名（最多10个）
        if method_lines:
            summary_lines.append("")
            summary_lines.append("// ... 关键方法签名 ...")
            for idx, line in method_lines[:10]:
                summary_lines.append(f"// 第 {idx + 1} 行: {line.strip()}")
        
        # 添加结束大括号
        summary_lines.append("")
        summary_lines.append("// ... 结束大括号 ...")
        summary_lines.extend(lines[-10:])
        
        summary_lines.append("")
        summary_lines.append(f"// 使用分页或特定方法提取获取完整内容")
        
        return '\n'.join(summary_lines)
    
    def should_paginate(self, data: Dict[str, Any]) -> bool:
        """
        检查响应是否应该分页
        
        参数:
            data: 要检查的数据字典
            
        返回:
            如果响应大小超过限制则返回 True
        """
        response_str = json.dumps(data, indent=2)
        return len(response_str) > self.max_response_size
    
    def should_summarize(self, text: str) -> bool:
        """
        检查文本是否应该摘要
        
        参数:
            text: 要检查的文本
            
        返回:
            如果文本长度超过限制则返回 True
        """
        return len(text) > self.max_text_length

class MavenDecoderServer:
    """
    Maven JAR 文件分析 MCP 服务器
    
    这是 Maven Decoder MCP 服务器的主类，提供了完整的 Maven JAR 文件分析功能。
    它集成了反编译器、依赖分析器和响应管理器，为客户端提供丰富的工具集。
    
    主要组件：
    - MCP 服务器核心：处理客户端请求和响应
    - Java 反编译器：将字节码反编译为源代码
    - Maven 依赖分析器：分析项目依赖关系
    - 响应管理器：处理大型响应的分页和摘要
    
    支持的操作：
    - 列出 Maven 构件
    - 分析 JAR 文件结构
    - 提取类信息和方法签名
    - 获取依赖关系
    - 搜索类文件
    - 提取源代码
    """
    
    def __init__(self):
        """
        初始化 Maven Decoder MCP 服务器
        
        设置所有必要的组件，包括：
        - MCP 服务器实例
        - Maven 仓库路径检测
        - Java 反编译器初始化
        - 依赖分析器初始化
        - 响应管理器配置
        """
        logger.info("正在初始化 Maven Decoder MCP 服务器...")
        
        # 创建 MCP 服务器实例
        self.server = Server("maven-decoder")
        
        # 设置 Maven 仓库路径（通常在用户主目录的 .m2/repository）
        self.maven_home = Path.home() / ".m2" / "repository"
        
        # 初始化响应管理器
        self.response_manager = ResponseManager()
        
        logger.info(f"Maven 仓库位置: {self.maven_home}")
        
        # 检查 Maven 仓库是否存在并统计文件数量
        if not self.maven_home.exists():
            logger.warning(f"在 {self.maven_home} 未找到 Maven 仓库")
        else:
            # 统计构件数量以提供信息
            jar_count = len(list(self.maven_home.rglob("*.jar")))
            pom_count = len(list(self.maven_home.rglob("*.pom")))
            logger.info(f"在仓库中找到 {jar_count} 个 JAR 文件和 {pom_count} 个 POM 文件")
        
        # 初始化 Java 反编译器
        logger.info("正在初始化 Java 反编译器...")
        self.decompiler = JavaDecompiler()
        logger.info(f"可用的反编译器: {list(self.decompiler.available_decompilers.keys())}")
        
        # 初始化 Maven 依赖分析器
        logger.info("正在初始化 Maven 依赖分析器...")
        self.dependency_analyzer = MavenDependencyAnalyzer(self.maven_home)
        
        # 设置 MCP 服务器处理程序
        logger.info("正在设置 MCP 服务器处理程序...")
        self.setup_handlers()
        logger.info("Maven Decoder MCP 服务器初始化完成!")
    
    def setup_handlers(self):
        """
        设置 MCP 服务器处理程序
        
        注册所有可用的工具和处理函数，包括：
        - 工具列表处理程序
        - 工具调用处理程序
        - 各种 Maven 分析工具的实现
        """
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools for Maven jar analysis"""
            logger.info("MCP client requested tool list")
            tools = [
                Tool(
                    name="list_artifacts",
                    description="List all Maven artifacts in the local repository with optional filtering",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string", "description": "Filter by group ID (e.g., 'org.springframework')"},
                            "artifact_id": {"type": "string", "description": "Filter by artifact ID (e.g., 'spring-core')"},
                            "version": {"type": "string", "description": "Filter by version (e.g., '5.3.21')"},
                            "limit": {"type": "integer", "default": 50, "description": "Maximum number of artifacts to return"},
                            "page": {"type": "integer", "default": 1, "description": "Page number for pagination"},
                            "items_per_page": {"type": "integer", "default": 20, "description": "Items per page"}
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="analyze_jar",
                    description="Analyze a specific jar file and extract detailed information",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string", "description": "Maven group ID"},
                            "artifact_id": {"type": "string", "description": "Maven artifact ID"},
                            "version": {"type": "string", "description": "Maven version"},
                            "include_bytecode": {"type": "boolean", "default": False, "description": "Include bytecode analysis"},
                            "include_manifest": {"type": "boolean", "default": True, "description": "Include JAR manifest"},
                            "summarize_large_content": {"type": "boolean", "default": True, "description": "Summarize large content automatically"}
                        },
                        "required": ["group_id", "artifact_id", "version"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="extract_class_info",
                    description="Get detailed information about Java classes in a jar",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string", "description": "Maven group ID"},
                            "artifact_id": {"type": "string", "description": "Maven artifact ID"},
                            "version": {"type": "string", "description": "Maven version"},
                            "class_pattern": {"type": "string", "description": "Pattern to match class names (regex supported)"},
                            "include_methods": {"type": "boolean", "default": True, "description": "Include method signatures"},
                            "include_fields": {"type": "boolean", "default": True, "description": "Include field information"},
                            "page": {"type": "integer", "default": 1, "description": "Page number for pagination"},
                            "items_per_page": {"type": "integer", "default": 20, "description": "Items per page"},
                            "summarize_large_content": {"type": "boolean", "default": True, "description": "Summarize large content automatically"}
                        },
                        "required": ["group_id", "artifact_id", "version"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="get_dependencies",
                    description="Get Maven dependencies from POM files",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string", "description": "Maven group ID"},
                            "artifact_id": {"type": "string", "description": "Maven artifact ID"},
                            "version": {"type": "string", "description": "Maven version"},
                            "include_transitive": {"type": "boolean", "default": False, "description": "Include transitive dependencies"},
                            "page": {"type": "integer", "default": 1, "description": "Page number for pagination"},
                            "items_per_page": {"type": "integer", "default": 20, "description": "Items per page"}
                        },
                        "required": ["group_id", "artifact_id", "version"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="search_classes",
                    description="Search for Java classes across all jars in the repository",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "class_name": {"type": "string", "description": "Class name to search for (supports wildcards)"},
                            "package_pattern": {"type": "string", "description": "Package pattern to filter by"},
                            "annotation": {"type": "string", "description": "Search for classes with specific annotation"},
                            "limit": {"type": "integer", "default": 100, "description": "Maximum results to return"},
                            "page": {"type": "integer", "default": 1, "description": "Page number for pagination"},
                            "items_per_page": {"type": "integer", "default": 20, "description": "Items per page"}
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="extract_source_code",
                    description="Extract source code from jar (if available) or decompile bytecode",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string", "description": "Maven group ID"},
                            "artifact_id": {"type": "string", "description": "Maven artifact ID"},
                            "version": {"type": "string", "description": "Maven version"},
                            "class_name": {"type": "string", "description": "Fully qualified class name"},
                            "prefer_sources": {"type": "boolean", "default": True, "description": "Prefer source jar over decompilation"},
                            "summarize_large_content": {"type": "boolean", "default": True, "description": "Summarize large content automatically"},
                            "max_lines": {"type": "integer", "default": 500, "description": "Maximum lines to return (0 for all)"}
                        },
                        "required": ["group_id", "artifact_id", "version", "class_name"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="compare_versions",
                    description="Compare different versions of the same Maven artifact",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string", "description": "Maven group ID"},
                            "artifact_id": {"type": "string", "description": "Maven artifact ID"},
                            "version1": {"type": "string", "description": "First version to compare"},
                            "version2": {"type": "string", "description": "Second version to compare"},
                            "compare_api": {"type": "boolean", "default": True, "description": "Compare public API changes"},
                            "summarize_large_content": {"type": "boolean", "default": True, "description": "Summarize large content automatically"}
                        },
                        "required": ["group_id", "artifact_id", "version1", "version2"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="find_usage_examples",
                    description="Find usage examples of classes/methods in test jars",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "class_name": {"type": "string", "description": "Class name to find usage for"},
                            "method_name": {"type": "string", "description": "Method name to find usage for"},
                            "search_tests": {"type": "boolean", "default": True, "description": "Search in test jars"},
                            "limit": {"type": "integer", "default": 50, "description": "Maximum results to return"},
                            "page": {"type": "integer", "default": 1, "description": "Page number for pagination"},
                            "items_per_page": {"type": "integer", "default": 20, "description": "Items per page"}
                        },
                        "required": ["class_name"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="get_dependency_tree",
                    description="Get complete dependency tree for an artifact",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string", "description": "Maven group ID"},
                            "artifact_id": {"type": "string", "description": "Maven artifact ID"},
                            "version": {"type": "string", "description": "Maven version"},
                            "max_depth": {"type": "integer", "default": 3, "description": "Maximum depth to show"},
                            "summarize_large_content": {"type": "boolean", "default": True, "description": "Summarize large content automatically"}
                        },
                        "required": ["group_id", "artifact_id", "version"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="find_dependents",
                    description="Find artifacts that depend on a specific artifact",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string", "description": "Target group ID"},
                            "artifact_id": {"type": "string", "description": "Target artifact ID"},
                            "version": {"type": "string", "description": "Specific version to search for (optional)"},
                            "limit": {"type": "integer", "default": 100, "description": "Maximum results to return"},
                            "page": {"type": "integer", "default": 1, "description": "Page number for pagination"},
                            "items_per_page": {"type": "integer", "default": 20, "description": "Items per page"}
                        },
                        "required": ["group_id", "artifact_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="get_version_info",
                    description="Get all available versions of an artifact",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string", "description": "Maven group ID"},
                            "artifact_id": {"type": "string", "description": "Maven artifact ID"},
                            "limit": {"type": "integer", "default": 50, "description": "Maximum versions to return"},
                            "page": {"type": "integer", "default": 1, "description": "Page number for pagination"},
                            "items_per_page": {"type": "integer", "default": 20, "description": "Items per page"}
                        },
                        "required": ["group_id", "artifact_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="analyze_jar_structure",
                    description="Analyze the overall structure and metadata of a jar file",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string", "description": "Maven group ID"},
                            "artifact_id": {"type": "string", "description": "Maven artifact ID"},
                            "version": {"type": "string", "description": "Maven version"},
                            "summarize_large_content": {"type": "boolean", "default": True, "description": "Summarize large content automatically"}
                        },
                        "required": ["group_id", "artifact_id", "version"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="extract_method_info",
                    description="Extract specific method information from a Java class",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string", "description": "Maven group ID"},
                            "artifact_id": {"type": "string", "description": "Maven artifact ID"},
                            "version": {"type": "string", "description": "Maven version"},
                            "class_name": {"type": "string", "description": "Fully qualified class name"},
                            "method_pattern": {"type": "string", "description": "Pattern to match method names (regex supported)"},
                            "include_bytecode": {"type": "boolean", "default": False, "description": "Include bytecode analysis"},
                            "max_methods": {"type": "integer", "default": 10, "description": "Maximum number of methods to return"}
                        },
                        "required": ["group_id", "artifact_id", "version", "class_name"],
                        "additionalProperties": False
                    }
                )
            ]
            logger.info(f"Registered {len(tools)} tools: {[tool.name for tool in tools]}")
            return tools
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            logger.info(f"Tool called: {name} with arguments: {arguments}")
            try:
                if name == "list_artifacts":
                    return await self._list_artifacts(**arguments)
                elif name == "analyze_jar":
                    return await self._analyze_jar(**arguments)
                elif name == "extract_class_info":
                    return await self._extract_class_info(**arguments)
                elif name == "get_dependencies":
                    return await self._get_dependencies(**arguments)
                elif name == "search_classes":
                    return await self._search_classes(**arguments)
                elif name == "extract_source_code":
                    return await self._extract_source_code(**arguments)
                elif name == "compare_versions":
                    return await self._compare_versions(**arguments)
                elif name == "find_usage_examples":
                    return await self._find_usage_examples(**arguments)
                elif name == "get_dependency_tree":
                    return await self._get_dependency_tree(**arguments)
                elif name == "find_dependents":
                    return await self._find_dependents(**arguments)
                elif name == "get_version_info":
                    return await self._get_version_info(**arguments)
                elif name == "analyze_jar_structure":
                    return await self._analyze_jar_structure(**arguments)
                elif name == "extract_method_info":
                    return await self._extract_method_info(**arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error(f"Error handling tool {name}: {e}", exc_info=True)
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _list_artifacts(self, group_id: Optional[str] = None, 
                            artifact_id: Optional[str] = None, 
                            version: Optional[str] = None, 
                            limit: int = 50, page: int = 1, items_per_page: int = 20) -> List[TextContent]:
        """List Maven artifacts with optional filtering"""
        logger.debug(f"Listing artifacts with filters: group_id={group_id}, artifact_id={artifact_id}, version={version}, limit={limit}, page={page}, items_per_page={items_per_page}")
        artifacts = []
        count = 0
        
        try:
            logger.debug(f"Scanning Maven repository: {self.maven_home}")
            group_dirs = [p for p in self.maven_home.iterdir() if p.is_dir()]
            logger.debug(f"Found {len(group_dirs)} top-level directories")
            
            for group_path in group_dirs:
                group_name = group_path.name
                if group_id and group_id not in group_name:
                    continue
                
                # Look for artifact directories within this group
                for artifact_dir in group_path.iterdir():
                    if not artifact_dir.is_dir():
                        continue
                    
                    artifact_name = artifact_dir.name
                    if artifact_id and artifact_id not in artifact_name:
                        continue
                    
                    # Look for version directories within this artifact
                    for version_dir in artifact_dir.iterdir():
                        if not version_dir.is_dir():
                            continue
                        
                        version_name = version_dir.name
                        if version and version not in version_name:
                            continue
                        
                        # Check if this version directory contains jar files
                        jar_files = list(version_dir.glob("*.jar"))
                        if jar_files:
                            artifacts.append({
                                "group_id": self._path_to_group_id(group_path),
                                "artifact_id": artifact_name,
                                "version": version_name,
                                "jar_files": [f.name for f in jar_files],
                                "path": str(version_dir)
                            })
                            count += 1
                            if count >= limit:
                                break
                    
                    if count >= limit:
                        break
                    
                    if count >= limit:
                        break
                if count >= limit:
                    break
            
            result = {
                "total_found": count,
                "artifacts": artifacts[:limit]
            }
            
            logger.info(f"Found {count} artifacts matching criteria")
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error listing artifacts: {str(e)}")]
    
    def _path_to_group_id(self, path: Path) -> str:
        """Convert file path to Maven group ID"""
        relative = path.relative_to(self.maven_home)
        return str(relative).replace(os.sep, '.')
    
    async def _analyze_jar(self, group_id: str, artifact_id: str, version: str,
                          include_bytecode: bool = False, include_manifest: bool = True,
                          summarize_large_content: bool = True) -> List[TextContent]:
        """Analyze a specific jar file"""
        jar_path = self._get_jar_path(group_id, artifact_id, version)
        if not jar_path or not jar_path.exists():
            return [TextContent(type="text", text=f"Jar file not found: {group_id}:{artifact_id}:{version}")]
        
        try:
            analysis = {
                "artifact": f"{group_id}:{artifact_id}:{version}",
                "jar_path": str(jar_path),
                "size_bytes": jar_path.stat().st_size
            }
            
            with zipfile.ZipFile(jar_path, 'r') as jar:
                entries = jar.namelist()
                analysis["total_entries"] = len(entries)
                
                # Categorize entries
                classes = [e for e in entries if e.endswith('.class')]
                resources = [e for e in entries if not e.endswith('.class') and not e.endswith('/')]
                
                analysis["classes"] = {
                    "count": len(classes),
                    "packages": self._extract_packages(classes),
                    "class_list": classes[:100] if not include_bytecode else classes
                }
                
                analysis["resources"] = {
                    "count": len(resources),
                    "types": self._categorize_resources(resources),
                    "resource_list": resources[:50]
                }
                
                # Extract manifest
                if include_manifest and "META-INF/MANIFEST.MF" in entries:
                    manifest_content = jar.read("META-INF/MANIFEST.MF").decode('utf-8', errors='ignore')
                    analysis["manifest"] = self._parse_manifest(manifest_content)
                
                # Extract Maven metadata
                pom_entries = [e for e in entries if e.endswith('pom.xml')]
                if pom_entries:
                    pom_content = jar.read(pom_entries[0]).decode('utf-8', errors='ignore')
                    analysis["maven_metadata"] = self._parse_pom(pom_content)
            
            if summarize_large_content and self.response_manager.should_summarize(json.dumps(analysis, indent=2)):
                analysis["content"] = self.response_manager.summarize_large_text(json.dumps(analysis, indent=2))
                analysis["summarized"] = True
            
            return [TextContent(type="text", text=json.dumps(analysis, indent=2))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error analyzing jar: {str(e)}")]
    
    def _get_jar_path(self, group_id: str, artifact_id: str, version: str) -> Optional[Path]:
        """Get path to jar file"""
        group_path = group_id.replace('.', os.sep)
        jar_dir = self.maven_home / group_path / artifact_id / version
        
        # Look for the main jar file
        main_jar = jar_dir / f"{artifact_id}-{version}.jar"
        if main_jar.exists():
            return main_jar
        
        # Look for any jar file in the directory
        jar_files = list(jar_dir.glob("*.jar"))
        if jar_files:
            return jar_files[0]
        
        return None
    
    def _extract_packages(self, classes: List[str]) -> Dict[str, int]:
        """Extract package information from class list"""
        packages = {}
        for class_file in classes:
            if '/' in class_file:
                package = '/'.join(class_file.split('/')[:-1]).replace('/', '.')
                packages[package] = packages.get(package, 0) + 1
        return packages
    
    def _categorize_resources(self, resources: List[str]) -> Dict[str, int]:
        """Categorize resource files by type"""
        types = {}
        for resource in resources:
            if '.' in resource:
                ext = resource.split('.')[-1].lower()
                types[ext] = types.get(ext, 0) + 1
            else:
                types['no_extension'] = types.get('no_extension', 0) + 1
        return types
    
    def _parse_manifest(self, manifest_content: str) -> Dict[str, str]:
        """Parse JAR manifest file"""
        manifest = {}
        for line in manifest_content.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                manifest[key.strip()] = value.strip()
        return manifest
    
    def _parse_pom(self, pom_content: str) -> Dict[str, Any]:
        """Parse POM XML content"""
        try:
            pom_dict = xmltodict.parse(pom_content)
            project = pom_dict.get('project', {})
            
            return {
                "group_id": project.get('groupId', ''),
                "artifact_id": project.get('artifactId', ''),
                "version": project.get('version', ''),
                "name": project.get('name', ''),
                "description": project.get('description', ''),
                "dependencies": project.get('dependencies', {})
            }
        except Exception:
            return {"error": "Failed to parse POM"}
    
    async def _extract_class_info(self, group_id: str, artifact_id: str, version: str,
                                 class_pattern: Optional[str] = None,
                                 include_methods: bool = True,
                                 include_fields: bool = True,
                                 page: int = 1, items_per_page: int = 20,
                                 summarize_large_content: bool = True) -> List[TextContent]:
        """Extract detailed class information"""
        jar_path = self._get_jar_path(group_id, artifact_id, version)
        if not jar_path or not jar_path.exists():
            return [TextContent(type="text", text=f"Jar file not found: {group_id}:{artifact_id}:{version}")]
        
        try:
            import re
            classes_info = []
            
            with zipfile.ZipFile(jar_path, 'r') as jar:
                class_files = [e for e in jar.namelist() if e.endswith('.class')]
                
                for class_file in class_files:
                    class_name = class_file.replace('/', '.').replace('.class', '')
                    
                    # Apply pattern filter if provided
                    if class_pattern:
                        if not re.search(class_pattern, class_name):
                            continue
                    
                    # Basic class info (without bytecode analysis)
                    class_info = {
                        "class_name": class_name,
                        "file_path": class_file,
                        "package": '.'.join(class_name.split('.')[:-1]) if '.' in class_name else '',
                        "simple_name": class_name.split('.')[-1]
                    }
                    
                    # TODO: Add bytecode analysis for methods and fields
                    # This would require additional libraries like javatools or ASM
                    if include_methods:
                        class_info["methods"] = "Bytecode analysis not implemented yet"
                    
                    if include_fields:
                        class_info["fields"] = "Bytecode analysis not implemented yet"
                    
                    classes_info.append(class_info)
            
            result = {
                "artifact": f"{group_id}:{artifact_id}:{version}",
                "total_classes": len(classes_info),
                "classes": classes_info
            }
            
            # Apply pagination if needed
            if self.response_manager.should_paginate(result):
                result = self.response_manager.paginate_response(result, page, items_per_page)
            
            # Apply summarization if needed
            if summarize_large_content and self.response_manager.should_summarize(json.dumps(result, indent=2)):
                result["content"] = self.response_manager.summarize_large_text(json.dumps(result, indent=2))
                result["summarized"] = True
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error extracting class info: {str(e)}")]
    
    async def _get_dependencies(self, group_id: str, artifact_id: str, version: str,
                              include_transitive: bool = False,
                              page: int = 1, items_per_page: int = 20) -> List[TextContent]:
        """Get Maven dependencies with enhanced analysis"""
        try:
            analysis = self.dependency_analyzer.analyze_dependencies(
                group_id, artifact_id, version, include_transitive, max_depth=3
            )
            
            # Apply pagination if needed
            if self.response_manager.should_paginate(analysis):
                analysis = self.response_manager.paginate_response(analysis, page, items_per_page)
            
            # Apply summarization if needed
            if self.response_manager.should_summarize(json.dumps(analysis, indent=2)):
                analysis["content"] = self.response_manager.summarize_large_text(json.dumps(analysis, indent=2))
                analysis["summarized"] = True
            
            return [TextContent(type="text", text=json.dumps(analysis, indent=2))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting dependencies: {str(e)}")]
    
    async def _search_classes(self, class_name: Optional[str] = None,
                            package_pattern: Optional[str] = None,
                            annotation: Optional[str] = None,
                            limit: int = 100, page: int = 1, items_per_page: int = 20) -> List[TextContent]:
        """Search for classes across all jars"""
        import re
        matches = []
        count = 0
        
        try:
            for jar_path in self.maven_home.rglob("*.jar"):
                if count >= limit:
                    break
                
                try:
                    with zipfile.ZipFile(jar_path, 'r') as jar:
                        class_files = [e for e in jar.namelist() if e.endswith('.class')]
                        
                        for class_file in class_files:
                            if count >= limit:
                                break
                            
                            class_full_name = class_file.replace('/', '.').replace('.class', '')
                            simple_name = class_full_name.split('.')[-1]
                            package = '.'.join(class_full_name.split('.')[:-1])
                            
                            # Apply filters
                            if class_name and not re.search(class_name.replace('*', '.*'), simple_name):
                                continue
                            
                            if package_pattern and not re.search(package_pattern, package):
                                continue
                            
                            # TODO: Add annotation search (requires bytecode analysis)
                            if annotation:
                                continue  # Skip for now
                            
                            matches.append({
                                "class_name": class_full_name,
                                "simple_name": simple_name,
                                "package": package,
                                "jar_path": str(jar_path),
                                "artifact_info": self._extract_artifact_info_from_path(jar_path)
                            })
                            count += 1
                
                except Exception:
                    continue  # Skip corrupted jars
            
            result = {
                "total_matches": len(matches),
                "matches": matches
            }
            
            # Apply pagination if needed
            if self.response_manager.should_paginate(result):
                result = self.response_manager.paginate_response(result, page, items_per_page)
            
            # Apply summarization if needed
            if self.response_manager.should_summarize(json.dumps(result, indent=2)):
                result["content"] = self.response_manager.summarize_large_text(json.dumps(result, indent=2))
                result["summarized"] = True
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching classes: {str(e)}")]
    
    def _extract_artifact_info_from_path(self, jar_path: Path) -> Dict[str, str]:
        """Extract Maven artifact info from jar path"""
        try:
            relative_path = jar_path.relative_to(self.maven_home)
            parts = relative_path.parts
            
            if len(parts) >= 3:
                version = parts[-2]
                artifact_id = parts[-3]
                group_id = '.'.join(parts[:-3])
                
                return {
                    "group_id": group_id,
                    "artifact_id": artifact_id,
                    "version": version
                }
        except Exception:
            pass
        
        return {"group_id": "unknown", "artifact_id": "unknown", "version": "unknown"}
    
    async def _extract_source_code(self, group_id: str, artifact_id: str, version: str,
                                 class_name: str, prefer_sources: bool = True,
                                 summarize_large_content: bool = True, max_lines: int = 500) -> List[TextContent]:
        """Extract source code from jar or decompile"""
        # First try to find sources jar
        if prefer_sources:
            sources_jar = self._get_sources_jar_path(group_id, artifact_id, version)
            if sources_jar and sources_jar.exists():
                source_code = self._extract_from_sources_jar(sources_jar, class_name)
                if source_code:
                    result = {
                        "source": "sources-jar",
                        "class_name": class_name,
                        "artifact": f"{group_id}:{artifact_id}:{version}",
                        "code": source_code
                    }
                    if summarize_large_content and self.response_manager.should_summarize(result["code"]):
                        result["code"] = self.response_manager.summarize_large_text(result["code"])
                        result["summarized"] = True
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        # Fall back to decompilation
        jar_path = self._get_jar_path(group_id, artifact_id, version)
        if not jar_path or not jar_path.exists():
            return [TextContent(type="text", text=f"Jar file not found: {group_id}:{artifact_id}:{version}")]
        
        try:
            decompiled_code = self.decompiler.decompile_class(jar_path, class_name)
            result = {
                "source": "decompiled",
                "class_name": class_name,
                "artifact": f"{group_id}:{artifact_id}:{version}",
                "code": decompiled_code or "Failed to decompile class",
                "available_decompilers": list(self.decompiler.available_decompilers.keys())
            }
            if summarize_large_content and self.response_manager.should_summarize(result["code"]):
                result["code"] = self.response_manager.summarize_large_text(result["code"])
                result["summarized"] = True
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error extracting source code: {str(e)}")]
    
    def _get_sources_jar_path(self, group_id: str, artifact_id: str, version: str) -> Optional[Path]:
        """Get path to sources jar file"""
        group_path = group_id.replace('.', os.sep)
        jar_dir = self.maven_home / group_path / artifact_id / version
        sources_jar = jar_dir / f"{artifact_id}-{version}-sources.jar"
        return sources_jar if sources_jar.exists() else None
    
    def _extract_from_sources_jar(self, sources_jar: Path, class_name: str) -> Optional[str]:
        """Extract source code from sources jar"""
        try:
            java_file = class_name.replace('.', '/') + '.java'
            with zipfile.ZipFile(sources_jar, 'r') as jar:
                if java_file in jar.namelist():
                    return jar.read(java_file).decode('utf-8', errors='ignore')
        except Exception:
            pass
        return None
    
    async def _compare_versions(self, group_id: str, artifact_id: str,
                              version1: str, version2: str,
                              compare_api: bool = True,
                              summarize_large_content: bool = True) -> List[TextContent]:
        """Compare different versions of the same artifact"""
        # Get both jar paths
        jar1 = self._get_jar_path(group_id, artifact_id, version1)
        jar2 = self._get_jar_path(group_id, artifact_id, version2)
        
        if not jar1 or not jar1.exists():
            return [TextContent(type="text", text=f"Version {version1} not found")]
        
        if not jar2 or not jar2.exists():
            return [TextContent(type="text", text=f"Version {version2} not found")]
        
        try:
            comparison = {
                "artifact": f"{group_id}:{artifact_id}",
                "version1": version1,
                "version2": version2,
                "comparison": {}
            }
            
            # Compare jar sizes
            comparison["comparison"]["size_v1"] = jar1.stat().st_size
            comparison["comparison"]["size_v2"] = jar2.stat().st_size
            comparison["comparison"]["size_diff"] = jar2.stat().st_size - jar1.stat().st_size
            
            # Compare class lists
            with zipfile.ZipFile(jar1, 'r') as z1, zipfile.ZipFile(jar2, 'r') as z2:
                classes1 = set(e for e in z1.namelist() if e.endswith('.class'))
                classes2 = set(e for e in z2.namelist() if e.endswith('.class'))
                
                comparison["comparison"]["classes_added"] = sorted(list(classes2 - classes1))
                comparison["comparison"]["classes_removed"] = sorted(list(classes1 - classes2))
                comparison["comparison"]["classes_common"] = len(classes1 & classes2)
            
            # TODO: Add API comparison (requires bytecode analysis)
            if compare_api:
                comparison["comparison"]["api_changes"] = "API comparison not yet implemented"
            
            if summarize_large_content and self.response_manager.should_summarize(json.dumps(comparison, indent=2)):
                comparison["content"] = self.response_manager.summarize_large_text(json.dumps(comparison, indent=2))
                comparison["summarized"] = True
            
            return [TextContent(type="text", text=json.dumps(comparison, indent=2))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error comparing versions: {str(e)}")]
    
    async def _find_usage_examples(self, class_name: str,
                                 method_name: Optional[str] = None,
                                 search_tests: bool = True,
                                 limit: int = 50, page: int = 1, items_per_page: int = 20) -> List[TextContent]:
        """Find usage examples in test jars"""
        # TODO: Implement usage search in test jars and source code
        return [TextContent(type="text", text="Usage example search not yet implemented")]
    
    async def _get_dependency_tree(self, group_id: str, artifact_id: str, version: str,
                                  max_depth: int = 3, summarize_large_content: bool = True) -> List[TextContent]:
        """Get complete dependency tree"""
        try:
            tree = self.dependency_analyzer.find_dependency_tree(group_id, artifact_id, version)
            if summarize_large_content and self.response_manager.should_summarize(json.dumps(tree, indent=2)):
                tree = self.response_manager.summarize_large_text(json.dumps(tree, indent=2))
            return [TextContent(type="text", text=json.dumps(tree, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting dependency tree: {str(e)}")]
    
    async def _find_dependents(self, group_id: str, artifact_id: str, 
                             version: Optional[str] = None,
                             limit: int = 100, page: int = 1, items_per_page: int = 20) -> List[TextContent]:
        """Find artifacts that depend on the target"""
        try:
            dependents = self.dependency_analyzer.find_dependents(group_id, artifact_id, version)
            result = {
                "target_artifact": f"{group_id}:{artifact_id}" + (f":{version}" if version else ""),
                "dependents": dependents,
                "total_dependents": len(dependents)
            }
            # Apply pagination if needed
            if self.response_manager.should_paginate(result):
                result = self.response_manager.paginate_response(result, page, items_per_page)
            
            # Apply summarization if needed
            if self.response_manager.should_summarize(json.dumps(result, indent=2)):
                result["content"] = self.response_manager.summarize_large_text(json.dumps(result, indent=2))
                result["summarized"] = True
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error finding dependents: {str(e)}")]
    
    async def _get_version_info(self, group_id: str, artifact_id: str,
                                limit: int = 50, page: int = 1, items_per_page: int = 20) -> List[TextContent]:
        """Get version information for an artifact"""
        try:
            version_info = self.dependency_analyzer.get_version_info(group_id, artifact_id)
            # Apply pagination if needed
            if self.response_manager.should_paginate(version_info):
                version_info = self.response_manager.paginate_response(version_info, page, items_per_page)
            
            # Apply summarization if needed
            if self.response_manager.should_summarize(json.dumps(version_info, indent=2)):
                version_info["content"] = self.response_manager.summarize_large_text(json.dumps(version_info, indent=2))
                version_info["summarized"] = True
            return [TextContent(type="text", text=json.dumps(version_info, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting version info: {str(e)}")]
    
    async def _analyze_jar_structure(self, group_id: str, artifact_id: str, version: str,
                                   summarize_large_content: bool = True) -> List[TextContent]:
        """Analyze jar file structure"""
        jar_path = self._get_jar_path(group_id, artifact_id, version)
        if not jar_path or not jar_path.exists():
            return [TextContent(type="text", text=f"Jar file not found: {group_id}:{artifact_id}:{version}")]
        
        try:
            analysis = self.decompiler.analyze_jar_structure(jar_path)
            if summarize_large_content and self.response_manager.should_summarize(json.dumps(analysis, indent=2)):
                analysis["content"] = self.response_manager.summarize_large_text(json.dumps(analysis, indent=2))
                analysis["summarized"] = True
            return [TextContent(type="text", text=json.dumps(analysis, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error analyzing jar structure: {str(e)}")]
    
    async def _extract_method_info(self, group_id: str, artifact_id: str, version: str,
                                 class_name: str, method_pattern: Optional[str] = None,
                                 include_bytecode: bool = False, max_methods: int = 10) -> List[TextContent]:
        """Extract specific method information from a Java class"""
        jar_path = self._get_jar_path(group_id, artifact_id, version)
        if not jar_path or not jar_path.exists():
            return [TextContent(type="text", text=f"Jar file not found: {group_id}:{artifact_id}:{version}")]
        
        try:
            # Get the full source code first
            source_code = await self._extract_source_code_internal(jar_path, class_name)
            if not source_code:
                return [TextContent(type="text", text=f"Could not extract source code for class: {class_name}")]
            
            # Parse methods from source code
            methods = self._extract_methods_from_source(source_code, method_pattern, max_methods)
            
            result = {
                "class_name": class_name,
                "artifact": f"{group_id}:{artifact_id}:{version}",
                "total_methods_found": len(methods),
                "methods": methods,
                "method_pattern": method_pattern or "all methods"
            }
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error extracting method info: {str(e)}")]
    
    def _extract_methods_from_source(self, source_code: str, method_pattern: Optional[str] = None, 
                                   max_methods: int = 10) -> List[Dict[str, Any]]:
        """Extract method information from Java source code"""
        import re
        
        methods = []
        lines = source_code.split('\n')
        
        # Pattern to match method declarations
        method_pattern_regex = re.compile(
            r'^\s*(public|private|protected|static|final)?\s*'
            r'(?:<[^>]+>\s+)?'  # Generic type parameters
            r'(\w+(?:<[^>]+>)?)\s+'  # Return type
            r'(\w+)\s*'  # Method name
            r'\([^)]*\)'  # Parameters
        )
        
        current_method = None
        brace_count = 0
        method_start_line = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments and empty lines
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*') or not stripped:
                continue
            
            # Check if this line starts a method
            match = method_pattern_regex.match(stripped)
            if match and not current_method:
                method_name = match.group(3)
                
                # Apply pattern filter if provided
                if method_pattern and not re.search(method_pattern, method_name):
                    continue
                
                current_method = {
                    "name": method_name,
                    "return_type": match.group(2),
                    "modifiers": match.group(1) or "",
                    "signature": stripped,
                    "start_line": i + 1,
                    "body": []
                }
                method_start_line = i + 1
                brace_count = 0
                continue
            
            # If we're in a method, collect the body
            if current_method:
                current_method["body"].append(line)
                
                # Count braces to find method end
                brace_count += line.count('{') - line.count('}')
                
                if brace_count <= 0 and line.strip().endswith('}'):
                    # Method ended
                    current_method["end_line"] = i + 1
                    current_method["body"] = '\n'.join(current_method["body"])
                    
                    methods.append(current_method)
                    current_method = None
                    
                    if len(methods) >= max_methods:
                        break
        
        return methods
    
    async def _extract_source_code_internal(self, jar_path: Path, class_name: str) -> Optional[str]:
        """Internal method to extract source code without response formatting"""
        try:
            # First try to find sources jar
            sources_jar = self._get_sources_jar_path_from_jar(jar_path)
            if sources_jar and sources_jar.exists():
                source_code = self._extract_from_sources_jar(sources_jar, class_name)
                if source_code:
                    return source_code
            
            # Fall back to decompilation
            return self.decompiler.decompile_class(jar_path, class_name)
            
        except Exception:
            return None
    
    def _get_sources_jar_path_from_jar(self, jar_path: Path) -> Optional[Path]:
        """Get path to sources jar file from main jar path"""
        jar_dir = jar_path.parent
        jar_name = jar_path.stem
        
        # Remove version suffix to get artifact name
        if '-' in jar_name:
            artifact_name = jar_name.rsplit('-', 1)[0]
            version = jar_name.rsplit('-', 1)[1]
            sources_jar = jar_dir / f"{artifact_name}-{version}-sources.jar"
            return sources_jar if sources_jar.exists() else None
        
        return None

    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Maven Decoder MCP Server...")
        try:
            async with stdio_server() as (read_stream, write_stream):
                logger.info("Connected to stdio streams")
                logger.info("Server capabilities: tools support enabled")
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="maven-decoder",
                        server_version="1.0.0",
                        capabilities=ServerCapabilities(
                            tools=ToolsCapability(listChanged=False)
                        )
                    )
                )
        except Exception as e:
            logger.error(f"Error running MCP server: {e}", exc_info=True)
            raise

def main():
    """Main entry point for the maven-decoder-mcp command"""
    logger.info("="*60)
    logger.info("Maven Decoder MCP Server - Starting up...")
    logger.info("="*60)
    
    try:
        server = MavenDecoderServer()
        logger.info("Server instance created successfully")
        logger.info("Running async server loop...")
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
    except Exception as e:
        logger.error(f"Server startup failed: {e}", exc_info=True)
        raise
    finally:
        logger.info("Maven Decoder MCP Server shutdown complete")

if __name__ == "__main__":
    main()
