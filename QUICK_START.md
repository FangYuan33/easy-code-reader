# Easy Code Reader - 快速开始指南

# Easy Code Reader - 快速开始指南

> **📢 发布状态说明**: 
> - 如果包**已发布到 PyPI**：可以直接使用下方的"方式 1"（uvx），真正开箱即用
> - 如果包**未发布到 PyPI**：需要先手动安装（见"临时方案"部分）
>
> 检查是否已发布：访问 https://pypi.org/project/easy-code-reader/

## 🎯 方式 1: 使用 uvx（推荐 - 开箱即用）

> **前提**: 包已发布到 PyPI

最简单的使用方式，无需安装，直接运行：

```bash
uvx easy-code-reader
```

### 首次使用 uv？

如果您还没有安装 uv，可以快速安装：

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Claude Desktop 配置（开箱即用）

编辑 Claude Desktop 配置文件：
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### 基本配置（使用默认 Maven 路径）

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

### 自定义 Maven 路径配置

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

## 常见问题

### 1. 我需要先安装什么吗？

**不需要！** 如果您已经安装了 `uv`，可以直接使用 `uvx easy-code-reader`。
如果您还没有安装 `uv`，可以通过以下方式安装：

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Maven 仓库在哪里？

默认的 Maven 仓库位置：
- **macOS/Linux**: `~/.m2/repository`
- **Windows**: `C:\Users\<用户名>\.m2\repository`

如果您使用的是自定义位置，请在配置中指定 `--maven-repo` 参数。

### 3. 如何验证配置是否正确？

1. 在终端运行 `uvx easy-code-reader --help`，应该看到帮助信息
2. 在 Claude Desktop 中，重启应用后检查是否能看到 `easy-code-reader` 工具
3. 尝试读取一个已知的 JAR 包源码

### 4. 我可以使用其他方式运行吗？

可以！除了 `uvx`，还支持：

**方式 1**: 安装后直接运行
```bash
pip install easy-code-reader
easy-code-reader
```

**方式 2**: Python 模块方式
```bash
python -m easy_code_reader
```

## 示例用法

在 Claude 中使用 `read_jar_source` 工具：

```json
{
  "group_id": "org.springframework",
  "artifact_id": "spring-core",
  "version": "5.3.21",
  "class_name": "org.springframework.core.SpringVersion"
}
```

## 获取帮助

- GitHub: https://github.com/FangYuan33/easy-code-reader
- Issues: https://github.com/FangYuan33/easy-code-reader/issues
