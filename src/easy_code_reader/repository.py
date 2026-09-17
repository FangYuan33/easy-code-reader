"""Strict local Maven resolution shared by search and source reading."""

import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .errors import ReaderError
from .versions import MavenVersion

_COMPONENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*\Z")
_IGNORED = {"easy-code-reader", "easy-jar-reader", "cfr_temp"}


def coordinate(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReaderError("INVALID_ARGUMENT", f"错误: {name} 不能为空")
    value = value.strip()
    if len(value) > 256 or not _COMPONENT.fullmatch(value) or ".." in value:
        raise ReaderError("INVALID_ARGUMENT", f"{name} 必须为 Maven 坐标，不能包含路径或通配符")
    if name in {"group_id", "group_prefix"} and any(not part for part in value.split(".")):
        raise ReaderError("INVALID_ARGUMENT", f"{name} 包含空段")
    return value


@dataclass(frozen=True)
class ResolvedArtifact:
    group_id: str
    artifact_id: str
    version: str
    resolved_version: str
    binary: Optional[Path]
    sources: Optional[Path]
    selection: str
    warnings: tuple = ()

    @property
    def cache_jar_name(self) -> Optional[str]:
        if self.binary is None:
            return None
        return f"{self.artifact_id}-{self.resolved_version}.jar"

    @property
    def coordinate(self):
        return f"{self.group_id}:{self.artifact_id}:{self.version}"


class MavenRepository:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()

    def _within(self, path: Path) -> Path:
        actual = path.resolve()
        if not actual.is_relative_to(self.root):
            raise ReaderError("INVALID_ARGUMENT", "解析后的文件路径超出 Maven 仓库")
        return actual

    def resolve(self, group_id, artifact_id, version) -> ResolvedArtifact:
        group_id = coordinate(group_id, "group_id")
        artifact_id = coordinate(artifact_id, "artifact_id")
        version = coordinate(version, "version")
        directory = self._within(self.root / group_id.replace(".", "/") / artifact_id / version)
        files = {}
        if directory.is_dir():
            for path in directory.iterdir():
                if path.suffix == ".jar" and path.is_file():
                    files[path.name] = self._within(path)
        selected = version
        selection = "release"
        if version.endswith("-SNAPSHOT"):
            base = version[:-len("SNAPSHOT")]
            pattern = re.compile(re.escape(f"{artifact_id}-{base}") + r"(\d{8}\.\d{6})-(\d+)\.jar\Z")
            candidates = []
            for filename in files:
                match = pattern.fullmatch(filename)
                if match:
                    candidates.append((match[1], int(match[2]), filename))
            if candidates:
                filename = max(candidates)[2]
                selected = filename[len(artifact_id) + 1:-4]
                selection = "timestamp"
            else:
                selection = "snapshot"
        binary = files.get(f"{artifact_id}-{selected}.jar")
        sources = files.get(f"{artifact_id}-{selected}-sources.jar")
        if version.endswith("-SNAPSHOT"):
            normalized_binary = files.get(f"{artifact_id}-{version}.jar")
            if normalized_binary is not None:
                binary = normalized_binary
                sources = files.get(f"{artifact_id}-{version}-sources.jar") or sources
                selection = "normalized_snapshot" if selected != version else "snapshot"
        if binary is None and sources is None and version.endswith("-SNAPSHOT"):
            # Source-only repositories remain readable, preferring the normalized source archive.
            pattern = re.compile(re.escape(f"{artifact_id}-{version[:-len('SNAPSHOT')]}")
                                 + r"(\d{8}\.\d{6})-(\d+)-sources\.jar\Z")
            candidates = []
            for filename in files:
                match = pattern.fullmatch(filename)
                if match:
                    candidates.append((match[1], int(match[2]), filename))
            if candidates:
                filename = max(candidates)[2]
                selected = filename[len(artifact_id) + 1:-len("-sources.jar")]
                sources = files[filename]
        if binary is None and sources is None:
            candidates = ", ".join(sorted(files)[:5]) or "无"
            raise ReaderError("ARTIFACT_NOT_FOUND", f"未找到 JAR 文件: {group_id}:{artifact_id}:{version}",
                              f"使用 search_group_id（artifact_id={artifact_id}）核对坐标。目录中的候选: {candidates}")
        warnings = []
        # Metadata helps diagnose a stale mirror, but does not override local files.
        if selection == "timestamp":
            for metadata in sorted(directory.glob("maven-metadata*.xml")):
                self._within(metadata)
                try:
                    tree = ET.parse(metadata)
                    for entry in tree.findall(".//snapshotVersion"):
                        if entry.findtext("extension") == "jar" and not entry.findtext("classifier"):
                            value = entry.findtext("value")
                            if value and value != selected:
                                warnings.append(f"{metadata.name} 指向 {value}；已选择本地最新构建 {selected}")
                except (ET.ParseError, OSError):
                    warnings.append(f"无法核对 {metadata.name}；已按本地文件选择构建")
        return ResolvedArtifact(group_id, artifact_id, version, selected, binary, sources,
                                selection if binary else "sources_only", tuple(warnings))

    def _prefix_roots(self, prefix):
        roots = [self.root]
        if prefix:
            for part in prefix.split("."):
                roots = [self._within(child) for root in roots for child in root.iterdir()
                         if child.is_dir() and not child.is_symlink() and child.name.lower() == part.lower()]
        return roots

    def search(self, artifact_id, group_prefix=None, version_hint=None):
        artifact_id = coordinate(artifact_id, "artifact_id")
        group_prefix = coordinate(group_prefix, "group_prefix") if group_prefix is not None else None
        version_hint = coordinate(version_hint, "version_hint") if version_hint is not None else None
        if not self.root.is_dir():
            raise ReaderError("CONFIG_ERROR", f"Maven 仓库不存在或不是目录: {self.root}")
        start = time.monotonic()
        matches = []
        scanned = 0
        warnings = []

        def on_error(error):
            warnings.append(f"部分目录无法读取: {error.filename}")

        for root in self._prefix_roots(group_prefix):
            for current, directories, _ in os.walk(root, followlinks=False, onerror=on_error):
                scanned += 1
                directories[:] = sorted(name for name in directories
                                        if not name.startswith(".") and name not in _IGNORED
                                        and not (Path(current) / name).is_symlink())
                if Path(current).name != artifact_id:
                    continue
                group_id = ".".join(Path(current).parent.relative_to(self.root).parts)
                if not group_id:
                    continue
                if group_prefix and not (group_id.lower() == group_prefix.lower()
                                         or group_id.lower().startswith(group_prefix.lower() + ".")):
                    continue
                versions = []
                for version in directories:
                    if version_hint and version_hint.lower() not in version.lower():
                        continue
                    try:
                        self.resolve(group_id, artifact_id, version)
                        versions.append(version)
                    except ReaderError as exc:
                        if exc.code not in {"ARTIFACT_NOT_FOUND", "INVALID_ARGUMENT"}:
                            raise
                if versions:
                    matches.append({"group_id": group_id,
                                    "matched_versions": sorted(sorted(versions), key=MavenVersion, reverse=True)[:10],
                                    "total_versions": len(versions)})
                # An artifact name can also be a group segment; keep walking.
        matches.sort(key=lambda match: match["group_id"])
        if not matches:
            hint = "❌ 未找到匹配。可能原因：依赖未安装或 group_prefix/version_hint 过滤过严。建议操作：核对 artifact_id，放宽过滤后重试。"
        elif len(matches) == 1:
            hint = "✅ 找到唯一匹配；使用该 group_id 和 matched_versions 中的版本调用 read_jar_source。"
        else:
            hint = "🎯 找到多个候选；建议选择正确的 group_id 和版本后调用 read_jar_source。"
        result = {"artifact_id": artifact_id, "group_prefix": group_prefix or "none",
                  "version_hint": version_hint or "none", "total_matches": len(matches), "matches": matches,
                  "search_stats": {"scanned_groups": scanned, "scanned_directories": scanned,
                                   "elapsed_seconds": round(time.monotonic() - start, 4)},
                  "hint": hint}
        if warnings:
            result["warnings"] = warnings
        return result
