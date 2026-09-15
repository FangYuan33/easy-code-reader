# Easy Code Reader

<div align="center">
  <img src="https://raw.githubusercontent.com/FangYuan33/easy-code-reader/master/icon.png" alt="Easy Code Reader Icon" width="200"/>
</div>

<div align="center">

一个强大的本地 MCP Server，用于智能读取 Java 源代码。支持从 Maven 依赖（JAR 包）中提取源码，配备双反编译器（CFR/Fernflower）自动选择机制，智能处理 SNAPSHOT 版本，让 AI 助手能够深入理解你的 Java 代码库。

A powerful MCP (Model Context Protocol) server for intelligently reading Java source code. Supports extracting source code from Maven dependencies, equipped with dual decompiler (CFR/Fernflower) auto-selection mechanism and intelligent SNAPSHOT version handling. Empowers AI assistants to deeply understand your Java codebase.

</div>

---

---

## 功能特性

- 🤖 **AI 友好的智能提示**：所有工具都具备智能错误提示机制，当查询失败时主动引导 AI 助手调整策略，有效减少幻觉和重复尝试
- 📦 **从 Maven 仓库读取源代码**：自动从本地 Maven 仓库（默认获取 **MAVEN_HOME** 目录或 `~/.m2/repository`，支持配置）中查找和读取 JAR 包源代码
- 🔍 **智能源码提取**：优先从 sources jar 提取源码，如果不存在则自动反编译 class 文件
- 🛠️ **双反编译器支持**：支持 CFR 和 Fernflower 反编译器，根据 Java 版本自动选择最佳反编译器
- ⚡ **智能缓存机制**：反编译结果缓存在 JAR 包同目录的 `easy-code-reader/` 下，避免重复反编译
- 🔄 **SNAPSHOT 版本支持**：智能处理 SNAPSHOT 版本，自动查找带时间戳的最新版本并管理缓存

## 最佳实践

Easy Code Reader 特别适合与 Claude、ChatGPT 等大模型配合使用，接下来以 VSCode 结合 Copilot 为例，介绍一些最佳实践：

### 阅读 jar 包源码，根据源码完成代码编写

在使用第三方或其他外部依赖时，Copilot 或其他 Code Agent 并不能直接读取 jar 包中的源码，往往需要我们将源码内容手动复制到提示词中才能完成，费时费力。在 Easy Code Reader 中提供了 `read_jar_source` 工具来读取 jar 包中的源码，帮我们完成开发实现。以下面代码为例，现在我想实现多个服务实例的注册，但是我又不了解 `NamingService` 的实现，便可以借助 `read_jar_source` 来完成：

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

