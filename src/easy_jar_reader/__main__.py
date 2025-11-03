"""Entry point for running the Easy JAR Reader MCP server as a module."""

import argparse
import asyncio
from .server import main


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='Easy JAR Reader MCP Server - 从 Maven 依赖中读取 Java 源代码'
    )
    parser.add_argument(
        '--maven-repo',
        type=str,
        help='自定义 Maven 仓库路径（默认: ~/.m2/repository）',
        default=None
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(maven_repo_path=args.maven_repo))
