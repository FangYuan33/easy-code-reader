# Easy Code Reader

<div align="center">
  <img src="icon.png" alt="Easy Code Reader Icon" width="200"/>
</div>

<div align="center">

一个强大的 MCP (Model Context Protocol) 服务器，用于智能读取 Java 源代码。支持从 Maven 依赖和本地项目中提取源码，配备双反编译器（CFR/Fernflower）自动选择机制，智能处理 SNAPSHOT 版本，完美支持多模块项目，让 AI 助手能够深入理解你的 Java 代码库。

A powerful MCP (Model Context Protocol) server for intelligently reading Java source code. Supports extracting source code from Maven dependencies and local projects, equipped with dual decompiler (CFR/Fernflower) auto-selection mechanism, intelligent SNAPSHOT version handling, and perfect multi-module project support. Empowers AI assistants to deeply understand your Java codebase.

</div>

---

---

## 功能特性

- 📁 **本地项目代码读取**：支持从本地项目目录读取源代码，支持多模块 Maven/Gradle 项目
- 📋 **项目列举功能**：列出项目目录下所有项目，便于快速查找和定位
- 🗂️ **智能文件过滤**：自动过滤测试目录、编译产物和 IDE 配置，只显示源代码和配置文件
- 🎯 **模块聚焦模式**：支持只列出项目中特定子目录的文件，精准定位目标代码
- 📦 **从 Maven 仓库读取源代码**：自动从本地 Maven 仓库（默认获取 **MAVEN_HOME** 目录或 `~/.m2/repository`，支持配置）中查找和读取 JAR 包源代码
- 🔍 **智能源码提取**：优先从 sources jar 提取源码，如果不存在则自动反编译 class 文件
- 🛠️ **双反编译器支持**：支持 CFR 和 Fernflower 反编译器，根据 Java 版本自动选择最佳反编译器
- ⚡ **智能缓存机制**：反编译结果缓存在 JAR 包同目录的 `easy-code-reader/` 下，避免重复反编译
- 🔄 **SNAPSHOT 版本支持**：智能处理 SNAPSHOT 版本，自动查找带时间戳的最新版本并管理缓存

## 环境要求

