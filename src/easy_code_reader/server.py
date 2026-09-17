"""MCP stdio adapter exposing only search_group_id and read_jar_source."""

import asyncio
import json
import logging

from jsonschema import ValidationError, validate
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, Resource, TextContent, Tool

from .config import Config
from .errors import ReaderError
from .io_utils import run_io
from .service import SourceService

logger = logging.getLogger(__name__)


def _text(result):
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


class EasyCodeReaderServer:
    def __init__(self, maven_repo_path=None, decompile_timeout=60.0, *, config=None):
        self.config = config or Config.load(maven_repo_path, decompile_timeout=decompile_timeout)
        self.maven_home = self.config.maven_repo
        self.service = SourceService(self.config)
        self.decompiler = self.service.decompiler
        self.server = Server(Config.SERVER_NAME)
        self.setup_handlers()

    def setup_handlers(self):
        @self.server.list_tools()
        async def handle_list_tools():
            coordinate_properties = {
                "group_id": {"type": "string", "minLength": 1, "description": "Maven groupId，如 org.springframework"},
                "artifact_id": {"type": "string", "minLength": 1, "description": "Maven artifactId，如 spring-core"},
                "version": {"type": "string", "minLength": 1, "description": "Maven 版本；SNAPSHOT 优先读取普通包，使用最新时间戳文件名管理缓存"},
            }
            return [
                Tool(name="search_group_id", description=(
                    "在本地 Maven 仓库中按 artifact_id 查找 groupId 和可读版本，包括 SNAPSHOT 和仅源码包。"
                    "group_prefix 是完整 groupId 前缀（如 org.springframework），可缩小扫描范围。"
                    "version_hint 为可选版本子串；每次调用直接搜索当前 Maven 仓库。"
                    "选择结果中的坐标后使用 read_jar_source 读取源码。"),
                    inputSchema={"type": "object", "additionalProperties": False, "properties": {
                        "artifact_id": coordinate_properties["artifact_id"],
                        "group_prefix": {"type": "string", "minLength": 1, "description": "完整 groupId 前缀，不区分大小写"},
                        "version_hint": {"type": "string", "minLength": 1, "description": "版本子串，不区分大小写；不确定时省略"},
                    }, "required": ["artifact_id"]}),
                Tool(name="read_jar_source", description=(
                    "读取 Maven JAR 中指定 Java 类的源码。优先使用 sources JAR；SNAPSHOT 优先读取普通包，普通包不存在时回退时间戳包。"
                    "内部类使用 Outer$Inner，必要时返回外部类源码并附简短提示。"
                    "默认返回全文；start_line/end_line 为从 1 开始、包含首尾的可选行范围。"
                    "全文结果包含 class_name、artifact、source_type、code；分段读取附带行数信息，失败设置 isError=true。"),
                    inputSchema={"type": "object", "additionalProperties": False, "properties": {
                        **coordinate_properties,
                        "class_name": {"type": "string", "minLength": 1, "description": "完整 Java 类名；内部类使用 $"},
                        "prefer_sources": {"type": "boolean", "default": True},
                        "start_line": {"type": "integer", "minimum": 1},
                        "end_line": {"type": "integer", "minimum": 1},
                    }, "required": ["group_id", "artifact_id", "version", "class_name"]}),
            ]

        @self.server.call_tool(validate_input=False)
        async def handle_call_tool(name, arguments):
            try:
                definitions = {tool.name: tool for tool in await handle_list_tools()}
                if name not in definitions:
                    raise ReaderError("UNKNOWN_TOOL", f"未知工具: {name}")
                validate(arguments, definitions[name].inputSchema)
                if name == "read_jar_source":
                    content = await self._read_jar_source(**arguments)
                elif name == "search_group_id":
                    content = await self._search_group_id(**arguments)
                else:
                    raise ReaderError("UNKNOWN_TOOL", f"未知工具: {name}")
                return CallToolResult(content=content, isError=False)
            except ReaderError as exc:
                return CallToolResult(content=_text(exc.as_dict()), isError=True)
            except ValidationError as exc:
                error = ReaderError("INVALID_ARGUMENT", exc.message)
                return CallToolResult(content=_text(error.as_dict()), isError=True)
            except TypeError as exc:
                return CallToolResult(content=_text(ReaderError("INVALID_ARGUMENT", str(exc)).as_dict()), isError=True)
            except Exception:
                logger.exception("工具 %s 执行失败", name)
                return CallToolResult(content=_text(ReaderError("INTERNAL_ERROR", "读取失败，请检查 stderr 日志").as_dict()),
                                      isError=True)

        @self.server.list_resources()
        async def handle_list_resources():
            return [Resource(uri="easy-code-reader://guide", name="Easy Code Reader 使用指南",
                             description="两个 JAR 读取工具的配置与用法", mimeType="text/markdown")]

        @self.server.read_resource()
        async def handle_read_resource(uri):
            if str(uri) != "easy-code-reader://guide":
                raise ValueError(f"Unknown resource URI: {uri}")
            return self._get_guide_content()

    def _get_guide_content(self):
        example = {"mcpServers": {"easy-code-reader": {"command": "uvx", "args": [
            "easy-code-reader", "--maven-repo", str(self.config.maven_repo)]}}}
        return (
            "# Easy Code Reader 使用指南\n\n"
            "## 工具\n\n"
            "- `search_group_id`：按 artifact_id 查坐标；group_prefix 为完整前缀，每次调用直接搜索 Maven 仓库。\n"
            "- `read_jar_source`：按完整坐标和类名读取源码；默认全文，start_line/end_line 可指定包含首尾的行范围。\n\n"
            "## 版本与来源\n\n"
            "SNAPSHOT 优先读取普通主包及普通 sources 包；主包不存在时读取最新时间戳主包。最新时间戳和数字构建号用于缓存命名，只有普通包时使用普通文件名。"
            "内部类使用 Outer$Inner，返回外部类源码时会附带简短提示。全文结果仅包含类名、坐标、来源和代码；分段读取附带行范围。"
            "仅源码包也可读取；失败返回 isError=true 和错误码，不生成占位代码。\n\n"
            "## 配置\n\n"
            "Maven 路径优先级：--maven-repo → MAVEN_REPO → 用户 settings.xml → Maven 全局 settings.xml → ~/.m2/repository。"
            "MAVEN_HOME/M2_HOME 用于查找全局 settings，不代表依赖仓库。\n\n"
            "反编译缓存位于实际 JAR 所在版本目录的 `easy-code-reader/` 中，普通版本与原始 JAR 同名，SNAPSHOT 优先使用最新时间戳包名。"
            "每个版本目录的缓存预算默认 1 GiB；通过文件大小和修改时间校验同名输入。旧格式缓存首次访问时重新生成。\n"
            f"反编译预算：{self.config.decompile_timeout:g} 秒（--decompile-timeout）；"
            "不设置反编译并发数量上限。日志写入 stderr。\n\n"
            "```json\n" + json.dumps(example, ensure_ascii=False, indent=2) + "\n```\n"
        )

    async def _read_jar_source(self, group_id, artifact_id, version, class_name,
                               prefer_sources=True, start_line=None, end_line=None):
        return _text(await self.service.read(group_id, artifact_id, version, class_name,
                                              prefer_sources, start_line, end_line))

    async def _search_group_id(self, artifact_id, group_prefix=None, version_hint=None):
        return _text(await run_io(self.service.repository.search, artifact_id, group_prefix, version_hint))

    # Keep thin helpers for callers testing Maven path resolution independently.
    def _get_jar_path(self, group_id, artifact_id, version):
        return self.service.repository.resolve(group_id, artifact_id, version).binary

    def _get_sources_jar_path(self, group_id, artifact_id, version):
        return self.service.repository.resolve(group_id, artifact_id, version).sources

    async def run(self):
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())


async def main(maven_repo_path=None, decompile_timeout=60.0):
    await EasyCodeReaderServer(maven_repo_path, decompile_timeout=decompile_timeout).run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
