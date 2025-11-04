# 迁移到 uvx 启动方式

## 概述

本文档记录了从 npx/npm 启动方式迁移到 uvx 启动方式的所有更改。

## 更改内容

### 1. 删除的文件
- `bin/easy-jar-reader.js` - npm 启动脚本（已删除整个 bin 目录）
- `package.json` - npm 包配置文件

### 2. 修改的文件

#### pyproject.toml
添加了 `[project.scripts]` 配置，使包可以通过 uvx 运行：

```toml
[project.scripts]
easy-jar-reader = "easy_jar_reader.__main__:main"
```

#### src/easy_jar_reader/__main__.py
- 重命名 `main` 函数导入为 `server_main`
- 新增 `main()` 函数作为脚本入口点
- 保持命令行参数解析逻辑不变

#### README.md
- 移除所有 npm/npx 相关的安装和使用说明
- 添加 uv/uvx 安装和使用说明
- 更新 Claude Desktop 配置示例，优先推荐 uvx 方式
- 更新项目结构说明，移除 bin 目录

## 新的使用方式

### 推荐方式：使用 uvx（开箱即用）

```bash
# 默认 Maven 仓库
uvx easy-jar-reader

# 自定义 Maven 仓库
uvx easy-jar-reader --maven-repo /path/to/maven/repository
```

### Claude Desktop 配置（推荐）

```json
{
  "mcpServers": {
    "easy-jar-reader": {
      "command": "uvx",
      "args": [
        "easy-jar-reader",
        "--maven-repo",
        "/custom/path/to/maven/repository"
      ],
      "env": {}
    }
  }
}
```

注意：不要使用 `-m` 参数，uvx 会自动找到 `easy-jar-reader` 包并执行其脚本入口点。

## 优势

1. **开箱即用**：用户无需预先安装，uvx 会自动下载和运行
2. **简化依赖**：不再需要 Node.js 环境
3. **更快的启动**：uv 比 npm/pip 更快
4. **自动隔离**：uvx 为每个包创建独立的虚拟环境
5. **简化项目结构**：移除了 npm 相关文件

## 兼容性说明

迁移后仍然支持以下启动方式：

1. Python 模块方式：`python -m easy_jar_reader`
2. 直接命令方式（安装后）：`easy-jar-reader`
3. uvx 方式（推荐）：`uvx easy-jar-reader`

所有方式都支持 `--maven-repo` 参数来指定自定义 Maven 仓库路径。
