# Easy Code Reader 使用示例

## 示例 1: 基本使用

```bash
# 启动 MCP 服务器（使用默认 Maven 仓库）
python -m easy_code_reader

# 使用自定义 Maven 仓库路径
python -m easy_code_reader --maven-repo /path/to/maven/repo
```

## 示例 2: 在 Claude Desktop 中配置

编辑配置文件 `~/Library/Application Support/Claude/config.json`:

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

## 示例 3: 读取 Spring Framework 源代码

使用 `read_jar_source` 工具:

```json
{
  "group_id": "org.springframework",
  "artifact_id": "spring-core",
  "version": "5.3.21",
  "class_name": "org.springframework.core.SpringVersion"
}
```

## 示例 4: 读取 Apache Commons 源代码

```json
{
  "group_id": "org.apache.commons",
  "artifact_id": "commons-lang3",
  "version": "3.12.0",
  "class_name": "org.apache.commons.lang3.StringUtils"
}
```

## 示例 5: 限制返回的行数

```json
{
  "group_id": "com.google.guava",
  "artifact_id": "guava",
  "version": "31.1-jre",
  "class_name": "com.google.common.collect.Lists",
  "max_lines": 100
}
```

## 示例 6: 获取完整源代码（不摘要）

```json
{
  "group_id": "org.slf4j",
  "artifact_id": "slf4j-api",
  "version": "1.7.36",
  "class_name": "org.slf4j.Logger",
  "max_lines": 0,
  "summarize_large_content": false
}
```

## 示例 7: 强制使用反编译（不使用 sources jar）

```json
{
  "group_id": "junit",
  "artifact_id": "junit",
  "version": "4.13.2",
  "class_name": "org.junit.Test",
  "prefer_sources": false
}
```

## 环境变量配置示例

```bash
# 设置自定义 Maven 仓库
export MAVEN_REPO=/custom/maven/repository

# 设置响应大小限制
export MCP_MAX_RESPONSE_SIZE=100000
export MCP_MAX_TEXT_LENGTH=20000
export MCP_MAX_LINES=1000

# 启动服务器
python -m easy_code_reader
```

## 常见 Maven 依赖示例

### Spring Boot
```json
{
  "group_id": "org.springframework.boot",
  "artifact_id": "spring-boot-autoconfigure",
  "version": "2.7.0",
  "class_name": "org.springframework.boot.autoconfigure.SpringBootApplication"
}
```

### Jackson
```json
{
  "group_id": "com.fasterxml.jackson.core",
  "artifact_id": "jackson-databind",
  "version": "2.13.3",
  "class_name": "com.fasterxml.jackson.databind.ObjectMapper"
}
```

### MyBatis
```json
{
  "group_id": "org.mybatis",
  "artifact_id": "mybatis",
  "version": "3.5.10",
  "class_name": "org.apache.ibatis.session.SqlSessionFactory"
}
```

### Lombok
```json
{
  "group_id": "org.projectlombok",
  "artifact_id": "lombok",
  "version": "1.18.24",
  "class_name": "lombok.Data"
}
```

## 运行演示脚本

```bash
# 演示从 sources JAR 提取源代码
python examples/demo.py

# 演示反编译功能
python examples/demo_decompile.py
```
