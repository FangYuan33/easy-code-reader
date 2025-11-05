# 发布到 PyPI 指南

本文档介绍如何将 Easy Code Reader 发布到 Python Package Index (PyPI)。

## 📋 前置准备

### 1. 注册 PyPI 账号

- **正式 PyPI**: https://pypi.org/account/register/
- **测试 PyPI** (推荐先测试): https://test.pypi.org/account/register/

### 2. 安装发布工具

```bash
pip install --upgrade build twine
```

### 3. 配置 PyPI API Token

#### 创建 API Token

1. 登录 PyPI 账号
2. 访问 https://pypi.org/manage/account/token/
3. 点击 "Add API token"
4. 输入 token 名称（例如：easy-code-reader-upload）
5. 选择 Scope：
   - 首次发布选择 "Entire account"
   - 后续可以创建项目专用 token
6. 复制生成的 token（只显示一次！）

#### 配置本地认证

创建或编辑 `~/.pypirc` 文件：

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmc...你的PyPI token...

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmc...你的TestPyPI token...
```

**安全提示**: 
- 不要将 `.pypirc` 提交到 Git 仓库
- 确保文件权限设置为 `chmod 600 ~/.pypirc`

## 🚀 发布步骤

### 方式 1: 使用自动化脚本（推荐）

我们提供了两个脚本简化发布流程：

#### 发布前检查

```bash
# 运行发布前检查脚本
bash scripts/pre-publish-check.sh
```

这个脚本会检查：
- ✅ Python 版本
- ✅ 必要的工具是否已安装
- ✅ pyproject.toml 配置是否正确
- ✅ 测试是否通过
- ✅ 版本号是否已更新
- ✅ Git 状态

#### 执行发布

```bash
# 发布到测试 PyPI（首次推荐）
bash scripts/publish.sh --test

# 发布到正式 PyPI
bash scripts/publish.sh

