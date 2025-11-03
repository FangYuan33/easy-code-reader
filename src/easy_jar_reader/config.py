"""
Easy JAR Reader MCP 服务器配置模块

提供配置设置，包括 Maven 仓库位置、反编译器设置等。
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """
    Easy JAR Reader MCP 服务器配置类
    
    配置项包括：
    - Maven 仓库位置和路径设置
    - 反编译器配置和优先级
    - 响应大小限制
    """
    
    # Maven 仓库位置配置
    MAVEN_HOME: Path = Path.home() / ".m2" / "repository"
    
    # 从环境变量覆盖 Maven 仓库位置
    if "M2_HOME" in os.environ:
        MAVEN_HOME = Path(os.environ["M2_HOME"]) / "repository"
    elif "MAVEN_REPO" in os.environ:
        MAVEN_HOME = Path(os.environ["MAVEN_REPO"])
    
    # 服务器基础配置
    SERVER_NAME: str = "easy-jar-reader"
    SERVER_VERSION: str = "0.1.0"
    
    # 反编译器设置
    DECOMPILER_TIMEOUT: int = 30  # 反编译超时时间（秒）
    DECOMPILER_PRIORITY: list = ["fernflower", "cfr", "procyon", "javap"]  # 反编译器优先级
    
    # 响应管理器配置
    MAX_RESPONSE_SIZE: int = int(os.getenv('MCP_MAX_RESPONSE_SIZE', '50000'))
    MAX_ITEMS_PER_PAGE: int = int(os.getenv('MCP_MAX_ITEMS_PER_PAGE', '20'))
    MAX_TEXT_LENGTH: int = int(os.getenv('MCP_MAX_TEXT_LENGTH', '10000'))
    MAX_LINES: int = int(os.getenv('MCP_MAX_LINES', '500'))
    
    @classmethod
    def validate(cls) -> bool:
        """
        验证配置设置
        
        检查配置的有效性，特别是 Maven 仓库路径是否存在和可访问。
        
        返回:
            bool: 如果配置有效返回 True，否则返回 False
        """
        if not cls.MAVEN_HOME.exists():
            return False
        
        if not cls.MAVEN_HOME.is_dir():
            return False
        
        return True
    
    @classmethod
    def get_maven_home(cls) -> Path:
        """
        获取 Maven 仓库主目录
        
        返回:
            Path: Maven 仓库目录路径
        """
        return cls.MAVEN_HOME
    
    @classmethod
    def set_maven_home(cls, path: str) -> None:
        """
        设置自定义 Maven 仓库位置
        
        参数:
            path: Maven 仓库的新路径
        """
        cls.MAVEN_HOME = Path(path)
