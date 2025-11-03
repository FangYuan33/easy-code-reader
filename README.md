# Easy JAR Reader

[English](#english) | [中文](#中文)

## English

### Overview

Easy JAR Reader is a Model Context Protocol (MCP) server that provides tools for reading and analyzing JAR (Java Archive) files. It allows you to explore JAR contents, read files, extract class information, and more.

### Features

- 📦 **List JAR Contents**: Browse all files and directories within a JAR archive
- 📄 **Read Files**: Extract and read specific files from JAR archives
- 📋 **Manifest Reader**: Access JAR manifest information
- ☕ **Class File Analysis**: Get detailed information about compiled Java class files
- 🔍 **Smart Categorization**: Automatically organizes files by type (classes, resources, etc.)

### Installation

```bash
# Clone the repository
git clone https://github.com/FangYuan33/easy-jar-reader.git
cd easy-jar-reader

# Install dependencies
pip install -e .
```

### Usage

#### Running the MCP Server

```bash
python -m easy_jar_reader.server
```

#### Using with Claude Desktop

Add the following to your Claude Desktop configuration file (`~/.config/claude/config.json` on macOS/Linux or `%APPDATA%\Claude\config.json` on Windows):

```json
{
  "mcpServers": {
    "easy-jar-reader": {
      "command": "python",
      "args": ["-m", "easy_jar_reader.server"]
    }
  }
}
```

### Available Tools

1. **list_jar_contents** - List all files in a JAR archive
   - Input: `jar_path` (string)
   
2. **read_jar_file** - Read a specific file from a JAR
   - Input: `jar_path` (string), `file_path` (string), `encoding` (optional, default: utf-8)
   
3. **get_jar_manifest** - Get the MANIFEST.MF content
   - Input: `jar_path` (string)
   
4. **extract_class_info** - Get information about a class file
   - Input: `jar_path` (string), `class_path` (string)

### Examples

See the `examples/` directory for usage examples:

```bash
# Run the basic usage example
python examples/basic_usage.py

# Create a sample JAR file for testing
python examples/create_sample_jar.py
```

### Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

### License

See LICENSE file for details.

---

## 中文

### 概述

Easy JAR Reader 是一个模型上下文协议（MCP）服务器，提供用于读取和分析 JAR（Java 归档）文件的工具。它允许您浏览 JAR 内容、读取文件、提取类信息等。

### 功能特性

- 📦 **列出 JAR 内容**：浏览 JAR 归档中的所有文件和目录
- 📄 **读取文件**：从 JAR 归档中提取和读取特定文件
- 📋 **清单读取器**：访问 JAR 清单信息
- ☕ **类文件分析**：获取已编译 Java 类文件的详细信息
- 🔍 **智能分类**：按类型自动组织文件（类、资源等）

### 安装

```bash
# 克隆仓库
git clone https://github.com/FangYuan33/easy-jar-reader.git
cd easy-jar-reader

# 安装依赖
pip install -e .
```

### 使用方法

#### 运行 MCP 服务器

```bash
python -m easy_jar_reader.server
```

#### 与 Claude Desktop 配合使用

将以下内容添加到您的 Claude Desktop 配置文件中（macOS/Linux 上为 `~/.config/claude/config.json`，Windows 上为 `%APPDATA%\Claude\config.json`）：

```json
{
  "mcpServers": {
    "easy-jar-reader": {
      "command": "python",
      "args": ["-m", "easy_jar_reader.server"]
    }
  }
}
```

### 可用工具

1. **list_jar_contents** - 列出 JAR 归档中的所有文件
   - 输入：`jar_path`（字符串）
   
2. **read_jar_file** - 从 JAR 中读取特定文件
   - 输入：`jar_path`（字符串）、`file_path`（字符串）、`encoding`（可选，默认：utf-8）
   
3. **get_jar_manifest** - 获取 MANIFEST.MF 内容
   - 输入：`jar_path`（字符串）
   
4. **extract_class_info** - 获取类文件信息
   - 输入：`jar_path`（字符串）、`class_path`（字符串）

### 示例

查看 `examples/` 目录获取使用示例：

```bash
# 运行基本用法示例
python examples/basic_usage.py

# 创建用于测试的示例 JAR 文件
python examples/create_sample_jar.py
```

### 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest
```

### 许可证

详见 LICENSE 文件。
