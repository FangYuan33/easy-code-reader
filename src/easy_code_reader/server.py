#!/usr/bin/env python3
"""
Easy Code Reader MCP Server

这是一个 Model Context Protocol (MCP) 服务器，用于读取 Java 源代码。

主要功能：
- 从 Maven 仓库读取 JAR 包源代码（支持 SNAPSHOT 版本）
- 支持从 sources jar 提取源码或反编译 class 文件
- 智能选择反编译器（CFR/Fernflower）
- 在本地 Maven 仓库中根据 artifactId 和 package 前缀查找 groupId

提供的工具：
- search_group_id: 根据 artifactId 和 package 前缀查找 Maven groupId
- read_jar_source: 读取 Maven 依赖中的 Java 类源代码
"""

import asyncio
import json
import logging
import time
import zipfile
from pathlib import Path
from typing import Any, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource

from .config import Config
from .decompiler import JavaDecompiler

# 配置日志系统
import os

log_file = os.path.join(os.path.dirname(__file__), "easy_code_reader.log")
logging.basicConfig(
    level=logging.INFO,  # 生产环境使用 INFO 级别
    format='%(asctime)s - %(levelname)s - %(message)s',  # 简化格式，去除模块名
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EasyCodeReaderServer:
    """
    Easy Code Reader MCP 服务器
    
    提供从 Maven 依赖中读取 Java 源代码的功能。
    """

    def __init__(self, maven_repo_path: Optional[str] = None):
        """
        初始化 Easy Code Reader MCP 服务器
        
        参数:
            maven_repo_path: 自定义 Maven 仓库路径（可选）
        """
        logger.info("正在初始化 MCP 服务器...")

        # 创建 MCP 服务器实例
        self.server = Server(Config.SERVER_NAME)

        # 设置 Maven 仓库路径
        if maven_repo_path:
            Config.set_maven_home(maven_repo_path)

        self.maven_home = Config.get_maven_home()

        # 检查 Maven 仓库是否存在
        if not self.maven_home.exists():
            logger.warning(f"Maven 仓库不存在: {self.maven_home}")
        else:
            logger.info(f"Maven 仓库: {self.maven_home}")

        # 初始化 Java 反编译器
        self.decompiler = JavaDecompiler()
        if not self.decompiler.fernflower_jar and not self.decompiler.cfr_jar:
            logger.error("未找到任何可用的反编译器，反编译功能将不可用")

        # 设置 MCP 服务器处理程序
        self.setup_handlers()
        logger.info("MCP 服务器初始化完成")

    def setup_handlers(self):
        """设置 MCP 服务器处理程序"""

        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """列出可用的工具"""
            return [
                Tool(
                    name="search_group_id",
                    description=(
                        "辅助 read_jar_source 工具的调用，在未知 groupId 的情况下，根据 artifactId 和 package 前缀查找 Maven groupId。\n\n"
                        "**使用场景：**\n"
                        "当看到类路径如 `/spring-context-5.0.0.RELEASE.jar/org.springframework.context/ApplicationContext.class` "
                        "但不知道完整 Maven 坐标时，使用此工具查找 groupId。\n\n"
                        "**工作原理：**\n"
                        "1. 在 Maven 仓库中搜索匹配的 artifact ID\n"
                        "2. 可选使用 group_prefix 缩小搜索范围（强烈推荐，可提速 10 倍以上）\n"
                        "3. 可选使用 version_hint 进一步过滤版本\n"
                        "4. 返回按 groupId 排序的匹配列表\n\n"
                        "**参数说明：**\n"
                        "- artifact_id: JAR 名称（不含版本），如 \"spring-context\"\n"
                        "- group_prefix: （可选）groupId 前缀（1-2 级），如 \"org.springframework\"\n"
                        "  从类路径提取：org.springframework.context → 使用 \"org.springframework\"\n"
                        "- version_hint: （可选）版本提示，如 \"5.0.0.RELEASE\"、\"SNAPSHOT\"\n"
                        "  ⚠️ 警告：如果版本信息不准确可能导致查不到结果\n\n"
                        "**返回结果：**\n"
                        "包含 groupId、匹配版本列表的详细信息。\n\n"
                        "**典型工作流：**\n"
                        "1. 从错误信息中提取 artifact_id 和 package 前缀\n"
                        "2. 调用 search_group_id 获取候选 groupId\n"
                        "3. 选择合适的 groupId\n"
                        "4. 使用 read_jar_source 读取源码"
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "artifact_id": {
                                "type": "string",
                                "description": "Maven artifact ID，不含版本号（例如：spring-context）"
                            },
                            "group_prefix": {
                                "type": "string",
                                "description": "可选：groupId 前缀（1-2 级），如 \"org.springframework\"。从类路径中提取：org.springframework.context → 使用 \"org.springframework\"。用于缩小搜索范围，提升性能"
                            },
                            "version_hint": {
                                "type": "string",
                                "description": "可选：版本提示，如 \"1.2.2\"、\"SNAPSHOT\"、\"20251110\"。⚠️ 警告：如果版本信息不准确可能导致查不到结果"
                            }
                        },
                        "required": ["artifact_id"]
                    }
                ),
                Tool(
                    name="read_jar_source",
                    description=(
                        "从 Maven 依赖中读取 Java 类的源代码。\n"
                        "工作流程：1) 首先尝试从 -sources.jar 中提取原始源代码；2) 如果 sources jar 不存在，自动使用反编译器（CFR 或 Fernflower）反编译 class 文件。\n"
                        "支持 SNAPSHOT 版本的智能处理，会自动查找带时间戳的最新版本。\n"
                        "适用场景：阅读第三方库源码（如 Spring、MyBatis）、理解依赖实现细节、排查依赖相关问题。\n"
                        "注意：需要提供完整的 Maven 坐标（group_id、artifact_id、version）和完全限定的类名（如 org.springframework.core.SpringVersion）。\n"
                    ),
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
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Any) -> List[TextContent]:
            """处理工具调用"""
            try:
                if name == "read_jar_source":
                    return await self._read_jar_source(**arguments)
                elif name == "search_group_id":
                    return await self._search_group_id(**arguments)
                else:
                    logger.error(f"未知工具: {name}")
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error(f"工具 {name} 执行失败: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """列出可用的资源"""
            return [
                Resource(
                    uri="easy-code-reader://guide",
                    name="Easy Code Reader 使用指南",
                    description=(
                        "Github仓库: https://github.com/FangYuan33/easy-code-reader"
                    ),
                    mimeType="text/markdown"
                )
            ]

        @self.server.read_resource()
        async def handle_read_resource(uri) -> str:
            """读取资源内容
            
            注意：uri 参数类型为 pydantic.networks.AnyUrl，需要转换为字符串进行比较
            """
            # 将 AnyUrl 对象转换为字符串
            uri_str = str(uri)

            if uri_str == "easy-code-reader://guide":
                return self._get_guide_content()
            else:
                raise ValueError(f"Unknown resource URI: {uri_str}")

    def _get_guide_content(self) -> str:
        """获取使用指南内容"""
        maven_repo = self.maven_home if self.maven_home else "~/.m2/repository"

        # 使用普通字符串拼接，避免 f-string 中嵌套 JSON 导致的语法错误
        guide_text = "# Easy Code Reader 使用指南\n\n"
        guide_text += "## 功能介绍\n\n"
        guide_text += "Easy Code Reader 是一个强大的 MCP (Model Context Protocol) 服务器，专为智能读取 Java 源代码而设计，能从本地 Maven 仓库的 JAR 包中提取源码。\n\n"
        guide_text += "## 配置参数说明\n\n"
        guide_text += "- MCP 配置示例（uvx 使用示例）：\n\n"
        guide_text += "```json\n"
        guide_text += "{\n"
        guide_text += '  "mcpServers": {\n'
        guide_text += '    "easy-code-reader": {\n'
        guide_text += '      "command": "uvx",\n'
        guide_text += '      "args": [\n'
        guide_text += '        "easy-code-reader",\n'
        guide_text += '        "--maven-repo",\n'
        guide_text += '        "/path/to/maven/repository"\n'
        guide_text += '      ]\n'
        guide_text += '    }\n'
        guide_text += '  }\n'
        guide_text += '}\n'
        guide_text += "```\n\n"
        guide_text += "### maven_repo（Maven 仓库路径）\n\n"
        guide_text += f"- **当前配置：** `{maven_repo}`\n"
        guide_text += "- **用途：** 指定本地 Maven 仓库的位置，用于查找和读取 JAR 包。\n\n"
        guide_text += "**配置优先级：**\n"
        guide_text += "1. 启动参数 `--maven-repo`（最高优先级）\n"
        guide_text += "2. 环境变量 `MAVEN_HOME`（使用 $MAVEN_HOME/repository）\n"
        guide_text += "3. 环境变量 `M2_HOME`（使用 $M2_HOME/repository）\n"
        guide_text += "4. 环境变量 `MAVEN_REPO`\n"
        guide_text += "5. 默认路径 `~/.m2/repository`（最低优先级）\n\n"
        guide_text += "## 提供的工具\n\n"
        guide_text += "1. **search_group_id** - 根据 artifactId 和 package 前缀查找 Maven groupId\n"
        guide_text += "2. **read_jar_source** - 读取 Maven 依赖中的 Java 类源代码\n\n"
        guide_text += "## 项目仓库\n\n"
        guide_text += "- [GitHub 仓库](https://github.com/FangYuan33/easy-code-reader)\n\n"
        guide_text += "## 技术细节\n\n"
        guide_text += f"- **反编译缓存位置：** `{maven_repo}/.../easy-code-reader/`\n"
        guide_text += "- **日志文件位置：** `src/easy_code_reader/easy_code_reader.log`\n"
        guide_text += "- **源码来源：** sources JAR 或 class 文件反编译\n\n"
        guide_text += "---\n\n"
        guide_text += "💡 **提示：** 使用 AI 助手时，可以直接描述你想读取的代码，AI 会自动选择合适的工具来获取源码。\n"

        return guide_text

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
                        "source_type": "sources.jar",
                        "code": source_code
                    }

                    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        # 回退到反编译
        jar_path = self._get_jar_path(group_id, artifact_id, version)
        if not jar_path or not jar_path.exists():
            # 提取 groupId 的前缀部分用于搜索建议（取前1-2段）
            group_parts = group_id.split('.')
            if len(group_parts) >= 2:
                # 推荐使用前2段，如 com.alibaba.nacos.api -> com.alibaba
                suggested_hint = '.'.join(group_parts[:2])
            elif len(group_parts) == 1:
                # 只有1段，直接使用，如 com -> com
                suggested_hint = group_parts[0]
            else:
                suggested_hint = None
            
            error_msg = (
                f"❌ 未找到 JAR 文件: {group_id}:{artifact_id}:{version}\n\n"
                f"Maven 仓库路径: {self.maven_home}\n\n"
                f"可能的原因：\n"
                f"1. Maven 坐标信息（特别是 groupId）可能不正确\n"
                f"2. 该依赖尚未下载到本地 Maven 仓库\n\n"
                f"建议排查步骤（按优先级）：\n"
                f"1. 🔍 **强烈推荐：使用 search_group_id 工具查找正确的 Maven 坐标**\n"
                f"   - 必填参数 artifact_name: '{artifact_id}'\n"
                f"   - 可选参数 version_hint: '{version}' 缩小搜索范围\n"
            )
            
            # 添加 group_prefix 的智能建议
            if suggested_hint:
                error_msg += (
                    f"   - ⚠️ 重要：如需提供 group_prefix 参数，建议使用较短的前缀以避免过度限制\n"
                    f"     • 推荐使用: '{suggested_hint}' (groupId 的前2段)\n"
                    f"     • 或者更宽泛: '{group_parts[0]}' (groupId 的第1段)\n"
                    f"     • 避免使用完整的: '{group_id}' (可能因拼写错误而搜不到)\n"
                )
            else:
                error_msg += (
                    f"   - 💡 提示：group_prefix 参数是可选的，不确定时可以不传\n"
                )
            
            error_msg += (
                f"   - 该工具会在本地 Maven 仓库中搜索所有匹配的完整坐标\n"
                f"2. 如果有依赖声明，可核对 pom.xml 中的 Maven 坐标\n"
                f"   - 在 <dependencies> 部分查找正确的 groupId、artifactId 和 version\n"
                f"   - 注意：groupId 和 artifactId 可能与直观理解不同\n"
                f"3. 确认坐标信息正确后，重新调用 read_jar_source 工具\n"
            )
            logger.warning(error_msg)
            return [TextContent(type="text", text=error_msg)]

        try:
            # 对于 SNAPSHOT 版本，实际反编译使用 -SNAPSHOT.jar，但缓存使用带时间戳的版本名
            actual_jar_to_decompile = jar_path
            if version.endswith('-SNAPSHOT'):
                snapshot_jar = self._get_snapshot_jar_path(group_id, artifact_id, version)
                if snapshot_jar and snapshot_jar.exists():
                    actual_jar_to_decompile = snapshot_jar

            # decompile_class 现在返回 (code, source_type) 元组
            decompiled_code, source_type = self.decompiler.decompile_class(
                actual_jar_to_decompile, class_name,
                cache_jar_name=jar_path.name if actual_jar_to_decompile != jar_path else None
            )

            if not decompiled_code:
                logger.error(f"反编译失败: {class_name} from {group_id}:{artifact_id}:{version}")

            result = {
                "class_name": class_name,
                "artifact": f"{group_id}:{artifact_id}:{version}",
                "source_type": source_type,
                "code": decompiled_code or "反编译失败"
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        except Exception as e:
            logger.error(f"提取源代码时出错: {str(e)}", exc_info=True)
            return [TextContent(type="text", text=f"提取源代码时出错: {str(e)}")]

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

    def _get_snapshot_jar_path(self, group_id: str, artifact_id: str, version: str) -> Optional[Path]:
        """
        获取 SNAPSHOT jar 文件路径（不带时间戳）
        对于 SNAPSHOT 版本，返回 artifact-version-SNAPSHOT.jar
        """
        if not version.endswith('-SNAPSHOT'):
            return None

        group_path = group_id.replace('.', os.sep)
        jar_dir = self.maven_home / group_path / artifact_id / version
        snapshot_jar = jar_dir / f"{artifact_id}-{version}.jar"

        return snapshot_jar if snapshot_jar.exists() else None

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
            logger.error(f"从 sources jar 提取失败 {sources_jar}: {e}")
        return None

    def _filter_snapshot_jars(self, jar_files: List[Path], artifact_id: str, version: str) -> List[Path]:
        """
        过滤 SNAPSHOT 版本的 JAR 文件，优化返回结果
        
        策略：
        1. 如果存在主 SNAPSHOT JAR（如 artifact-1.0.0-SNAPSHOT.jar），只返回它
        2. 如果没有找到主 SNAPSHOT JAR，不处理带时间戳的版本（这些版本没有意义）
        3. 排除所有带时间戳的 SNAPSHOT JAR，减少上下文消耗
        
        参数:
            jar_files: JAR 文件路径列表
            artifact_id: Maven artifact ID
            version: 版本号
            
        返回:
            过滤后的 JAR 文件列表（通常只有一个，如果没有主 SNAPSHOT JAR 则返回空列表）
        """
        if not version.endswith('-SNAPSHOT'):
            # 非 SNAPSHOT 版本，直接返回所有 JAR
            return jar_files
        
        # 查找主 SNAPSHOT JAR
        main_snapshot_jar = f"{artifact_id}-{version}.jar"
        for jar_file in jar_files:
            if jar_file.name == main_snapshot_jar:
                # 找到主 SNAPSHOT JAR，只返回它
                return [jar_file]
        
        # 没有找到主 SNAPSHOT JAR，不处理带时间戳的 JAR（这些版本没有意义）
        return []

    async def _search_group_id(self, artifact_id: str,
                               group_prefix: Optional[str] = None,
                               version_hint: Optional[str] = None) -> List[TextContent]:
        """
        根据 artifact ID 和 package 前缀查找 Maven groupId
        
        工作原理：
        1. 在 Maven 仓库中搜索匹配的 artifact ID
        2. 可选使用 group_prefix 缩小搜索范围（提速 10 倍以上）
        3. 可选使用 version_hint 进一步过滤版本
        4. 返回按 groupId 排序的匹配列表

        参数:
            artifact_id: Maven artifact ID（不含版本号）
            group_prefix: groupId 前缀（1-2 级），用于缩小搜索范围
            version_hint: 版本提示，用于进一步过滤版本

        返回:
            包含所有匹配坐标的 JSON 结果，包含：
            - artifact_id: 搜索的 artifact ID
            - group_prefix: 使用的 groupId 前缀
            - version_hint: 使用的版本提示
            - total_matches: 匹配数量
            - search_stats: 搜索统计信息
            - matches: 匹配结果列表（包含 matched_versions）
            - hint: AI 友好的操作提示
        """
        # 输入验证
        if not artifact_id or not artifact_id.strip():
            return [TextContent(type="text", text="错误: artifact_id 不能为空")]

        # 规范化输入（去除首尾空格）
        artifact_id = artifact_id.strip()
        if group_prefix:
            group_prefix = group_prefix.strip()
            # 验证 group_prefix 最多2级
            prefix_parts = group_prefix.split('.')
            if len(prefix_parts) > 2:
                logger.warning(f"group_prefix '{group_prefix}' 超过2级，建议使用前2级以获得更好的搜索范围")
        if version_hint:
            version_hint = version_hint.strip()

        logger.info(
            f"开始搜索 groupId: artifact_id={artifact_id}, group_prefix={group_prefix}, version_hint={version_hint}")

        # 检查 Maven 仓库是否存在
        if not self.maven_home.exists():
            return [TextContent(
                type="text",
                text=f"错误: Maven 仓库不存在: {self.maven_home}\n请检查 Maven 仓库配置"
            )]

        # 用于收集匹配结果
        # key: group_id, value: {versions: []}
        group_matches = {}
        scanned_groups = 0
        start_time = time.perf_counter()

        def search_maven_repo(base_path: Path):
            """
            遍历搜索 Maven 仓库
            
            Maven 仓库结构: {maven_repo}/{groupId}/{artifactId}/{version}/
            """
            nonlocal scanned_groups

            try:
                # 遍历仓库根目录的第一层（通常是 groupId 的第一部分）
                for first_level in base_path.iterdir():
                    if not first_level.is_dir() or first_level.name.startswith('.'):
                        continue

                    # 性能优化：如果提供了 group_prefix，提前过滤
                    if group_prefix:
                        first_level_name_lower = first_level.name.lower()
                        group_prefix_lower = group_prefix.lower()
                        
                        # 分割 prefix 获取各部分
                        prefix_parts = group_prefix_lower.split('.')
                        
                        # 判断是否应该探索这个目录
                        should_explore = False
                        
                        # 情况1：prefix 的第一部分就是顶级目录
                        if prefix_parts[0] == first_level_name_lower:
                            should_explore = True
                        # 情况2：prefix 包含完整路径，检查第一部分是否匹配
                        elif '.' in group_prefix_lower:
                            should_explore = False
                        else:
                            # prefix 不包含点号，可能在任何顶级目录下
                            should_explore = True
                        
                        if not should_explore:
                            continue

                    # 递归查找 artifact_id 目录
                    for artifact_dir in first_level.rglob(artifact_id):
                        scanned_groups += 1

                        if not artifact_dir.is_dir():
                            continue

                        try:
                            # 提取 groupId（从 Maven 仓库路径推断）
                            rel_path = artifact_dir.parent.relative_to(base_path)
                            group_id = str(rel_path).replace(os.sep, '.')

                            # 精确的 group_prefix 过滤（不区分大小写）
                            if group_prefix and group_prefix.lower() not in group_id.lower():
                                continue

                            # 初始化该 groupId 的记录
                            if group_id not in group_matches:
                                group_matches[group_id] = {
                                    "versions": []
                                }

                            # 遍历所有版本目录
                            for version_dir in artifact_dir.iterdir():
                                if not version_dir.is_dir():
                                    continue

                                version = version_dir.name

                                # 版本号过滤（不区分大小写）
                                if version_hint and version_hint.lower() not in version.lower():
                                    continue

                                # 验证该版本是否有 JAR 文件（排除 sources 和 javadoc）
                                jar_files = [
                                    f for f in version_dir.glob(f"{artifact_id}-*.jar")
                                    if not f.name.endswith('-sources.jar')
                                       and not f.name.endswith('-javadoc.jar')
                                ]

                                if jar_files:
                                    # 对 SNAPSHOT 版本应用过滤
                                    filtered_jars = self._filter_snapshot_jars(jar_files, artifact_id, version)
                                    
                                    if not filtered_jars:
                                        continue
                                    
                                    # 记录版本
                                    group_matches[group_id]["versions"].append(version)

                                    logger.debug(f"找到版本: {group_id}:{artifact_id}:{version}")

                        except Exception as e:
                            logger.warning(f"处理路径 {artifact_dir} 时出错: {e}")
                            continue

            except PermissionError as e:
                logger.warning(f"无权限访问目录 {base_path}: {e}")
            except Exception as e:
                logger.error(f"搜索 Maven 仓库时出错: {e}", exc_info=True)

        # 执行搜索
        search_maven_repo(self.maven_home)

        # 计算搜索耗时
        elapsed_time = round(time.perf_counter() - start_time, 2)

        # 构建结果
        matches = []
        for group_id, data in group_matches.items():
            versions = data["versions"]
            
            # 跳过没有匹配版本的 groupId（可能被 version_hint 过滤掉了所有版本）
            if not versions:
                continue
            
            matches.append({
                "group_id": group_id,
                "matched_versions": sorted(versions, reverse=True)[:10],  # 最多返回10个版本
                "total_versions": len(versions)
            })

        # 按 group_id 字典序排序
        matches.sort(key=lambda x: x["group_id"])

        # 构建返回结果
        result = {
            "artifact_id": artifact_id,
            "group_prefix": group_prefix if group_prefix else "none",
            "version_hint": version_hint if version_hint else "none",
            "total_matches": len(matches),
            "search_stats": {
                "scanned_groups": scanned_groups,
                "elapsed_seconds": elapsed_time
            },
            "matches": matches
        }

        # 添加智能提示（针对不同场景）
        if len(matches) == 0:
            # 场景1: 未找到任何匹配
            result["hint"] = (
                f"❌ 未找到 artifact '{artifact_id}' 的任何匹配\n\n"
                "可能原因：\n"
                "1. artifact_id 拼写错误\n"
                "2. 依赖未下载到本地仓库\n"
                + (f"3. group_prefix '{group_prefix}' 过滤过严\n" if group_prefix else "")
                + (f"4. version_hint '{version_hint}' 过滤过严（⚠️ 注意：AI 可能产生幻觉导致版本号错误）\n" if version_hint else "")
                + "\n建议操作：\n"
                "1. group_prefix 可以修改成 1 级或者不传，version_hint 也可以不传，重新搜索\n"
                "2. 检查 artifact_id 拼写"
            )
        else:
            # 找到匹配
            if len(matches) == 1:
                # 场景2: 找到唯一匹配
                match = matches[0]
                versions_str = ", ".join(match["matched_versions"][:3])
                if match["total_versions"] > 3:
                    versions_str += f" (共 {match['total_versions']} 个版本)"
                
                result["hint"] = (
                    f"✅ 找到唯一匹配！\n\n"
                    f"📦 groupId: {match['group_id']}\n"
                    f"📊 匹配版本: {versions_str}\n\n"
                    "下一步：使用 read_jar_source 读取源码\n"
                    f"  • group_id: {match['group_id']}\n"
                    f"  • artifact_id: {artifact_id}\n"
                    f"  • version: {match['matched_versions'][0]}\n"
                    "  • class_name: <完全限定的类名>"
                )
            else:
                # 场景3: 找到多个候选
                suggestions = []
                for i, m in enumerate(matches[:5], 1):
                    suggestions.append(f"{i}. {m['group_id']}")
                
                result["hint"] = (
                    f"🎯 找到 {len(matches)} 个候选 groupId\n\n"
                    "建议选择：\n" + "\n".join(suggestions) + "\n\n"
                    "💡 提示：\n"
                    "• 依次尝试每个 groupId\n"
                    "• 可查看 matched_versions 确认版本可用性"
                )

        logger.info(f"搜索完成: 找到 {len(matches)} 个匹配，耗时 {elapsed_time}s")

        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    async def run(self):
        """运行 MCP 服务器"""
        logger.info("启动 MCP 服务器...")
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
    server = EasyCodeReaderServer(maven_repo_path=maven_repo_path)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