# 发布到正式 PyPI（跳过确认）
bash scripts/publish.sh --yes
```

### 方式 2: 手动发布

#### 步骤 1: 清理旧的构建文件

```bash
rm -rf dist/ build/ *.egg-info src/*.egg-info
```

#### 步骤 2: 更新版本号

编辑 `pyproject.toml`，更新版本号：

```toml
[project]
version = "0.1.1"  # 更新为新版本
```

版本号规则：
- **补丁版本** (0.1.0 → 0.1.1): Bug 修复
- **次版本** (0.1.0 → 0.2.0): 新功能，向后兼容
- **主版本** (0.1.0 → 1.0.0): 破坏性变更

#### 步骤 3: 运行测试

```bash
pytest tests/
```

#### 步骤 4: 构建包

```bash
python -m build
```

这会在 `dist/` 目录生成：
- `easy_code_reader-x.x.x-py3-none-any.whl` (wheel 包)
- `easy_code_reader-x.x.x.tar.gz` (源码包)

#### 步骤 5: 检查包

```bash
# 检查包的元数据
twine check dist/*
```

#### 步骤 6: 上传到测试 PyPI（推荐先测试）

```bash
twine upload --repository testpypi dist/*
```

#### 步骤 7: 测试安装

```bash
# 从测试 PyPI 安装
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ easy-code-reader

# 测试运行
easy-code-reader --help
```

#### 步骤 8: 上传到正式 PyPI

```bash
twine upload dist/*
```

#### 步骤 9: 验证发布

```bash
# 从正式 PyPI 安装
pip install easy-code-reader

# 测试运行
easy-code-reader --help

# 或使用 uvx 测试
uvx easy-code-reader --help
```

#### 步骤 10: 创建 Git Tag

```bash
# 创建版本标签
git tag -a v0.1.0 -m "Release version 0.1.0"
git push origin v0.1.0

# 或创建 GitHub Release
```

## 🤖 自动化发布（GitHub Actions）

### 设置 GitHub Secrets

1. 访问 GitHub 仓库设置: Settings → Secrets and variables → Actions
2. 添加以下 secrets:
   - `PYPI_API_TOKEN`: 你的 PyPI API token
   - `TEST_PYPI_API_TOKEN`: 你的 Test PyPI API token (可选)

### 使用工作流

我们提供了 `.github/workflows/publish-to-pypi.yml` 工作流。

#### 触发方式 1: 创建 GitHub Release

1. 访问仓库的 Releases 页面
2. 点击 "Draft a new release"
3. 创建新标签（例如：v0.1.0）
4. 填写发布说明
5. 点击 "Publish release"
6. GitHub Actions 会自动构建并发布到 PyPI

#### 触发方式 2: 手动触发

1. 访问 Actions 页面
2. 选择 "Publish to PyPI" 工作流
3. 点击 "Run workflow"
4. 选择是否发布到测试 PyPI
5. 点击 "Run workflow"

## 📝 版本发布检查清单

每次发布新版本前，请确认：

- [ ] 所有测试通过 (`pytest tests/`)
- [ ] 更新了版本号 (`pyproject.toml`)
- [ ] 更新了 `README.md` 中的变更说明
- [ ] 更新了 `CHANGELOG.md`（如果有）
- [ ] 提交了所有更改到 Git
- [ ] 清理了旧的构建文件
- [ ] 运行了 `twine check dist/*`
- [ ] 在测试 PyPI 上验证通过（首次发布）
- [ ] 创建了 Git tag
- [ ] 创建了 GitHub Release

## 🔧 常见问题

### 1. 包名已被占用

错误信息：`The name 'easy-code-reader' is too similar to an existing project`

解决方案：
- 在 `pyproject.toml` 中修改 `name` 字段
- 建议使用更独特的名称，如 `easy-code-reader-mcp`

### 2. 版本号已存在

错误信息：`File already exists`

解决方案：
- PyPI 不允许重复上传相同版本号
- 必须更新版本号后重新发布
- **不要**删除 dist 文件夹后重新上传相同版本

### 3. API Token 无效

错误信息：`Invalid or non-existent authentication information`

解决方案：
- 确认 token 复制完整（包括 `pypi-` 前缀）
- 检查 `~/.pypirc` 格式是否正确
- 重新生成 API token

### 4. 依赖包无法安装

错误信息：测试安装时某些依赖找不到

解决方案：
- 使用 `--extra-index-url https://pypi.org/simple/` 参数
- 这样可以从正式 PyPI 安装依赖，从测试 PyPI 安装你的包

### 5. 包内容不完整

解决方案：
- 检查 `pyproject.toml` 中的 `[tool.setuptools]` 配置
- 确保 `packages` 和 `package-dir` 设置正确
- 使用 `python -m build --wheel` 检查生成的 wheel 包内容

## 📚 相关资源

- [PyPI 官方文档](https://pypi.org/help/)
- [Python 打包用户指南](https://packaging.python.org/)
- [Twine 文档](https://twine.readthedocs.io/)
- [Setuptools 文档](https://setuptools.pypa.io/)
- [语义化版本](https://semver.org/lang/zh-CN/)

## 🎯 发布后的工作

1. **更新文档**
   - 在 README 中标记"已发布到 PyPI"
   - 更新安装说明

2. **宣传推广**
   - 在 GitHub 创建 Release
   - 在社交媒体分享
   - 更新项目网站

3. **监控反馈**
   - 关注 PyPI 下载统计
   - 处理 GitHub Issues
   - 收集用户反馈

4. **持续维护**
   - 定期发布 bug 修复版本
   - 添加新功能
   - 保持依赖更新

## 🔐 安全建议

1. **保护 API Token**
   - 不要在代码中硬编码 token
   - 不要提交 `.pypirc` 到版本控制
   - 定期轮换 token

2. **使用项目专用 Token**
   - 首次发布后，创建项目专用 token
   - 限制 token 权限范围

3. **启用 2FA**
   - 在 PyPI 账号上启用两步验证
   - 提高账号安全性

## 📞 获取帮助

如有问题，请：
1. 查看本文档的常见问题部分
2. 访问 [PyPI 帮助文档](https://pypi.org/help/)
3. 在项目 Issues 中提问
4. 查看 [Python 打包讨论组](https://discuss.python.org/c/packaging/)
