"""
Maven Decoder MCP 服务器配置模块

提供 Maven Decoder MCP 服务器的所有配置设置，包括 Maven 仓库位置、
反编译器设置、性能参数、功能开关等。支持环境变量覆盖和运行时配置。
"""

import os
from pathlib import Path
from typing import Optional

class Config:
    """
    Maven Decoder MCP 服务器配置类
    
    这个类包含了 Maven Decoder MCP 服务器的所有配置设置。
    配置项包括：
    - Maven 仓库位置和路径设置
    - 反编译器配置和优先级
    - 搜索和分析限制
    - 缓存设置和性能优化
    - 日志配置
    - 功能开关和特性标志
    - 文件大小限制
    
    支持通过环境变量进行配置覆盖，适应不同的部署环境。
    """
    
    # Maven 仓库位置配置
    MAVEN_HOME: Path = Path.home() / ".m2" / "repository"
    
    # 从环境变量覆盖 Maven 仓库位置
    if "M2_HOME" in os.environ:
        MAVEN_HOME = Path(os.environ["M2_HOME"]) / "repository"
    elif "MAVEN_REPO" in os.environ:
        MAVEN_HOME = Path(os.environ["MAVEN_REPO"])
    
    # 服务器基础配置
    SERVER_NAME: str = "maven-decoder"  # 服务器名称
    SERVER_VERSION: str = "1.0.0"       # 版本号
    
    # 反编译器设置
    DECOMPILER_TIMEOUT: int = 30  # 反编译超时时间（秒）
    DECOMPILER_PRIORITY: list = ["cfr", "procyon", "fernflower", "javap"]  # 反编译器优先级
    
    # 搜索和分析限制
    DEFAULT_ARTIFACT_LIMIT: int = 50    # 默认构件搜索限制
    DEFAULT_SEARCH_LIMIT: int = 100     # 默认搜索结果限制
    MAX_DEPENDENCY_DEPTH: int = 5       # 最大依赖深度
    
    # 缓存设置
    ENABLE_CACHE: bool = True           # 启用缓存
    CACHE_SIZE: int = 1000             # 缓存大小
    CACHE_TTL: int = 3600              # 缓存生存时间（秒）
    
    # 日志配置
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")  # 日志级别
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # 日志格式
    
    # 性能设置
    MAX_CONCURRENT_OPERATIONS: int = 10  # 最大并发操作数
    JAR_ANALYSIS_TIMEOUT: int = 60       # JAR 分析超时时间（秒）
    
    # 功能开关
    ENABLE_DECOMPILATION: bool = True         # 启用反编译功能
    ENABLE_TRANSITIVE_DEPS: bool = True      # 启用传递依赖分析
    ENABLE_BYTECODE_ANALYSIS: bool = False   # 启用字节码分析（需要额外库）
    
    # 文件大小限制（字节）
    MAX_JAR_SIZE: int = 100 * 1024 * 1024    # 最大 JAR 文件大小：100MB
    MAX_CLASS_SIZE: int = 1024 * 1024        # 最大类文件大小：1MB
    
    @classmethod
    def validate(cls) -> bool:
        """
        验证配置设置
        
        检查配置的有效性，特别是 Maven 仓库路径是否存在和可访问。
        
        返回:
            bool: 如果配置有效返回 True，否则返回 False
        """
        if not cls.MAVEN_HOME.exists():
            print(f"警告: 在 {cls.MAVEN_HOME} 未找到 Maven 仓库")
            return False
        
        if not cls.MAVEN_HOME.is_dir():
            print(f"错误: Maven 仓库路径不是目录: {cls.MAVEN_HOME}")
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
    
    @classmethod
    def get_decompiler_config(cls) -> dict:
        """
        获取反编译器配置
        
        返回:
            dict: 包含反编译器设置的字典
        """
        return {
            "timeout": cls.DECOMPILER_TIMEOUT,
            "priority": cls.DECOMPILER_PRIORITY,
            "enabled": cls.ENABLE_DECOMPILATION
        }
    
    @classmethod
    def get_limits(cls) -> dict:
        """
        获取搜索和分析限制
        
        返回:
            dict: 包含各种限制设置的字典
        """
        return {
            "artifacts": cls.DEFAULT_ARTIFACT_LIMIT,
            "search": cls.DEFAULT_SEARCH_LIMIT,
            "dependency_depth": cls.MAX_DEPENDENCY_DEPTH,
            "max_jar_size": cls.MAX_JAR_SIZE,
            "max_class_size": cls.MAX_CLASS_SIZE
        }

# 环境特定的配置覆盖
if os.environ.get("MAVEN_DECODER_ENV") == "development":
    # 开发环境配置
    Config.LOG_LEVEL = "DEBUG"
    Config.ENABLE_BYTECODE_ANALYSIS = True
    Config.CACHE_TTL = 60  # 开发环境使用较短的缓存时间

elif os.environ.get("MAVEN_DECODER_ENV") == "production":
    # 生产环境配置
    Config.LOG_LEVEL = "WARNING"
    Config.MAX_CONCURRENT_OPERATIONS = 20
    Config.CACHE_SIZE = 5000
