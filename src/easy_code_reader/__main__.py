"""CLI entry point for the stdio MCP server."""

import argparse
import asyncio
import logging

from .errors import ReaderError
from .server import main as server_main


def parse_args():
    parser = argparse.ArgumentParser(description="Easy Code Reader - 读取 Maven JAR 中的 Java 源码")
    parser.add_argument("--maven-repo", help="Maven 仓库路径；省略时读取 MAVEN_REPO/settings.xml")
    parser.add_argument("--decompile-timeout", type=float, default=60.0, help="反编译请求预算（秒，默认 60）")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(server_main(args.maven_repo, decompile_timeout=args.decompile_timeout))
    except ReaderError as exc:
        raise SystemExit(f"{exc.code}: {exc}. {exc.hint}") from exc


if __name__ == "__main__":
    main()
