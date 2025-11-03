# Easy JAR Reader - 实现说明

## 项目概述

Easy JAR Reader 是一个 MCP (Model Context Protocol) 服务器，用于从 Maven 依赖中读取 Java 源代码。本项目基于 [maven-decoder-mcp](https://github.com/salitaba/maven-decoder-mcp) 的参考实现，但仅保留了核心的源代码读取功能，去除了其他不必要的功能。

## 核心功能实现

### 1. 源代码提取（`server.py`）

- **read_jar_source 工具**：主要的 MCP 工具
  - 优先从 sources jar 提取源码
  - 如果 sources jar 不存在，则使用反编译器
  - 支持大型内容自动摘要
  - 支持行数限制

### 2. Maven 仓库配置（`config.py`）

- **默认路径**：`~/.m2/repository`
- **环境变量支持**：
  - `MAVEN_REPO`：直接指定 Maven 仓库路径
  - `M2_HOME`：指定 Maven 主目录（会使用 `$M2_HOME/repository`）
- **命令行参数**：`--maven-repo` 可以指定自定义路径

### 3. 反编译器集成（`decompiler.py`）

支持四种反编译器（按优先级）：

1. **CFR** - 现代化的 Java 反编译器
   - 文件：`decompilers/cfr.jar`
   - 特点：支持最新 Java 特性，输出质量高
   
2. **Procyon** - 高质量开源反编译器
   - 文件：`decompilers/procyon-decompiler.jar`
   - 特点：开源，可靠性好
   
3. **Fernflower** - IntelliJ IDEA 使用的反编译器
   - 文件：`decompilers/fernflower.jar`
   - 特点：IDE 级别的反编译质量
   
4. **javap** - JDK 内置工具
   - 特点：无需额外文件，但输出的是字节码而非源代码

### 4. 响应管理（`response_manager.py`）

- **智能摘要**：对于超长的 Java 源文件，自动保留关键部分
  - 前 20 行（包声明、导入、类声明）
  - 方法签名（最多 10 个）
  - 最后 10 行（结束大括号）
- **配置项**：
  - `MAX_TEXT_LENGTH`：默认 10000 字符
  - `MAX_LINES`：默认 500 行

## 与参考实现的差异

### 保留的功能
- ✅ 源代码提取（`extract_source_code`）
- ✅ Maven 仓库路径配置
- ✅ 反编译器集成
- ✅ 响应管理和内容摘要

### 移除的功能
- ❌ `list_artifacts` - 列出所有 Maven 构件
- ❌ `analyze_jar` - 分析 JAR 文件结构
- ❌ `extract_class_info` - 提取类信息
- ❌ `get_dependencies` - 获取依赖关系
- ❌ `search_classes` - 搜索类
- ❌ `compare_versions` - 版本比较
- ❌ `find_usage_examples` - 查找使用示例
- ❌ `get_dependency_tree` - 依赖树
- ❌ `find_dependents` - 查找依赖者
- ❌ `get_version_info` - 版本信息
- ❌ `analyze_jar_structure` - JAR 结构分析
- ❌ `extract_method_info` - 方法信息提取
- ❌ Maven 依赖分析器（`maven_analyzer.py`）

## 技术实现细节

### MCP 协议实现

使用 `mcp` Python 库实现 Model Context Protocol：

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
```

### Maven 路径解析

Maven 仓库使用标准的目录结构：
```
~/.m2/repository/
  ├── org/springframework/spring-core/5.3.21/
  │   ├── spring-core-5.3.21.jar
  │   ├── spring-core-5.3.21-sources.jar
  │   └── spring-core-5.3.21.pom
```

路径转换逻辑：
- Group ID: `org.springframework` → `org/springframework`
- Artifact ID: `spring-core`
- Version: `5.3.21`
- 完整路径: `org/springframework/spring-core/5.3.21/spring-core-5.3.21.jar`

### 反编译流程

1. 从 JAR 中提取 `.class` 文件到临时目录
2. 调用反编译器处理 class 文件
3. 读取反编译后的 `.java` 文件
4. 返回源代码内容

### 错误处理

- JAR 文件不存在：返回友好的错误消息
- 类文件不存在：返回基本的字节码信息
- 反编译失败：回退到下一个可用的反编译器
- 所有反编译器都失败：返回基本的类信息（版本号、大小等）

## 测试覆盖

### 单元测试（`test_jar_reader.py`）
- JAR 文件创建和读取
- Manifest 解析
- 类文件魔数验证

### 集成测试（`test_integration.py`）
- 服务器初始化
- 从 sources jar 提取源码
- JAR 文件路径解析
- 行数限制功能
- 配置管理

### 演示脚本
- `examples/demo.py` - 从 sources jar 提取演示
- `examples/demo_decompile.py` - 反编译功能演示

## 性能优化

1. **按需反编译**：只在需要时才调用反编译器
2. **智能摘要**：避免返回超大响应
3. **缓存考虑**：虽然当前未实现缓存，但架构支持未来添加
4. **优先级选择**：优先使用最快最可靠的反编译器

## 未来改进方向

1. **缓存机制**：缓存反编译结果
2. **并发支持**：支持并发反编译多个类
3. **增量更新**：支持 Maven 仓库的增量扫描
4. **更多工具**：可以考虑添加简化版的其他工具（如果需要）

## 依赖项

- `mcp>=0.9.0` - MCP 协议实现
- `pytest>=7.0.0` - 测试框架（开发依赖）
- `pytest-asyncio>=0.21.0` - 异步测试支持（开发依赖）

## 兼容性

- Python 3.10+
- 需要 Java Runtime Environment (JRE) 来运行反编译器
- 支持所有主流操作系统（Windows、macOS、Linux）