- [uv](https://github.com/astral-sh/uv) - Python 包和项目管理工具
- Python 3.10 或更高版本
- Java Development Kit (JDK) - 用于运行反编译器，要求至少 Java 8

## 快速接入：使用 uvx（推荐 - 开箱即用）

如果您还没有安装 uv，可以通过以下方式快速安装：

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或使用 pip
pip install uv
```

或者参考 [uv 官网](https://github.com/astral-sh/uv) 进行安装，并配置 uv 的安装路径添加到系统 PATH 中，以便可以直接使用 `uvx` 命令。[uv](https://github.com/astral-sh/uv) 是一个极快的 Python 包和项目管理工具。使用 `uvx` 可以无需预先安装，直接运行，参考以下 MCP 客户端配置：

- `--maven-repo`: 指定 Maven 仓库路径，将 `/custom/path/to/maven/repository` 内容替换为本地 Maven 仓库路径即可，不配置默认使用 **MAVEN_HOME** 目录或 `~/.m2/repository`
- `--project-dir`: 指定本地项目目录路径，将 `/path/to/projects` 替换为实际保存所有项目的路径

```json
{
  "mcpServers": {
    "easy-code-reader": {
      "command": "uvx",
      "args": [
        "easy-code-reader",
        "--maven-repo",
        "/custom/path/to/maven/repository",
        "--project-dir",
        "/path/to/projects"
      ],
      "env": {}
    }
  }
}
```

将以上内容配置好后，AI 助手即可通过 MCP 协议调用 Easy Code Reader 提供的工具，完成多项目、多依赖的 Java 源代码读取工作。

## 最佳实践

### 与 AI 助手配合使用

Easy Code Reader 特别适合与 Claude、ChatGPT 等 AI 助手配合使用：

1. **阅读第三方库源码**：通过 `read_jar_source` 快速查看 Spring、MyBatis 等框架的实现细节
2. **分析项目结构**：使用 `list_project_files` 了解大型项目的组织结构
3. **代码学习**：结合 AI 助手的解释，深入理解复杂的代码逻辑
4. **问题排查**：读取依赖源码，分析第三方库的行为

### 最佳实践

- **使用 sub_path 参数**：对于大型项目（如 Nacos、Spring Cloud），建议先用 `sub_path` 聚焦到具体模块，避免返回过多文件
- **先列举再读取**：不确定文件位置时，先用 `list_project_files` 查看文件列表，再用 `read_project_code` 读取
- **验证项目名**：使用 `list_all_project` 验证项目名称是否正确，避免拼写错误

---

## 工具说明

Easy Code Reader 提供了 4 个主要工具，分为两大使用场景：

### 场景 1: 读取 Maven JAR 包源代码

#### read_jar_source

从 Maven 依赖中读取 Java 类的源代码（优先从 sources jar，否则反编译）。

**参数：**

- `group_id` (必需): Maven group ID，例如 `org.springframework`
- `artifact_id` (必需): Maven artifact ID，例如 `spring-core`
- `version` (必需): Maven version，例如 `5.3.21`
- `class_name` (必需): 完全限定的类名，例如 `org.springframework.core.SpringVersion`
- `prefer_sources` (可选，默认 `true`): 优先使用 sources jar 而不是反编译

**工作原理：**

1. 首先尝试从 `-sources.jar` 中提取源代码（如果 `prefer_sources=true`）
2. 如果 sources jar 不存在或提取失败，自动回退到反编译主 JAR 文件
3. 支持 SNAPSHOT 版本的智能处理

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
  "class_name": "org.springframework.core.SpringVersion",
  "artifact": "org.springframework:spring-core:5.3.21",
  "code": "package org.springframework.core;\n\npublic class SpringVersion {\n    // ...\n}"
}
```

---

### 场景 2: 读取本地项目源代码

#### list_all_project

列举项目目录下所有的项目文件夹名称。

**用途：**
- 查看所有可用的项目
- 当输入不完整的项目名时，帮助推理出最接近的项目名
- 验证项目是否存在

**参数：**

- `project_dir` (可选): 项目目录路径，如未提供则使用启动时配置的路径

**示例：**

```json
{}
```

**返回格式：**

```json
{
  "project_dir": "/path/to/projects",
  "project_count": 5,
  "projects": [
    "nacos",
    "spring-boot",
    "my-app",
    "demo-project",
    "test-service"
  ]
}
```

#### list_project_files

列出 Java 项目中的源代码文件和配置文件路径。

**用途：**
- 了解项目结构和文件组织
- 查找特定的类或配置文件
- 分析类之间的关系和依赖
- 当项目文件过多时，聚焦特定模块

**支持两种模式：**

1. **全项目模式**（不指定 `sub_path`）：列出整个项目的所有文件
2. **聚焦模式**（指定 `sub_path`）：只列出指定子目录下的文件

**参数：**

- `project_name` (必需): 项目名称，例如 `nacos`
- `sub_path` (可选): 指定项目内的子目录路径，例如 `core` 或 `address/src/main/java`
- `project_dir` (可选): 项目所在的父目录路径，如未提供则使用启动时配置的路径

**自动过滤内容：**
- ✅ 包含：Java 源代码 (.java)、配置文件 (.xml, .properties, .yaml, .json 等)、构建脚本、文档
- ❌ 排除：测试目录 (`src/test`)、编译产物 (`target`, `build`)、IDE 配置、版本控制文件

**示例 1 - 列出整个项目：**

```json
{
  "project_name": "nacos"
}
```

**示例 2 - 只列出 core 模块：**

```json
{
  "project_name": "nacos",
  "sub_path": "core"
}
```

**返回格式：**

```json
{
  "project_name": "nacos",
  "project_dir": "/path/to/projects/nacos",
  "search_scope": "core",
  "total_files": 45,
  "files": [
    "core/pom.xml",
    "core/src/main/java/com/alibaba/nacos/core/service/NacosService.java",
    "core/src/main/resources/application.properties",
    "..."
  ]
}
```

#### read_project_code

从本地项目目录中读取指定文件的源代码。

**用途：**
- 读取具体类或文件的完整源代码
- 支持多模块 Maven/Gradle 项目
- 自动搜索常见的源代码路径

**参数：**

- `project_name` (必需): 项目名称，例如 `my-project`
- `class_name` (必需): 完全限定的类名或相对路径
  - 类名格式：`com.example.MyClass`
  - 相对路径格式：`src/main/java/com/example/MyClass.java`
  - 模块相对路径：`core/src/main/java/com/example/MyClass.java`
- `project_dir` (可选): 项目目录路径，如未提供则使用启动时配置的路径

**支持的文件类型：**
- Java (.java)

**自动搜索路径：**
- `src/main/java/{class_path}.java`
- `src/{class_path}.java`
- `{class_path}.java`
- 多模块项目中的子模块路径

**示例 1 - 使用类名：**

```json
{
  "project_name": "my-spring-app",
  "class_name": "com.example.service.UserService"
}
```

**示例 2 - 使用相对路径：**

```json
{
  "project_name": "nacos",
  "class_name": "address/src/main/java/com/alibaba/nacos/address/component/AddressServerGeneratorManager.java"
}
```

**返回格式：**

```json
{
  "project_name": "my-spring-app",
  "class_name": "com.example.service.UserService",
  "file_path": "/path/to/projects/my-spring-app/src/main/java/com/example/service/UserService.java",
  "code": "package com.example.service;\n\nimport ...\n\npublic class UserService {\n    // ...\n}"
}
```

---

## 常见问题

### Q1: spawn uvx ENOENT spawn uvx ENOENT

uv 命令未找到，确保已正确安装 uv 并将其路径添加到系统 PATH 中，参考 [快速接入使用-uvx推荐---开箱即用](#快速接入使用-uvx推荐---开箱即用)。

---

## 技术细节

### 项目结构

```
easy-code-reader/
├── src/easy_code_reader/
│   ├── __init__.py
│   ├── __main__.py          # 程序入口点
│   ├── server.py            # MCP 服务器实现
│   ├── config.py            # 配置管理
│   ├── decompiler.py        # 反编译器集成
│   └── decompilers/         # 反编译器 JAR 文件目录
│       ├── fernflower.jar   # Fernflower 反编译器
│       └── cfr.jar          # CFR 反编译器
├── tests/                   # 测试文件
├── pyproject.toml           # Python 项目配置
├── requirements.txt         # Python 依赖
└── README.md                # 本文档
```

### 反编译器

Easy Code Reader 支持多个反编译器，并根据 Java 版本自动选择最合适的：

| Java 版本 | 推荐反编译器     | 说明                                                                                                       |
|---------|------------|----------------------------------------------------------------------------------------------------------|
| 8 - 20  | CFR        | 自动使用 **CFR** 反编译器（兼容 Java 8+），已包含在包中：`src/easy_code_reader/decompilers/cfr.jar`                          |
| 21+     | Fernflower | 自动使用 **Fernflower** 反编译器（IntelliJ IDEA 使用的反编译器），已包含在包中：`src/easy_code_reader/decompilers/fernflower.jar` |

#### 反编译缓存机制

反编译后的文件会被缓存在 JAR 包所在目录的 `easy-code-reader/` 子目录中，例如：

如果 JAR 包位置为：

```
~/.m2/repository/org/springframework/spring-core/5.3.21/spring-core-5.3.21.jar
```

反编译后的源文件将存储在：

```
~/.m2/repository/org/springframework/spring-core/5.3.21/easy-code-reader/spring-core-5.3.21.jar
```

缓存文件本身也是一个 JAR 格式的压缩包，包含所有反编译后的 `.java` 文件。

**SNAPSHOT 版本特殊处理：**

- 对于 SNAPSHOT 版本（如 `1.0.0-SNAPSHOT`），Maven 会生成带时间戳的 JAR（如 `artifact-1.0.0-20251030.085053-1.jar`）
- 系统会自动查找最新的带时间戳版本进行反编译
- 缓存以规范化名称存储（`artifact-1.0.0-SNAPSHOT.jar`）
- 当检测到新版本时，会自动清理旧的 SNAPSHOT 缓存

这样可以避免重复反编译相同的 JAR 包，提高性能。

## 许可证

Apache License 2.0，详见 [LICENSE](LICENSE) 文件。

## 巨人的肩膀

- [Github: maven-decoder-mcp](https://github.com/salitaba/maven-decoder-mcp) 灵感来源
- [Github: fernflower](https://github.com/JetBrains/fernflower)
