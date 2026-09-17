"""Application service for the two JAR-reading tools."""

import logging

from .decompiler import JavaDecompiler
from .errors import ReaderError
from .io_utils import run_io
from .repository import MavenRepository
from .source import check_class, class_name, read_java, select_lines, validate_range


logger = logging.getLogger(__name__)


class SourceService:
    def __init__(self, config):
        self.repository = MavenRepository(config.maven_repo)
        self.decompiler = JavaDecompiler(config)

    async def read(self, group_id, artifact_id, version, class_name_value,
                   prefer_sources=True, start_line=None, end_line=None):
        name = class_name(class_name_value)
        validate_range(start_line, end_line)
        if type(prefer_sources) is not bool:
            raise ReaderError("INVALID_ARGUMENT", "prefer_sources 必须为布尔值")
        artifact = await run_io(self.repository.resolve, group_id, artifact_id, version)
        warnings = list(artifact.warnings)
        if artifact.binary:
            await run_io(check_class, artifact.binary, name)
        source = None
        actual_path = artifact.sources
        if prefer_sources and artifact.sources:
            try:
                source = await run_io(read_java, artifact.sources, name)
            except ReaderError as exc:
                if artifact.binary is None or exc.code == "INPUT_CHANGED":
                    raise
                warnings.append(f"{exc}；已回退到所选二进制包反编译。")
        if source is None:
            if artifact.binary is None:
                code = "CLASS_NOT_FOUND" if prefer_sources else "ARTIFACT_NOT_FOUND"
                raise ReaderError(code, "未找到目标源码或可反编译的二进制 JAR",
                                  "安装对应二进制包或检查完整类名。")
            actual_path = artifact.binary
            source = await self.decompiler.decompile_class(artifact.binary, name, cache_jar_name=artifact.cache_jar_name)
        result = await run_io(select_lines, source, start_line, end_line)
        result.update({"class_name": name, "artifact": artifact.coordinate})
        logger.debug("源码读取: requested=%s cache_version=%s jar=%s source=%s",
                     artifact.coordinate, artifact.resolved_version, actual_path, source.source_file)
        if source.source_file != name.replace(".", "/") + ".java":
            warnings.append(f"返回包含该内部类的外部类源码：{source.source_file}")
        if warnings:
            result["warnings"] = warnings
        return result
