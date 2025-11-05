# Easy Code Reader

一个用于从 Maven 依赖中读取 Java 源代码的 MCP (Model Context Protocol) 服务器。

[![PyPI version](https://badge.fury.io/py/easy-code-reader.svg)](https://badge.fury.io/py/easy-code-reader)
[![Python Version](https://img.shields.io/pypi/pyversions/easy-code-reader)](https://pypi.org/project/easy-code-reader/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **📢 发布状态**: 
> - ✅ **已发布到 PyPI** - 可以直接使用 `uvx easy-code-reader` 开箱即用
> - 🔄 **未发布到 PyPI** - 需要先从 GitHub 安装（见下方说明）
>
> 请根据实际发布状态选择对应的安装方式。

## 功能特性

- 📦 **从 Maven 仓库读取源代码**：自动从本地 Maven 仓库（`~/.m2/repository`）中查找和读取 JAR 包源代码
- 🔍 **智能源码提取**：优先从 sources jar 提取源码，如果不存在则自动反编译 class 文件
- 🛠️ **Fernflower 反编译器支持**：使用 IntelliJ IDEA 的 Fernflower 反编译器
- ⚡ **智能缓存机制**：反编译结果缓存在 JAR 包同目录的 `easy-code-reader/` 下，避免重复反编译
- ⚙️ **自定义 Maven 路径**：支持配置自定义的 Maven 仓库路径
- 📄 **智能内容管理**：自动摘要大型源文件，支持行数限制

## 前置要求

- Python 3.10 或更高版本
- Java Development Kit (JDK) - 用于运行反编译器
- [uv](https://github.com/astral-sh/uv) - Python 包和项目管理工具（推荐）

## 安装

### ⚡ 方式 1: 使用 uvx（推荐 - 开箱即用）

> **注意**: 此方式仅在包发布到 PyPI 后可用

[uv](https://github.com/astral-sh/uv) 是一个极快的 Python 包和项目管理工具。使用 `uvx` 可以无需预先安装，直接运行：

```bash
# 无需安装，直接运行
uvx easy-code-reader

# 或指定自定义 Maven 仓库
uvx easy-code-reader --maven-repo /path/to/maven/repository
```

#### 首次使用 uv？

如果您还没有安装 uv，可以通过以下方式快速安装：

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或使用 pip
pip install uv
```

### 📦 方式 2: 从 PyPI 安装

> **注意**: 此方式仅在包发布到 PyPI 后可用

```bash
# 使用 uv 安装（推荐）
uv pip install easy-code-reader

# 或使用 pip 安装
pip install easy-code-reader
```

安装后可以直接运行：

```bash
easy-code-reader
easy-code-reader --maven-repo /path/to/maven/repository
```

### 🔧 方式 3: 从 GitHub 安装（当前可用）

在包发布到 PyPI 之前，或者您想使用最新开发版本，可以从 GitHub 安装：

```bash
# 使用 uv 安装
uv pip install git+https://github.com/FangYuan33/easy-code-reader.git

# 或使用 pip 安装
pip install git+https://github.com/FangYuan33/easy-code-reader.git
```

### 🛠️ 方式 4: 本地开发安装

克隆仓库并以开发模式安装：

```bash
# 克隆仓库
git clone https://github.com/FangYuan33/easy-code-reader.git
cd easy-code-reader

# 使用 uv 安装
uv pip install -e .

# 或使用 pip 安装
pip install -e .

# 开发模式安装（包含测试工具）
uv pip install -e ".[dev]"
# 或
pip install -e ".[dev]"
```

## 使用方法

### 快速开始（使用 uvx - 推荐）

使用 `uvx` 可以直接运行 Easy Code Reader，无需手动安装：

```bash
# 使用默认 Maven 仓库路径 (~/.m2/repository)
uvx easy-code-reader

# 指定自定义 Maven 仓库路径
uvx easy-code-reader --maven-repo /path/to/your/maven/repository

# 查看帮助信息
uvx easy-code-reader --help
```

### 使用已安装的包

如果您已经通过 pip 或 uv 安装了包，可以直接运行：

```bash
# 使用默认 Maven 仓库路径
easy-code-reader

# 指定自定义 Maven 仓库路径
easy-code-reader --maven-repo /path/to/your/maven/repository

# 或使用 Python 模块方式运行
python -m easy_code_reader
python -m easy_code_reader --maven-repo /path/to/your/maven/repository
```

### 在 MCP 客户端中配置

Easy Code Reader 实现了 Model Context Protocol，可以与支持 MCP 的客户端（如 Claude Desktop）集成。

#### Claude Desktop 配置

编辑 Claude Desktop 的配置文件：
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

##### 方式 1：使用 uvx（推荐 - 开箱即用）

```json
{
  "mcpServers": {
    "easy-code-reader": {
      "command": "uvx",
      "args": ["easy-code-reader"],
      "env": {}
    }
  }
}
```

##### 使用 uvx 并指定自定义 Maven 路径：

```json
{
  "mcpServers": {
    "easy-code-reader": {
      "command": "uvx",
      "args": [
        "easy-code-reader",
        "--maven-repo",
        "/custom/path/to/maven/repository"
      ],
      "env": {}
    }
  }
}
```

##### 方式 2：使用已安装的包

```json
{
  "mcpServers": {
    "easy-code-reader": {
      "command": "easy-code-reader",
      "args": [],
      "env": {}
    }
  }
}
```

##### 方式 3：使用 Python 模块

```json
{
  "mcpServers": {
    "easy-code-reader": {
      "command": "python",
      "args": ["-m", "easy_code_reader"],
      "env": {}
    }
  }
}
```

##### 指定自定义 Maven 路径（Python 模块方式）：

```json
{
  "mcpServers": {
    "easy-code-reader": {
      "command": "python",
      "args": [
        "-m", 
        "easy_code_reader",
        "--maven-repo",
        "/custom/path/to/maven/repository"
      ],
      "env": {}
    }
  }
}
```

## 工具说明

### read_jar_source

从 Maven 依赖中读取 Java 类的源代码。

**参数：**

- `group_id` (必需): Maven group ID，例如 `org.springframework`
- `artifact_id` (必需): Maven artifact ID，例如 `spring-core`
- `version` (必需): Maven version，例如 `5.3.21`
- `class_name` (必需): 完全限定的类名，例如 `org.springframework.core.SpringVersion`
- `prefer_sources` (可选，默认 `true`): 优先使用 sources jar 而不是反编译
- `summarize_large_content` (可选，默认 `true`): 自动摘要大型内容
- `max_lines` (可选，默认 `500`): 返回的最大行数，设为 `0` 返回全部内容

**示例：**

```json
{
  "group_id": "org.springframework",
  "artifact_id": "spring-core",
  "version": "5.3.21",
  "class_name": "org.springframework.core.SpringVersion"
}
```

**返回格式：**

```json
{
  "source": "sources-jar",
  "class_name": "org.springframework.core.SpringVersion",
  "artifact": "org.springframework:spring-core:5.3.21",
  "code": "package org.springframework.core;\n\npublic class SpringVersion {\n    // ...\n}"
}
```

## 反编译器

Easy Code Reader 使用 **Fernflower** 反编译器（IntelliJ IDEA 使用的反编译器）。

反编译后的文件会被缓存在 JAR 包所在目录的 `easy-code-reader/` 子目录中，例如：

如果 JAR 包位置为：
```
/Users/username/maven/repository/com/example/mylib/1.0.0/mylib-1.0.0.jar
```

反编译后的源文件将存储在：
```
/Users/username/maven/repository/com/example/mylib/1.0.0/easy-jar-reader/mylib-1.0.0/
```

这样可以避免重复反编译相同的 JAR 包，提高性能。

Fernflower JAR 文件已包含在 `decompilers/` 目录中：
- `decompilers/fernflower.jar`

## 环境变量配置

除了命令行参数，还可以通过环境变量配置：

- `MAVEN_REPO`: 自定义 Maven 仓库路径
- `M2_HOME`: Maven 主目录（将使用 `$M2_HOME/repository`）
- `MCP_MAX_RESPONSE_SIZE`: 最大响应大小（字节），默认 50000
- `MCP_MAX_TEXT_LENGTH`: 最大文本长度，默认 10000
- `MCP_MAX_LINES`: 最大行数，默认 500

## 开发

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_jar_reader.py -v
```

### 项目结构

```
easy-code-reader/
├── src/easy_code_reader/
│   ├── __init__.py
│   ├── __main__.py          # 程序入口点
│   ├── server.py            # MCP 服务器实现
│   ├── config.py            # 配置管理
│   ├── decompiler.py        # 反编译器集成
│   └── response_manager.py  # 响应管理器
├── decompilers/             # 反编译器 JAR 文件
│   └── fernflower.jar       # Fernflower 反编译器
├── tests/                   # 测试文件
├── pyproject.toml           # Python 项目配置
├── requirements.txt         # Python 依赖
└── README.md                # 本文档
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 致谢

本项目参考了 [maven-decoder-mcp](https://github.com/salitaba/maven-decoder-mcp) 的部分实现。
