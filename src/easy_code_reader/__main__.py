"""
Entry point for running the Easy Code Reader MCP server as a module.

支持通过 python -m easy_code_reader 或 uvx easy-code-reader 启动服务器。
"""

import argparse
import asyncio
from .server import main as server_main


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='Easy Code Reader MCP Server - 读取 Maven JAR 包中的 Java 源代码'
    )
    parser.add_argument(
        '--maven-repo',
        type=str,
        help='自定义 Maven 仓库路径（默认: ~/.m2/repository）',
        default=None
    )
    return parser.parse_args()


def main():
    """主入口函数，用于 uvx 和直接运行"""
    args = parse_args()
    asyncio.run(server_main(maven_repo_path=args.maven_repo))


if __name__ == "__main__":
    main()
