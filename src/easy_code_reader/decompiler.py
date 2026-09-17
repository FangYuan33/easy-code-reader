"""Asynchronous whole-JAR decompilation with JAR-name disk caching."""

import asyncio
import logging
import os
import re
import signal
import zipfile
from pathlib import Path

from .cache import SourceCache
from .config import Config
from .errors import ReaderError
from .io_utils import run_io, temporary_directory
from .source import check_class, class_name

logger = logging.getLogger(__name__)


class JavaDecompiler:
    def __init__(self, config=None):
        self.config = config or Config.load()
        package = Path(__file__).parent / "decompilers"
        self.cfr_jar = package / "cfr.jar" if (package / "cfr.jar").is_file() else None
        self.fernflower_jar = package / "fernflower.jar" if (package / "fernflower.jar").is_file() else None
        self.java_version = None

    def _cache_for(self, jar_path: Path) -> SourceCache:
        """Keep each artifact version's cache beside its original JARs."""
        return SourceCache(jar_path.resolve().parent / "easy-code-reader", self.config.cache_budget_bytes)

    async def _run_process(self, command, cwd=None):
        """Drain bounded diagnostics and reap the child on cancellation or timeout."""
        kwargs = {"start_new_session": True} if os.name == "posix" else {}
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(
            *map(str, command), cwd=cwd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, **kwargs))
        try:
            process = await asyncio.shield(spawn)
        except asyncio.CancelledError:
            process = await spawn
            await self._stop(process)
            raise

        async def drain(stream):
            tail = b""
            while chunk := await stream.read(8192):
                tail = (tail + chunk)[-65536:]
            return tail.decode("utf-8", errors="replace")

        stdout = asyncio.create_task(drain(process.stdout))
        stderr = asyncio.create_task(drain(process.stderr))
        try:
            code = await process.wait()
            return code, await stdout, await stderr
        finally:
            if process.returncode is None:
                await self._stop(process)
            await asyncio.gather(stdout, stderr, return_exceptions=True)

    async def _stop(self, process):
        if process.returncode is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        await process.wait()

    async def _detect_java_version(self):
        try:
            code, stdout, stderr = await asyncio.wait_for(self._run_process(["java", "-version"]), 5)
            match = re.search(r'version\s+"(\d+)(?:\.(\d+))?', stdout + stderr)
            if code == 0 and match:
                self.java_version = int(match[2]) if match[1] == "1" and match[2] else int(match[1])
        except (OSError, asyncio.TimeoutError):
            self.java_version = None
        return self.java_version

    async def decompile_class(self, jar_path: Path, name: str, cache_jar_name: str | None = None):
        name = class_name(name)
        try:
            return await asyncio.wait_for(self._decompile(jar_path, name, cache_jar_name), self.config.decompile_timeout)
        except asyncio.TimeoutError as exc:
            raise ReaderError("DECOMPILE_TIMEOUT", f"反编译超过 {self.config.decompile_timeout:g} 秒",
                              "使用 --decompile-timeout 增加预算，或提供 sources JAR。") from exc
        except ReaderError:
            raise
        except OSError as exc:
            raise ReaderError("CACHE_UNAVAILABLE", f"无法访问输入或缓存: {exc}",
                              "检查原始 JAR 的读取权限及其 Maven 版本目录中 easy-code-reader 缓存目录的写入权限。") from exc

    async def _decompile(self, jar_path, name, cache_jar_name=None):
        jar_path = await run_io(jar_path.resolve)
        input_stat = await run_io(jar_path.stat)
        cache = self._cache_for(jar_path)
        cache_name = cache_jar_name or jar_path.name
        await run_io(check_class, jar_path, name)
        cached = await run_io(cache.read, jar_path, name, cache_name)
        if cached:
            return cached
        await run_io(cache.prepare)
        # Only intermediate output goes into the request workspace.
        async with temporary_directory(cache.root) as workspace:
            java = await self._detect_java_version()
            engines = [("cfr", self.cfr_jar, 6), ("fernflower", self.fernflower_jar, 21)]
            if java and java >= 21:
                engines.reverse()
            attempted = []
            for kind, engine, minimum in engines:
                if engine is None or java is None or java < minimum:
                    continue
                output = workspace / kind
                await run_io(output.mkdir)
                command = ["java", "-jar", engine, jar_path]
                command += ["--outputdir", output] if kind == "cfr" else [output]
                try:
                    status, stdout, stderr = await self._run_process(command, cwd=workspace)
                    if status != 0:
                        attempted.append(f"{kind}: {(stderr or stdout)[-1000:]}")
                        continue
                    generated = output if kind == "cfr" else output / jar_path.name
                    result = await run_io(cache.publish, jar_path, input_stat, generated, workspace, name, cache_name)
                    await run_io(cache.prune, cache_name)
                    return result
                except ReaderError as exc:
                    if exc.code == "INPUT_CHANGED":
                        raise
                    attempted.append(f"{kind}: {exc}")
                except (OSError, ValueError, zipfile.BadZipFile) as exc:
                    attempted.append(f"{kind}: {exc}")
            if attempted:
                raise ReaderError("DECOMPILE_FAILED", "反编译失败", "；".join(attempted))
            raise ReaderError("DECOMPILER_UNAVAILABLE", "没有当前 Java 环境可用的反编译器",
                              "安装 JDK 并加入 PATH；CFR 需要 Java 6+，随包 Fernflower 需要 Java 21+。")
