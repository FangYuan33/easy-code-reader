#!/usr/bin/env python3
"""
Easy Code Reader MCP Server

这是一个 Model Context Protocol (MCP) 服务器，用于读取 Java 源代码。

主要功能：
- 从 Maven 仓库读取 JAR 包源代码（支持 SNAPSHOT 版本）
- 从本地项目目录读取源代码（支持多模块项目）
- 支持从 sources jar 提取源码或反编译 class 文件
- 智能选择反编译器（CFR/Fernflower）

提供的工具：
- read_jar_source: 读取 Maven 依赖中的 Java 类源代码
- read_project_code: 读取本地项目中的源代码
- list_all_project: 列举项目目录下的所有项目
- list_project_files: 列出项目中的源代码和配置文件
"""

import asyncio
import json
import logging
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
    
    def __init__(self, maven_repo_path: Optional[str] = None, project_dir: Optional[str] = None):
        """
        初始化 Easy Code Reader MCP 服务器
        
        参数:
            maven_repo_path: 自定义 Maven 仓库路径（可选）
            project_dir: 项目目录路径（可选）
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
        
        # 设置项目目录路径
        self.project_dir = Path(project_dir) if project_dir else None
        if self.project_dir:
            if not self.project_dir.exists():
                logger.warning(f"项目目录不存在: {self.project_dir}")
            else:
                logger.info(f"项目目录: {self.project_dir}")
        
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
                    name="read_jar_source",
                    description=(
                        "从 Maven 依赖中读取 Java 类的源代码。"
                        "工作流程：1) 首先尝试从 -sources.jar 中提取原始源代码；2) 如果 sources jar 不存在，自动使用反编译器（CFR 或 Fernflower）反编译 class 文件。"
                        "支持 SNAPSHOT 版本的智能处理，会自动查找带时间戳的最新版本。"
                        "适用场景：阅读第三方库源码（如 Spring、MyBatis）、理解依赖实现细节、排查依赖相关问题。"
                        "注意：需要提供完整的 Maven 坐标（group_id、artifact_id、version）和完全限定的类名（如 org.springframework.core.SpringVersion）。"
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
                ),
                Tool(
                    name="read_project_code",
                    description=(
                        "从本地项目目录中读取指定文件的源代码或配置文件内容。"
                        "支持读取 Java 项目中的所有文件类型：Java 源代码、XML 配置、properties、YAML、JSON、Gradle 脚本、Markdown 文档等。"
                        "支持两种输入格式：1) 完全限定的类名（如 com.example.service.UserService，自动查找对应的 .java 文件）；2) 相对路径（如 src/main/resources/application.yml、pom.xml、core/src/main/java/com/example/MyClass.java）。"
                        "自动支持多模块 Maven/Gradle 项目，会递归搜索子模块中的文件。"
                        "搜索策略：优先在项目根目录查找，如果未找到则自动在所有子模块（包含 pom.xml 或 build.gradle 的目录）中搜索。"
                        "适用场景：阅读本地项目源码、查看配置文件、分析项目结构、理解业务逻辑实现。"
                        "推荐流程：先使用 list_all_project 确认项目存在 → 使用 list_project_files（建议带 file_name_pattern 参数进行模糊匹配）查看文件列表 → 使用本工具读取具体文件。"
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_name": {
                                "type": "string",
                                "description": "项目名称（例如: my-project）"
                            },
                            "file_path": {
                                "type": "string",
                                "description": "文件标识符：可以是完全限定的 Java 类名或文件相对路径。Java 类名示例: com.example.MyClass（自动查找 .java 文件）；文件路径示例: src/main/resources/application.yml、pom.xml、README.md、core/src/main/java/MyClass.java"
                            },
                            "project_dir": {
                                "type": "string",
                                "description": "项目目录路径（可选，如果未提供则使用启动时配置的路径）"
                            }
                        },
                        "required": ["project_name", "file_path"]
                    }
                ),
                Tool(
                    name="list_all_project",
                    description=(
                        "列举项目目录下所有的项目文件夹名称。"
                        "返回项目目录中所有子目录的名称列表（自动过滤隐藏目录如 .git）。"
                        "支持通过 project_name_pattern 进行项目名称模糊匹配，但使用需谨慎：如果指定的匹配模式过于严格可能遗漏目标项目。"
                        "适用场景：1) 探索未知的项目目录，了解有哪些项目可用；2) 验证项目名称是否正确，避免拼写错误；3) 当用户提供不完整的项目名时，帮助推断完整名称；4) 快速查找特定名称模式的项目。"
                        "推荐使用：这是探索本地项目的第一步，先用此工具获取所有项目列表，再使用 list_project_files 查看具体项目的文件结构。"
                        "返回格式：包含项目目录路径、项目总数和项目名称列表的 JSON 对象。"
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_dir": {
                                "type": "string",
                                "description": "项目目录路径（可选，如果未提供则使用启动时配置的路径）"
                            },
                            "project_name_pattern": {
                                "type": "string",
                                "description": "可选：项目名称模糊匹配模式（不区分大小写），用于过滤项目列表。例如：'nacos' 将匹配包含 'nacos'、'Nacos'、'NACOS' 的项目名。注意：如果匹配模式过于严格可能导致遗漏目标项目，若未找到预期结果，建议不传此参数重新查询"
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="list_project_files",
                    description=(
                        "列出 Java 项目中的源代码文件和配置文件路径。"
                        "支持两种模式：1) 列出整个项目的所有文件；2) 指定子目录（如 'core' 或 'address/src/main/java'）仅列出该目录下的文件。"
                        "返回相对路径列表，已自动过滤测试目录（src/test）、编译产物（target/build）和 IDE 配置等无关文件。"
                        "支持通过 file_name_pattern 进行文件名模糊匹配，但使用需谨慎：如果指定的匹配模式过于严格可能遗漏目标文件。"
                        "适合在阅读代码前先了解项目结构，或当项目文件过多时聚焦特定模块。"
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_name": {
                                "type": "string",
                                "description": "项目名称（例如: nacos）"
                            },
                            "sub_path": {
                                "type": "string",
                                "description": "可选：指定项目内的子目录路径，只列出该目录下的文件（例如: 'core' 或 'address/src/main/java'）。不指定则列出整个项目"
                            },
                            "file_name_pattern": {
                                "type": "string",
                                "description": "可选：文件名模糊匹配模式（不区分大小写），用于进一步过滤文件列表。例如：'Service' 将匹配包含 'service'、'Service'、'SERVICE' 的文件名。注意：如果匹配模式过于严格可能导致遗漏目标文件，若未找到预期结果，建议不传此参数重新查询"
                            },
                            "project_dir": {
                                "type": "string",
                                "description": "可选：项目所在的父目录路径。如果未提供则使用服务器启动时配置的路径"
                            }
                        },
                        "required": ["project_name"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Any) -> List[TextContent]:
            """处理工具调用"""
            try:
                if name == "read_jar_source":
                    return await self._read_jar_source(**arguments)
                elif name == "read_project_code":
                    return await self._read_project_code(**arguments)
                elif name == "list_all_project":
                    return await self._list_all_project(**arguments)
                elif name == "list_project_files":
                    return await self._list_project_files(**arguments)
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
        project_dir = self.project_dir if self.project_dir else "未配置"
        
        # 使用普通字符串拼接，避免 f-string 中嵌套 JSON 导致的语法错误
        guide_text = "# Easy Code Reader 使用指南\n\n"
        guide_text += "## 功能介绍\n\n"
        guide_text += "Easy Code Reader 是一个强大的 MCP (Model Context Protocol) 服务器，专为智能读取 Java 源代码而设计，能从本地 Maven 仓库和项目目录中提取源码。\n\n"
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
        guide_text += '        "/path/to/maven/repository",\n'
        guide_text += '        "--project-dir",\n'
        guide_text += '        "/path/to/project"\n'
        guide_text += '      ]\n'
        guide_text += '    }\n'
        guide_text += '  }\n'
        guide_text += '}\n'
        guide_text += "```\n\n"
        guide_text += "### 1. maven_repo（Maven 仓库路径）\n\n"
        guide_text += f"- **当前配置：** `{maven_repo}`\n"
        guide_text += "- **用途：** 指定本地 Maven 仓库的位置，用于查找和读取 JAR 包。\n\n"
        guide_text += "**配置优先级：**\n"
        guide_text += "1. 启动参数 `--maven-repo`（最高优先级）\n"
        guide_text += "2. 环境变量 `MAVEN_HOME`（使用 $MAVEN_HOME/repository）\n"
        guide_text += "3. 环境变量 `M2_HOME`（使用 $M2_HOME/repository）\n"
        guide_text += "4. 环境变量 `MAVEN_REPO`\n"
        guide_text += "5. 默认路径 `~/.m2/repository`（最低优先级）\n\n"
        guide_text += "### 2. project_dir（项目目录路径）\n\n"
        guide_text += f"- **当前配置：** `{project_dir}`\n"
        guide_text += "- **用途：** 指定本地项目代码的根目录，用于读取本地项目源码。\n\n"
        guide_text += "## 提供的工具\n\n"
        guide_text += "1. **read_jar_source** - 读取 Maven 依赖中的 Java 类源代码\n"
        guide_text += "2. **read_project_code** - 读取本地项目中的源代码\n"
        guide_text += "3. **list_all_project** - 列举项目目录下的所有项目\n"
        guide_text += "4. **list_project_files** - 列出项目中的源代码和配置文件\n\n"
        guide_text += "## 项目仓库\n\n"
        guide_text += "- [GitHub 仓库](https://github.com/FangYuan33/easy-code-reader)\n\n"
        guide_text += "## 技术细节\n\n"
        guide_text += f"- **反编译缓存位置：** `{maven_repo}/.../easy-code-reader/`\n"
        guide_text += "- **日志文件位置：** `src/easy_code_reader/easy_code_reader.log`\n"
        guide_text += "- **支持的文件类型：** .java, .xml, .properties, .yaml, .json, .gradle 等\n\n"
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
            error_msg = (
                f"❌ 未找到 JAR 文件: {group_id}:{artifact_id}:{version}\n\n"
                f"Maven 仓库路径: {self.maven_home}\n\n"
                f"可能的原因：\n"
                f"1. Maven 坐标信息（groupId/artifactId/version）不正确\n"
                f"2. 该依赖尚未下载到本地 Maven 仓库\n\n"
                f"建议排查步骤（按优先级）：\n"
                f"1. 如果有项目的 pom.xml 文件，使用 read_project_code 工具读取\n"
                f"   - 在 <dependencies> 部分查找正确的 groupId、artifactId 和 version\n"
                f"   - 注意：groupId 和 artifactId 可能与直观理解不同（如 'spring-core' 的 groupId 是 'org.springframework'）\n"
                f"2. 确认坐标信息正确后，重新调用 read_jar_source 工具\n"
                f"3. 如果坐标正确但 JAR 不存在，需要在项目目录执行 Maven 构建命令：\n"
                f"   - mvn dependency:resolve (下载所有依赖)\n"
                f"   - 或 mvn clean install (完整构建)"
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
                actual_jar_to_decompile, class_name, cache_jar_name=jar_path.name if actual_jar_to_decompile != jar_path else None
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
    
    async def _read_project_code(self, project_name: str, file_path: str, 
                                 project_dir: Optional[str] = None) -> List[TextContent]:
        """
        从本地项目目录中读取代码或配置文件
        支持多模块项目（Maven/Gradle），会递归搜索子模块
        支持读取所有类型的文件：Java 源代码、配置文件、脚本、文档等
        
        参数:
            project_name: 项目名称
            file_path: 文件标识符（完全限定的类名、相对路径或文件名）
            project_dir: 项目目录路径（可选）
        """
        # 输入验证
        if not project_name or not project_name.strip():
            return [TextContent(type="text", text="错误: project_name 不能为空")]
        if not file_path or not file_path.strip():
            return [TextContent(type="text", text="错误: file_path 不能为空")]
        
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
        
        # 尝试查找文件
        # 1. 如果 file_path 看起来像是路径（包含 / 或文件扩展名），直接使用
        has_path_separator = '/' in file_path
        has_extension = any(file_path.endswith(ext) for ext in ['.java', '.xml', '.properties', '.yaml', 
                                                                   '.yml', '.json', '.gradle', '.md', 
                                                                   '.txt', '.sql', '.sh', '.bat', '.conf'])
        
        if has_path_separator or has_extension:
            # 优先尝试：直接在 target_dir 下查找（适用于 file_path 包含完整相对路径的情况）
            file_path_direct = target_dir / file_path
            if file_path_direct.exists() and file_path_direct.is_file():
                logger.info(f"直接在 project_dir 下找到文件: {file_path_direct}")
                return await self._return_file_content(project_name, file_path, file_path_direct)
            
            # 检查项目子目录是否存在
            project_path = target_dir / project_name
            if project_path.exists() and project_path.is_dir():
                # 在项目子目录中查找
                file_path_in_project = project_path / file_path
                if file_path_in_project.exists() and file_path_in_project.is_file():
                    return await self._return_file_content(project_name, file_path, file_path_in_project)
                
                # 在子模块中查找
                result = self._search_in_modules(project_path, file_path)
                if result:
                    return await self._return_file_content(project_name, file_path, result)
            else:
                # 项目子目录不存在，但 file_path 是路径形式，已经在 target_dir 直接查找过了
                logger.warning(f"在 {target_dir} 下未找到文件: {file_path}")
        
        # 2. 如果 file_path 没有扩展名且不包含路径分隔符，可能是 Java 类名
        # 将类名转换为路径，搜索可能的 .java 文件
        if not has_extension and not has_path_separator:
            # 支持 Java 类名格式: com.example.MyClass -> com/example/MyClass.java
            class_path = file_path.replace('.', '/')
            
            # 常见的源代码路径模式
            search_patterns = [
                f"src/main/java/{class_path}.java",
                f"src/{class_path}.java",
                f"{class_path}.java",
            ]
            
            # 检查项目子目录是否存在
            project_path = target_dir / project_name
            if project_path.exists() and project_path.is_dir():
                # 尝试各种路径模式 - 在项目子目录中
                for pattern in search_patterns:
                    file_path_pattern = project_path / pattern
                    if file_path_pattern.exists() and file_path_pattern.is_file():
                        return await self._return_file_content(project_name, file_path, file_path_pattern)
                
                # 在子模块中搜索
                for pattern in search_patterns:
                    result = self._search_in_modules(project_path, pattern)
                    if result:
                        return await self._return_file_content(project_name, file_path, result)
            else:
                # 项目子目录不存在，尝试直接在 target_dir 下搜索
                logger.info(f"项目子目录 {project_path} 不存在，尝试在 {target_dir} 下搜索")
                for pattern in search_patterns:
                    file_path_direct = target_dir / pattern
                    if file_path_direct.exists() and file_path_direct.is_file():
                        logger.info(f"在 project_dir 下找到文件: {file_path_direct}")
                        return await self._return_file_content(project_name, file_path, file_path_direct)
        else:
            # 3. 如果有扩展名但不是标准路径，尝试在常见目录中查找
            # 例如：application.yml, pom.xml 等
            project_path = target_dir / project_name
            if project_path.exists() and project_path.is_dir():
                # 尝试在常见位置查找配置文件
                common_paths = [
                    file_path,  # 项目根目录
                    f"src/main/resources/{file_path}",  # resources 目录
                    f"src/{file_path}",  # src 目录
                    f"config/{file_path}",  # config 目录
                ]
                
                for common_path in common_paths:
                    file_path_common = project_path / common_path
                    if file_path_common.exists() and file_path_common.is_file():
                        return await self._return_file_content(project_name, file_path, file_path_common)
                
                # 在子模块中搜索
                for common_path in common_paths:
                    result = self._search_in_modules(project_path, common_path)
                    if result:
                        return await self._return_file_content(project_name, file_path, result)
            else:
                # 项目子目录不存在，尝试直接在 target_dir 下搜索
                logger.info(f"项目子目录 {project_path} 不存在，尝试在 {target_dir} 下搜索常见路径")
                for common_path in [file_path, f"src/main/resources/{file_path}", f"src/{file_path}"]:
                    file_path_direct = target_dir / common_path
                    if file_path_direct.exists() and file_path_direct.is_file():
                        logger.info(f"在 project_dir 下找到文件: {file_path_direct}")
                        return await self._return_file_content(project_name, file_path, file_path_direct)
        
        # 如果找不到文件，返回错误信息
        logger.warning(f"在项目 {project_name} 中未找到文件: {file_path}")
        return [TextContent(
            type="text",
            text=f"错误: 在项目 {project_name} 中未找到文件 {file_path}\n\n"
                 f"建议排查步骤：\n"
                 f"1. 优先使用 list_project_files 工具并传入 file_name_pattern 参数进行文件名模糊匹配（推荐）\n"
                 f"   - 例如：如果要查找 UserService.java，可以传入 file_name_pattern='UserService'\n"
                 f"   - 这样可以快速定位文件，减少返回的文件数量，节省上下文\n"
                 f"2. 如果模糊匹配未找到，再使用 list_project_files 不传 file_name_pattern 查看完整文件列表\n"
                 f"3. 确认文件路径后，使用正确的相对路径重新调用 read_project_code"
        )]
    
    def _search_in_modules(self, project_path: Path, relative_path: str) -> Optional[Path]:
        """
        在多模块项目的子模块中搜索文件
        
        参数:
            project_path: 项目根目录路径
            relative_path: 相对路径（如 src/main/java/com/example/MyClass.java）
        
        返回:
            找到的文件路径，未找到则返回 None
        """
        try:
            # 查找所有子目录
            for subdir in project_path.iterdir():
                # 跳过隐藏目录和常见的非模块目录
                if not subdir.is_dir() or subdir.name.startswith('.') or subdir.name in ['target', 'build', 'node_modules', 'dist']:
                    continue
                
                # 检查是否是 Maven 或 Gradle 模块（包含 pom.xml 或 build.gradle）
                if not ((subdir / 'pom.xml').exists() or (subdir / 'build.gradle').exists() or (subdir / 'build.gradle.kts').exists()):
                    continue
                
                # 在模块中查找文件
                file_path = subdir / relative_path
                if file_path.exists() and file_path.is_file():
                    return file_path
        except Exception as e:
            logger.error(f"搜索子模块时出错: {e}", exc_info=True)
        
        return None
    
    async def _return_file_content(self, project_name: str, class_name: str, file_path: Path) -> List[TextContent]:
        """
        读取文件内容并返回
        
        参数:
            project_name: 项目名称
            class_name: 类名
            file_path: 文件路径
        
        返回:
            包含文件内容的响应
        """
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
            logger.error(f"读取文件失败 {file_path}: {str(e)}", exc_info=True)
            return [TextContent(type="text", text=f"读取文件时出错: {str(e)}")]
    
    async def _list_all_project(self, project_dir: Optional[str] = None, 
                                 project_name_pattern: Optional[str] = None) -> List[TextContent]:
        """
        列举项目目录下所有的项目文件夹
        
        参数:
            project_dir: 项目目录路径（可选）
            project_name_pattern: 可选，项目名称模糊匹配模式（不区分大小写）
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
            all_projects = [d.name for d in target_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
            
            # 如果指定了项目名称模式，进行模糊匹配
            if project_name_pattern:
                projects = [p for p in all_projects if project_name_pattern.lower() in p.lower()]
            else:
                projects = all_projects
            
            projects.sort()
            
            result = {
                "project_dir": str(target_dir),
                "project_name_pattern": project_name_pattern if project_name_pattern else "none",
                "total_projects": len(projects),
                "projects": projects
            }
            
            # 如果使用了项目名称模式但没有匹配到项目，添加提示
            if project_name_pattern and len(projects) == 0:
                result["hint"] = (
                    f"⚠️ 使用项目名称模式 '{project_name_pattern}' 未匹配到任何项目。\n\n"
                    "可能原因：\n"
                    "- 模式关键词不在项目名称中\n"
                    "- 项目名称拼写与模式不符\n\n"
                    "建议操作：\n"
                    "1. 不传入 project_name_pattern 参数，重新调用 list_all_project 查看完整项目列表\n"
                    "2. 从完整列表中找到正确的项目名称后再进行后续操作"
                )
                result["total_all_projects"] = len(all_projects)
            elif project_name_pattern:
                result["hint"] = (
                    f"✓ 已使用项目名称模式 '{project_name_pattern}' 进行过滤，共匹配到 {len(projects)} 个项目。\n\n"
                    "如果未找到预期的项目：\n"
                    "- 可能是模式匹配过于严格\n"
                    "- 建议不传入 project_name_pattern 参数重新调用 list_all_project 查看完整项目列表"
                )
                result["total_all_projects"] = len(all_projects)
            
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
        except Exception as e:
            logger.error(f"列举项目失败: {str(e)}", exc_info=True)
            return [TextContent(type="text", text=f"列举项目时出错: {str(e)}")]

    async def _list_project_files(self, project_name: str, sub_path: Optional[str] = None, 
                                   file_name_pattern: Optional[str] = None,
                                   project_dir: Optional[str] = None) -> List[TextContent]:
        """
        列出 Java 项目中的源代码文件和配置文件路径
        
        支持两种模式：
        1. 列出整个项目的所有文件（sub_path 为 None）
        2. 只列出指定子目录下的文件（sub_path 指定子目录路径）
        
        已自动过滤测试目录（src/test）、编译产物和不必要的文件

        参数:
            project_name: 项目名称
            sub_path: 可选，项目内的子目录路径（如 'core' 或 'address/src/main/java'）
            file_name_pattern: 可选，文件名模糊匹配模式（不区分大小写）
            project_dir: 可选，项目所在的父目录路径
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

        # 检查项目是否存在
        project_path = target_dir / project_name
        if not project_path.exists() or not project_path.is_dir():
            return [TextContent(
                type="text",
                text=f"错误: {project_name} 项目不存在，请执行 list_all_project tool 检查项目是否存在"
            )]

        # 如果指定了子路径，验证并调整起始路径
        start_path = project_path
        search_prefix = ""
        if sub_path:
            sub_path = sub_path.strip().strip('/')  # 清理路径
            start_path = project_path / sub_path
            if not start_path.exists() or not start_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"错误: 子目录 '{sub_path}' 在项目 {project_name} 中不存在"
                )]
            search_prefix = sub_path

        # 需要忽略的目录
        IGNORED_DIRS = {
            'target', 'build', 'out', 'bin',  # 编译输出目录
            'node_modules', 'dist',  # 前端相关
            '.git', '.svn', '.hg',  # 版本控制
            '.idea', '.vscode', '.eclipse', '.settings',  # IDE 配置
            '__pycache__', '.pytest_cache',  # Python 相关
            '.gradle', '.mvn',  # 构建工具缓存
            'test', 'tests'  # 测试目录
        }
        
        # 需要忽略的路径模式（相对路径）
        IGNORED_PATH_PATTERNS = [
            'src/test',  # Maven/Gradle 测试目录
        ]

        # 需要包含的文件扩展名（源代码和配置文件）
        INCLUDED_EXTENSIONS = {
            # Java 源代码
            '.java',
            # 配置文件
            '.xml', '.properties', '.yaml', '.yml', '.json', '.conf', '.config',
            # 构建脚本
            '.gradle', '.gradle.kts', '.sh', '.bat',
            # 文档
            '.md', '.txt',
            # SQL 脚本
            '.sql'
        }

        # 需要包含的特定文件名（无扩展名或特殊文件）
        INCLUDED_FILENAMES = {
            'pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle', 'settings.gradle.kts',
            'gradlew', 'mvnw', 'Dockerfile', 'Makefile', 'README', 'LICENSE'
        }

        def should_include_file(filename: str) -> bool:
            """判断文件是否应该包含在结果中"""
            # 检查特定文件名
            if filename in INCLUDED_FILENAMES:
                return True
            # 检查文件扩展名
            return any(filename.endswith(ext) for ext in INCLUDED_EXTENSIONS)

        def should_ignore_path(relative_path: str) -> bool:
            """判断路径是否应该被忽略"""
            for pattern in IGNORED_PATH_PATTERNS:
                if pattern in relative_path or relative_path.startswith(pattern):
                    return True
            return False

        # 收集所有符合条件的文件路径
        file_paths = []

        def collect_files(path: Path, relative_path: str = ""):
            """
            递归收集符合条件的文件路径
            
            参数:
                path: 当前路径
                relative_path: 相对于项目根目录的路径
            """
            try:
                for item in sorted(path.iterdir(), key=lambda p: p.name):
                    # 跳过隐藏文件和目录
                    if item.name.startswith('.') and item.name not in {'.gitignore', '.dockerignore'}:
                        continue
                    
                    if item.is_dir():
                        # 跳过需要忽略的目录
                        if item.name in IGNORED_DIRS:
                            continue
                        
                        # 构建相对路径
                        child_relative = f"{relative_path}/{item.name}" if relative_path else item.name
                        
                        # 检查路径是否应该被忽略
                        if should_ignore_path(child_relative):
                            continue
                        
                        # 递归处理子目录
                        collect_files(item, child_relative)
                    else:
                        # 只包含指定的文件类型
                        if should_include_file(item.name):
                            file_relative = f"{relative_path}/{item.name}" if relative_path else item.name
                            # 如果指定了文件名模式，进行模糊匹配
                            if file_name_pattern:
                                if file_name_pattern.lower() in item.name.lower():
                                    file_paths.append(file_relative)
                            else:
                                file_paths.append(file_relative)
            except PermissionError as e:
                logger.warning(f"无权限访问目录 {path}: {e}")
            except Exception as e:
                logger.error(f"遍历目录 {path} 时出错: {e}")

        collect_files(start_path, search_prefix)

        # 构建结果信息
        result = {
            "project_name": project_name,
            "project_dir": str(project_path),
            "search_scope": sub_path if sub_path else "entire project",
            "file_name_pattern": file_name_pattern if file_name_pattern else "none",
            "total_files": len(file_paths),
            "files": sorted(file_paths)
        }
        
        # 如果使用了文件名模式但没有匹配到文件，添加提示
        if file_name_pattern and len(file_paths) == 0:
            result["hint"] = (
                f"⚠️ 使用文件名模式 '{file_name_pattern}' 未匹配到任何文件。\n\n"
                "可能原因：\n"
                "- 模式关键词不在文件名中\n"
                "- 搜索范围（sub_path）可能不包含目标文件\n\n"
                "建议操作：\n"
                "1. 调整 file_name_pattern 为更宽泛的关键词（如 'Service' 改为 'Serv'）\n"
                "2. 不传入 file_name_pattern 参数，查看完整文件列表\n"
                "3. 检查 sub_path 参数是否正确，或不传 sub_path 在整个项目中搜索"
            )
        elif file_name_pattern:
            result["hint"] = (
                f"✓ 已使用文件名模式 '{file_name_pattern}' 进行过滤，共匹配到 {len(file_paths)} 个文件。\n\n"
                "提示：这种方式可以减少返回的文件数量，节省上下文，推荐使用。\n"
                "如果未找到预期的文件，可以调整模式或不传 file_name_pattern 查看完整列表。"
            )

        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
    
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
    
    async def run(self):
        """运行 MCP 服务器"""
        logger.info("启动 MCP 服务器...")
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
