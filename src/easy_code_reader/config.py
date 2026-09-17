"""Per-server configuration; Maven installations are not local repositories."""

import math
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Mapping, Optional

from .errors import ReaderError


def _settings_repository(path: Path, env: Mapping[str, str], home: Path) -> Optional[str]:
    if not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
        node = next((n for n in root if n.tag.rsplit("}", 1)[-1] == "localRepository"), None)
        if node is None or not (node.text or "").strip():
            return None

        def substitute(match):
            name = match.group(1)
            if name == "user.home":
                return str(home)
            if name.startswith("env.") and name[4:] in env:
                return env[name[4:]]
            raise ReaderError("CONFIG_ERROR", f"无法解析 {path} 中的变量 {name}",
                              "使用 --maven-repo 显式指定仓库。")

        value = re.sub(r"\$\{([^}]+)\}", substitute, node.text.strip())
        if "${" in value:
            raise ReaderError("CONFIG_ERROR", f"无法解析 {path} 中的 localRepository")
        return value
    except (ET.ParseError, OSError) as exc:
        raise ReaderError("CONFIG_ERROR", f"无法读取 Maven settings: {path}: {exc}",
                          "修复 settings 或使用 --maven-repo。") from exc


@dataclass(frozen=True)
class Config:
    SERVER_NAME: ClassVar[str] = "easy-code-reader"
    maven_repo: Path
    decompile_timeout: float = 60.0
    cache_budget_bytes: int = 1024 ** 3

    def __post_init__(self):
        if not math.isfinite(self.decompile_timeout) or self.decompile_timeout <= 0:
            raise ReaderError("CONFIG_ERROR", "decompile_timeout 必须为正数")
        if self.cache_budget_bytes < 1:
            raise ReaderError("CONFIG_ERROR", "cache_budget_bytes 必须为正整数")

    @classmethod
    def load(cls, maven_repo_path=None, decompile_timeout=60.0, *, env=None, home=None):
        env = os.environ if env is None else env
        home = Path.home() if home is None else Path(home)
        repository = maven_repo_path or env.get("MAVEN_REPO")
        if not repository:
            repository = _settings_repository(home / ".m2/settings.xml", env, home)
        if not repository:
            maven_install = env.get("MAVEN_HOME") or env.get("M2_HOME")
            if maven_install:
                repository = _settings_repository(Path(maven_install).expanduser() / "conf/settings.xml", env, home)
        repository = repository or str(home / ".m2/repository")
        return cls(
            maven_repo=Path(repository).expanduser().resolve(),
            decompile_timeout=decompile_timeout,
        )
