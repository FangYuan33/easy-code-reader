# Easy Code Reader

<div align="center">
  <img src="https://raw.githubusercontent.com/FangYuan33/easy-code-reader/master/icon.png" alt="Easy Code Reader Icon" width="200"/>
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

## 最佳实践

Easy Code Reader 特别适合与 Claude、ChatGPT 等大模型配合使用，接下来以 VSCode 结合 Copilot 为例，介绍一些最佳实践：

### 1. 跨项目调用，根据调用链路分析源码

在比较复杂的项目中一般会拆分多个微服务，某些功能的实现可能会跨多个项目调用，如果靠人梳理相关逻辑会比较耗时，所以可以将涉及的代码 clone 到本地后使用 Easy Code Reader MCP 并结合 Code Agent 进行分析。接下来我们以 Nacos 项目为例，假设我们想了解 Nacos 的服务注册功能是如何实现的，可以按照以下步骤操作。

首先，比如我们创建了一个 Nacos Client 客户端，在这段逻辑中执行服务注册：

```java
public class Main {
    private static final Logger logger = LoggerFactory.getLogger(Main.class);

    public static void main(String[] args) throws NacosException, InterruptedException {
        logger.info("开始初始化 Nacos 客户端...");

        Properties properties = new Properties();
        properties.put(PropertyKeyConst.SERVER_ADDR, "127.0.0.1:8848");
        properties.put(PropertyKeyConst.NAMESPACE, "7430d8fe-99ce-4b20-866e-ed021a0652c9");

        NamingService namingService = NacosFactory.createNamingService(properties);

        System.out.println("=== 注册服务实例 ===");
        try {
            // 注册一个服务实例
            namingService.registerInstance("test-service0", "127.0.0.1", 8080);
            // 添加事件监听器
            namingService.subscribe("test-service", event -> {
                System.out.println("服务实例变化: " + event);
            });
        } catch (Exception e) {
            System.out.println("服务注册失败(预期，因为服务器可能未启动): " + e.getMessage());
        }

        TimeUnit.HOURS.sleep(3);
    }
}
```

因为我们创建 Nacos Client 执行服务注册时是由 Nacos 提供的 SDK 直接调用 `NamingService#registerInstance` 方法实现的，我们并不清楚底层是如何实现的，如果我们想要了解实现细节，那么就需要将 Nacos 的源码 Clone 下来，并使用 Easy Code Reader 读取相关源码，下面是一个示例 Prompt：

```text
你是一位 Java 专家，请你帮我分析 #file:Main.java 中 namingService.registerInstance 方法的逻辑，这段逻辑的实现在本地项目的 nacos 中，所以你需要在 nacos 读取一系列相关的源码才能了解它的核心逻辑，读取 nacos 项目的代码你可以借助 easy-code-reader MCP，其中包含你可以获取项目信息、项目中所有的文件信息和某个文件的工具
```

![img.png](imges/img.png)

如图所示，它会不断地根据源码调用链路，读取相关源码并进行分析，最终我们就能了解服务注册的实现细节，会使用到 MCP Easy Code Reader 提供的多个工具 `list_all_project`、`list_project_files` 和 `read_project_code`， 具体调用细节图示如下：

![img.png](imges/img1.png)

最终得到分析结果，节省很多时间：

![img.png](imges/img2.png)

### 2. 阅读 jar 包源码，根据源码完成代码编写

在使用第三方或其他外部依赖时，Copilot 或其他 Code Agent 并不能直接读取 jar 包中的源码，往往需要我们将源码内容手动复制到提示词中才能完成，费时费力。在 Easy Code Reader 中提供了 `read_jar_source` 工具来读取 jar 包中的源码，帮我们完成开发实现。我们还是以如下代码为例，现在我想实现多个服务实例的注册，但是我又不了解 `NamingService` 的实现，便可以借助 `read_jar_source` 来完成：