![img.png](https://raw.githubusercontent.com/FangYuan33/easy-code-reader/master/imges/img3.png)

这样我们便能够快速地了解 `NamingService` 的实现细节，从而完成代码编写工作，节省了大量时间。

还可以使用 Easy Code Reader 完成以下事项：

- 异常问题快速溯源：如果有异常信息是外部 jar 包依赖中抛出来的，可以使用 `read_jar_source` 工具根据异常堆栈日志快速定位异常点
- 依赖升级影响评估（旧/新版本差异核对）：同样是使用 `read_jar_source` 工具来完成新旧版本的实现差异，评估升级影响

---

<a id="quick-start-env"></a>
## 环境要求

- [uv](https://github.com/astral-sh/uv) - Python 包和项目管理工具
- Python 3.10 或更高版本
- Java Development Kit (JDK) - 用于运行反编译器，要求至少 Java 8

## 快速接入（方法一）：使用 uvx（推荐）

如果您还没有安装 uv，可以通过以下方式快速安装：

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

或者参考 [uv 官网](https://github.com/astral-sh/uv) 进行安装，并配置 uv 的安装路径添加到系统 PATH 中，以便可以直接使用 `uvx` 命令。[uv](https://github.com/astral-sh/uv) 是一个极快的 Python 包和项目管理工具。使用 `uvx` 可以无需预先安装，直接运行，参考以下 MCP 客户端配置：

- `--maven-repo`: 指定 Maven 仓库路径，将 `/custom/path/to/maven/repository` 内容替换为本地 Maven 仓库路径即可，不配置默认使用 **MAVEN_HOME** 目录或 `~/.m2/repository`

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

将以上内容配置好后，AI 助手即可通过 MCP 协议调用 Easy Code Reader 提供的工具，完成 Maven 依赖的 Java 源代码读取工作。

<a id="quick-start-uv"></a>
## 快速接入（方法二）：使用 uv 安装到本地

如果使用 **快速接入（方法一）** 安装运行失败，那么可以采用直接安装到本地的方法，运行如下命令：

```bash
uv tool install easy-code-reader
```

安装成功后，执行以下命令获取安装目录：

```bash
which easy-code-reader
```

比如，输出结果是：/Users/fangyuan/.local/bin/easy-code-reader，那么需要按照如下方式配置 MCP 客户端，**注意 `args` 参数配置**，**注意 `args` 参数配置**，**注意 `args` 参数配置**：

```json
{
  "mcpServers": {
    "easy-code-reader": {
      "command": "/Users/fangyuan/.local/bin/easy-code-reader",
      "args": [
        "--maven-repo",
        "/custom/path/to/maven/repository"
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

## 常见问题

### Q1: spawn uvx ENOENT spawn uvx ENOENT

uv 命令未找到，确保已正确安装 uv 并将其路径添加到系统 PATH 中，参考 [环境要求](#quick-start-env)，并尝试重启 IDE 后再启动 MCP Server。

### Q2: Downloading cpython-3.10.19-macos-aarch64-none (download) (17.7MiB) MCP error -32001: Request timed out

Python 环境下载失败，尝试手动下载或重试下载，或者参考 [快速接入（方法二）](#quick-start-uv)。

---

## 工具说明

Easy Code Reader 提供两个工具，用于查找 Maven 坐标和读取 JAR 包源码。

### search_group_id

根据 artifactId 和可选的 groupId 前缀，在本地 Maven 仓库中查找 groupId 及可用版本，辅助调用 `read_jar_source`。

**参数：**

- `artifact_id`（必需）：不含版本号的 Maven artifact ID，例如 `spring-core`。
- `group_prefix`（可选）：1–2 级 groupId 前缀，例如 `org.springframework`，用于缩小搜索范围。
- `version_hint`（可选）：版本提示，例如 `5.3.21` 或 `SNAPSHOT`；不确定版本时可不传。

**示例：**

```json
{
  "artifact_id": "spring-core",
  "group_prefix": "org.springframework",
  "version_hint": "5.3.21"
}
```

**返回内容：**

- `matches`：按 groupId 排序的候选列表，每项包含 `group_id`、`matched_versions`（最多 10 个版本）和 `total_versions`。
- `total_matches`：匹配的 groupId 数量。
- `search_stats`：扫描的 group 数量及耗时。
- `hint`：后续操作建议。

**典型工作流：**

1. 使用 `search_group_id` 查找 groupId 和可用版本。
2. 从结果中选择正确的 Maven 坐标。
3. 使用 `read_jar_source` 读取指定类的源码。

没有匹配结果时，检查 artifact ID 拼写，放宽 `group_prefix` 或移除 `version_hint` 后重试。

### read_jar_source

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

**智能错误提示：**

当 JAR 文件未找到时，工具会提供详细的排查建议：
- 提示可能的原因（依赖未安装、Maven 坐标错误）
- 建议使用 `search_group_id` 工具查找正确的 groupId 和可用版本
- 指导在 `<dependencies>` 部分核对正确的 Maven 坐标
- 提示确认坐标后重新调用工具
- 说明可能需要执行 Maven 构建命令安装依赖

这个智能提示机制特别适合与 AI 助手配合使用，能有效减少因 Maven 坐标错误导致的重复尝试。

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
  "source_type": "sources.jar",
  "code": "package org.springframework.core;\n\npublic class SpringVersion {\n    // ...\n}"
}
```

**source_type 字段说明：**

`source_type` 字段标识源码的来源，帮助 AI 助手了解代码的可靠性和新鲜度：

- `"sources.jar"`: 从 Maven 的 sources JAR 文件中提取（最可靠，与发布版本完全一致）
- `"decompiled"`: 通过反编译器新反编译生成（可能存在反编译不完整的情况）
- `"decompiled_cache"`: 从之前反编译的缓存中读取（避免重复反编译，提升性能）

💡 **使用建议**：
- `sources.jar` 来源的代码最准确，可直接作为分析依据
- `decompiled` 来源的代码可能会有语法糖恢复、泛型擦除等反编译特征
- `decompiled_cache` 与 `decompiled` 质量相同，只是从缓存读取以提升效率

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

缓存文件本身也是一个 JAR 格式的压缩包，包含所有反编译后的 `.java` 文件，这样可以避免重复反编译相同的 JAR 包，提高性能。但 **针对 SNAPSHOT 版本需要特殊处理：** 因为 Maven 针对快照版本会生成带时间戳的 JAR（如 `artifact-1.0.0-20251030.085053-1.jar`），Easy Code Reader 会自动查找最新的带时间戳版本进行反编译，并且以缓存以 `artifact-1.0.0-20251030.085053-1.jar` 名称存储，提供版本判断的依据，当检测到新版本时，会自动清理旧的 SNAPSHOT 缓存，生成新的缓存文件。

## 许可证

Apache License 2.0，详见 [LICENSE](LICENSE) 文件。

## 巨人的肩膀

- [Github: maven-decoder-mcp](https://github.com/salitaba/maven-decoder-mcp)
- [Github: fernflower](https://github.com/JetBrains/fernflower)
- [Github: Model Context Protocol(MCP) 编程极速入门](https://github.com/liaokongVFX/MCP-Chinese-Getting-Started-Guide)
