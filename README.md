# Easy JAR Reader

一个用于从 Maven 依赖中读取 Java 源代码的 MCP (Model Context Protocol) 服务器。

## 功能特性

- 📦 **从 Maven 仓库读取源代码**：自动从本地 Maven 仓库（`~/.m2/repository`）中查找和读取 JAR 包源代码
- 🔍 **智能源码提取**：优先从 sources jar 提取源码，如果不存在则自动反编译 class 文件
- 🛠️ **Fernflower 反编译器支持**：使用 IntelliJ IDEA 的 Fernflower 反编译器
- ⚡ **智能缓存机制**：反编译结果缓存在 JAR 包同目录的 `easy-jar-reader/` 下，避免重复反编译
- ⚙️ **自定义 Maven 路径**：支持配置自定义的 Maven 仓库路径
- 📄 **智能内容管理**：自动摘要大型源文件，支持行数限制

## 安装

### 前置要求

- Python 3.10 或更高版本
- Java Development Kit (JDK) - 用于运行反编译器
- Node.js 18.0.0 或更高版本（仅在使用 npm 安装时需要）

### 方法 1: 从 npm 安装（推荐）

```bash
# 全局安装
npm install -g @fangyuan33/easy-jar-reader

# 或者本地安装
npm install @fangyuan33/easy-jar-reader
```

安装后，还需要安装 Python 依赖：

```bash
# 进入包安装目录
cd $(npm root -g)/@fangyuan33/easy-jar-reader  # 全局安装
# 或
cd node_modules/@fangyuan33/easy-jar-reader    # 本地安装

# 安装 Python 依赖
pip install -e .
```

### 方法 2: 从源码安装

```bash
# 克隆仓库
git clone https://github.com/FangYuan33/easy-jar-reader.git
cd easy-jar-reader

# 安装 Python 依赖
pip install -e .

# 开发模式安装（包含测试工具）
pip install -e .[dev]
```

## 使用方法

### 启动方式 1: 使用 Python 命令直接启动

Easy JAR Reader 实现了 Model Context Protocol，可以与支持 MCP 的客户端（如 Claude Desktop）集成。

#### 基本用法

```bash
# 使用默认 Maven 仓库路径 (~/.m2/repository)
python -m easy_jar_reader
```

#### 自定义 Maven 仓库路径

```bash
# 指定自定义 Maven 仓库路径
python -m easy_jar_reader --maven-repo /path/to/your/maven/repository
```

#### 查看帮助信息

```bash
python -m easy_jar_reader --help
```

### 启动方式 2: 使用 npm 命令启动

如果你通过 npm 安装了此包，可以使用 `easy-jar-reader` 命令启动：

#### 基本用法

```bash
# 全局安装后
easy-jar-reader

# 本地安装后
npx easy-jar-reader
```

#### 自定义 Maven 仓库路径

```bash
# 全局安装后
easy-jar-reader --maven-repo /path/to/your/maven/repository

# 本地安装后
npx easy-jar-reader --maven-repo /path/to/your/maven/repository
```

#### 查看帮助信息

```bash
# 全局安装后
easy-jar-reader --help

# 本地安装后
npx easy-jar-reader --help
```

### 在 MCP 客户端中配置

#### Claude Desktop 配置示例

编辑 Claude Desktop 的配置文件：
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

##### 使用 Python 命令启动：

```json
{
  "mcpServers": {
    "easy-jar-reader": {
      "command": "python",
      "args": ["-m", "easy_jar_reader"],
      "env": {}
    }
  }
}
```

##### 使用 npm 全局安装后启动：

```json
{
  "mcpServers": {
    "easy-jar-reader": {
      "command": "easy-jar-reader",
      "args": [],
      "env": {}
    }
  }
}
```

##### 使用 npx 启动（本地安装）：

```json
{
  "mcpServers": {
    "easy-jar-reader": {
      "command": "npx",
      "args": ["-y", "@fangyuan33/easy-jar-reader"],
      "env": {}
    }
  }
}
```

##### 使用自定义 Maven 路径：

```json
{
  "mcpServers": {
    "easy-jar-reader": {
      "command": "python",
      "args": [
        "-m", 
        "easy_jar_reader",
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

Easy JAR Reader 使用 **Fernflower** 反编译器（IntelliJ IDEA 使用的反编译器）。

反编译后的文件会被缓存在 JAR 包所在目录的 `easy-jar-reader/` 子目录中，例如：

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
easy-jar-reader/
├── bin/                     # npm 命令行工具
│   └── easy-jar-reader.js   # npm 启动脚本
├── src/easy_jar_reader/
│   ├── __init__.py
│   ├── __main__.py          # Python 入口点
│   ├── server.py            # MCP 服务器实现
│   ├── config.py            # 配置管理
│   ├── decompiler.py        # 反编译器集成
│   └── response_manager.py  # 响应管理器
├── decompilers/             # 反编译器 JAR 文件
│   └── fernflower.jar       # Fernflower 反编译器
├── tests/                   # 测试文件
├── package.json             # npm 包配置
├── pyproject.toml           # Python 项目配置
└── README.md                # 本文档
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 致谢

本项目参考了 [maven-decoder-mcp](https://github.com/salitaba/maven-decoder-mcp) 的部分实现。
