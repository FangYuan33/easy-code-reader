"""JAR-name disk caching with small file stamps and atomic publication."""

import json
import logging
import os
import zipfile
from pathlib import Path
from typing import Optional

from .errors import ReaderError
from .source import JavaSource, read_java, read_java_entry

logger = logging.getLogger(__name__)
# Regenerate older output that may have lost Fernflower generic signatures.
_FORMAT = 3
_META = "META-INF/easy-code-reader.json"


def _signature(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _metadata(stat):
    return {"format": _FORMAT, "source_size": stat.st_size, "source_mtime_ns": stat.st_mtime_ns}


class SourceCache:
    def __init__(self, root: Path, budget=1024 ** 3):
        self.root = root
        self.budget = budget

    def prepare(self):
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, jar_path: Path, cache_jar_name: Optional[str] = None) -> Path:
        filename = cache_jar_name or jar_path.name
        if Path(filename).name != filename or "\\" in filename or not filename.endswith(".jar"):
            raise ReaderError("INVALID_ARGUMENT", "缓存名称必须是 JAR 文件名")
        return self.root / filename

    def read(self, jar_path: Path, name: str, cache_jar_name: Optional[str] = None) -> Optional[JavaSource]:
        path = self.path_for(jar_path, cache_jar_name)
        if not path.is_file():
            return None
        try:
            before = jar_path.stat()
            # Read metadata and source through the same handle if another writer replaces the cache.
            with zipfile.ZipFile(path) as archive:
                if json.loads(archive.read(_META)) != _metadata(before):
                    return None
                source = read_java_entry(archive, name, "decompiled_cache")
            if _signature(before) != _signature(jar_path.stat()):
                return None
            if source:
                try:
                    os.utime(path, None)
                except OSError:
                    pass  # A readable cache remains usable without write permission.
            return source
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, ReaderError):
            logger.debug("缓存不可用，将重新生成: %s", path)
            return None

    def publish(self, jar_path: Path, input_stat, generated: Path, workspace: Path, name: str,
                cache_jar_name: Optional[str] = None) -> JavaSource:
        output = workspace / "validated.jar"
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            if generated.is_dir():
                for source in sorted(generated.rglob("*.java")):
                    if source.is_file() and not source.is_symlink():
                        archive.write(source, source.relative_to(generated).as_posix())
            else:
                with zipfile.ZipFile(generated) as incoming:
                    for entry in incoming.infolist():
                        if entry.filename.endswith(".java"):
                            archive.writestr(entry.filename, incoming.read(entry))
            archive.writestr(_META, json.dumps(_metadata(input_stat)))
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None:
                raise ReaderError("DECOMPILE_FAILED", "反编译结果 ZIP 校验失败")
        result = read_java(output, name, "decompiled")
        if result is None:
            raise ReaderError("DECOMPILE_FAILED", f"反编译结果缺少目标源码: {name}")
        if _signature(input_stat) != _signature(jar_path.stat()):
            raise ReaderError("INPUT_CHANGED", "反编译期间原始 JAR 已更新", "重新调用工具。")
        os.replace(output, self.path_for(jar_path, cache_jar_name))
        return result

    def prune(self, protected_name=None):
        """Best-effort LRU for our completed archives; workspaces and old formats are untouched."""
        entries = []
        for path in self.root.glob("*.jar"):
            try:
                with zipfile.ZipFile(path) as archive:
                    metadata = json.loads(archive.read(_META))
                    if not isinstance(metadata, dict) or metadata.get("format") != _FORMAT:
                        continue
                stat = path.stat()
                entries.append((stat.st_mtime_ns, stat.st_size, path))
            except (OSError, ValueError, KeyError, zipfile.BadZipFile):
                continue
        total = sum(size for _, size, _ in entries)
        for access_time, size, path in sorted(entries):
            if total <= self.budget:
                break
            if path.name == protected_name:
                continue
            try:
                # A different request may have just read or replaced this archive.
                if path.stat().st_mtime_ns != access_time:
                    continue
                path.unlink()
                total -= size
            except OSError:
                continue