```java
public class Main {
    private static final Logger logger = LoggerFactory.getLogger(Main.class);

    public static void main(String[] args) throws NacosException, InterruptedException {
        logger.info("开始初始化 Nacos 客户端...");

        Properties properties = new Properties();
        properties.put(PropertyKeyConst.SERVER_ADDR, "127.0.0.1:8848");
        properties.put(PropertyKeyConst.NAMESPACE, "7430d8fe-99ce-4b20-866e-ed021a0652c9");

        NamingService namingService = NacosFactory.createNamingService(properties);

        System.out.println("=== 注册服务实例 ===");
        try {
            // 注册一个服务实例
            namingService.registerInstance("test-service0", "127.0.0.1", 8080);
            // 添加事件监听器
            namingService.subscribe("test-service", event -> {
                System.out.println("服务实例变化: " + event);
            });
            // 注册多个服务实例

        } catch (Exception e) {
            System.out.println("服务注册失败(预期，因为服务器可能未启动): " + e.getMessage());
        }

        TimeUnit.HOURS.sleep(3);
    }
}
```

```text
你是一位 Java 技术专家，精通 Nacos 框架，请你帮我在 #file:Main.java 中完成注册多个服务实例的逻辑，在编写代码前，你需要先试用 easy-code-reader 的 read_jar_source 工具读取 com.alibaba.nacos.api.naming.NamingService 的源码信息来了解注册多个服务实例的方法
```

处理过程如下所示：

![img.png](imges/img3.png)

这样我们便能够快速地了解 `NamingService` 的实现细节，从而完成代码编写工作，节省了大量时间。

### 3. 跨项目阅读源码，根据源码完成本项目实现

在大型项目中，某些功能的实现可能会跨多个模块或微服务，如果部分逻辑已经实现并且后续其他应用的逻辑需要依赖这部分逻辑时，可以借助 Easy Code Reader 读取相关模块的源码，帮助我们更好地理解和实现当前项目的功能，示例 Prompt 如下：

```text
你是一位 Java 技术专家，现在我要实现 XXX 的业务逻辑，这部分逻辑的实现需要调用本地项目 A 中 XXX 的接口及其实现，请你借助 MCP easy-code-reader 来帮我读取 A 项目中的源码，并帮我实现 XXX 的业务逻辑
```

当然除了这三种应用场景以外，还可以使用 Easy Code Reader 完成以下事项：

- 异常问题快速溯源：如果有异常信息是外部 jar 包依赖中抛出来的，可以使用 read_jar_source 工具根据异常堆栈日志快速定位异常点
- 依赖升级影响评估（旧/新版本差异核对）：同样是使用 read_jar_source 工具来完成新旧版本的实现差异，评估升级影响
- 业务代码逻辑评审：如果业务逻辑开发实现在多个项目中，可以借助读取本地项目代码的工具 `list_all_project`、`list_project_files` 和 `read_project_code`，来分析新增的逻辑是否满足业务要求
- 新人快速上手多个微服务：借助读取本地项目代码的工具，可以根据接口调用链路快速理清微服务项目代码之间的关系，提高上手速度

---

## 环境要求

- [uv](https://github.com/astral-sh/uv) - Python 包和项目管理工具
- Python 3.10 或更高版本
- Java Development Kit (JDK) - 用于运行反编译器，要求至少 Java 8

## 快速接入（方法一）：使用 uvx（推荐 - 开箱即用）

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

## 快速接入（方法二）：使用 uv 安装到本地（不推荐）

如果使用 **快速接入（方法一）** 安装运行失败，那么可以采用直接安装到本地的方法，运行如下命令：

```bash
uv tool install easy-code-reader
```

安装成功后，执行以下命令获取安装目录：

```bash
which easy-code-reader
```

比如，输出结果是：/Users/fangyuan/.local/bin/easy-code-reader，那么需要按照如下方式配置 MCP 客户端：

```json
{
  "mcpServers": {
    "easy-code-reader": {
      "command": "/Users/fangyuan/.local/bin/easy-code-reader",
      "args": [
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

一般这样操作都能完成安装，后续如果有版本更新，可以通过以下命令进行升级：

```bash
uv tool install --upgrade easy-code-reader
```

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

- [Github: maven-decoder-mcp](https://github.com/salitaba/maven-decoder-mcp)
- [Github: fernflower](https://github.com/JetBrains/fernflower)
