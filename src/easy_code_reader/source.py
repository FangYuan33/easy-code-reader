"""Source extraction and line selection, independent of MCP and Java processes."""

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .errors import ReaderError

_CLASS_NAME = re.compile(r"(?:[^\W\d]|[$_])[\w$]*(?:\.(?:[^\W\d]|[$_])[\w$]*)*\Z", re.UNICODE)


@dataclass(frozen=True)
class JavaSource:
    code: str
    source_file: str
    source_type: str


def class_name(value):
    if not isinstance(value, str) or not value.strip():
        raise ReaderError("INVALID_ARGUMENT", "错误: class_name 不能为空")
    value = value.strip()
    if len(value) > 1024 or not _CLASS_NAME.fullmatch(value):
        raise ReaderError("INVALID_ARGUMENT", "class_name 必须为完整 Java 类名，内部类使用 Outer$Inner")
    return value


def source_candidates(name):
    path = name.replace(".", "/")
    yield path + ".java"
    while "$" in path.rsplit("/", 1)[-1]:
        path = path.rsplit("$", 1)[0]
        yield path + ".java"


def check_class(jar_path: Path, name: str):
    try:
        with zipfile.ZipFile(jar_path) as jar:
            with jar.open(name.replace(".", "/") + ".class") as stream:
                header = stream.read(10)
            if len(header) < 10 or header[:4] != b"\xca\xfe\xba\xbe":
                raise ReaderError("INVALID_JAR", f"类文件头无效: {name}")
    except KeyError as exc:
        raise ReaderError("CLASS_NOT_FOUND", f"JAR 中未找到类: {name}", "核对完整类名；内部类使用 $。") from exc
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ReaderError("INVALID_JAR", f"无法读取 JAR: {jar_path}: {exc}") from exc


def read_java_entry(archive: zipfile.ZipFile, name: str, source_type: str) -> Optional[JavaSource]:
    for candidate in source_candidates(name):
        try:
            data = archive.read(candidate)
        except KeyError:
            continue
        try:
            code = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReaderError("SOURCE_DECODE_ERROR", f"源码不是有效 UTF-8: {candidate}") from exc
        return JavaSource(code, candidate, source_type)
    return None


def read_java(jar_path: Path, name: str, source_type="sources.jar") -> Optional[JavaSource]:
    try:
        before = jar_path.stat()
        with zipfile.ZipFile(jar_path) as jar:
            source = read_java_entry(jar, name, source_type)
        after = jar_path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ReaderError("INPUT_CHANGED", f"读取期间 JAR 已更新: {jar_path}", "重新调用工具。")
        return source
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ReaderError("INVALID_JAR", f"无法读取源码包: {jar_path}: {exc}") from exc


def validate_range(start_line, end_line):
    for name, value in (("start_line", start_line), ("end_line", end_line)):
        if value is not None and (type(value) is not int or value < 1):
            raise ReaderError("INVALID_ARGUMENT", f"{name} 必须为从 1 开始的整数")
    if start_line is not None and end_line is not None and end_line < start_line:
        raise ReaderError("INVALID_ARGUMENT", "end_line 不能小于 start_line")


def select_lines(source: JavaSource, start_line=None, end_line=None):
    validate_range(start_line, end_line)
    if start_line is None and end_line is None:
        return {"code": source.code, "source_type": source.source_type}
    lines = source.code.splitlines(keepends=True)
    total = len(lines)
    start = start_line or 1
    if start_line is not None and start_line > total:
        raise ReaderError("INVALID_ARGUMENT", f"start_line 超出源码总行数 {total}")
    end = min(end_line, total) if end_line is not None else total
    code = "".join(lines[start - 1:end])
    return {"code": code, "source_type": source.source_type,
            "total_lines": total, "start_line": start if total else 0, "end_line": end,
            "is_partial": start > 1 or end < total}
