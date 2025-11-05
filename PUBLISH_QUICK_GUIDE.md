# 快速发布到 PyPI

这是一个快速参考指南。详细说明请查看 [PUBLISH_TO_PYPI.md](./PUBLISH_TO_PYPI.md)。

## 🚀 快速开始

### 1. 首次发布准备

```bash
# 注册 PyPI 账号
# https://pypi.org/account/register/

# 安装工具
pip install --upgrade build twine

# 配置 API Token
# 在 PyPI 创建 token: https://pypi.org/manage/account/token/
# 然后创建 ~/.pypirc（见下方）
```

### 2. 配置 `~/.pypirc`

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-你的PyPI_token

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-你的TestPyPI_token
```

```bash
chmod 600 ~/.pypirc  # 设置安全权限
```

### 3. 发布流程

#### 使用自动化脚本（推荐）

```bash
# 步骤 1: 更新版本号
# 编辑 pyproject.toml，修改 version = "0.1.1"

# 步骤 2: 运行检查
bash scripts/pre-publish-check.sh

# 步骤 3: 发布到测试 PyPI（首次推荐）
bash scripts/publish.sh --test

# 步骤 4: 测试安装
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ easy-code-reader

# 步骤 5: 发布到正式 PyPI
bash scripts/publish.sh
```

#### 手动发布

```bash
# 1. 更新版本号
# 编辑 pyproject.toml

# 2. 清理并构建
rm -rf dist/ build/ *.egg-info src/*.egg-info
python -m build

# 3. 检查包
twine check dist/*

# 4. 上传到测试 PyPI
twine upload --repository testpypi dist/*

# 5. 测试安装
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ easy-code-reader

# 6. 上传到正式 PyPI
twine upload dist/*

# 7. 创建 Git 标签
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

## 🤖 使用 GitHub Actions 自动发布

### 设置 Secrets

在 GitHub 仓库设置中添加：
- `PYPI_API_TOKEN`: PyPI API token
- `TEST_PYPI_API_TOKEN`: Test PyPI API token（可选）

### 触发发布

**方式 1**: 创建 GitHub Release
1. 访问 GitHub 仓库的 Releases 页面
2. 点击 "Draft a new release"
3. 创建标签（如 v0.1.0）
4. 填写发布说明
5. 点击 "Publish release"
6. GitHub Actions 自动发布到 PyPI

**方式 2**: 手动触发
1. 访问 Actions 页面
2. 选择 "Publish to PyPI" 工作流
3. 点击 "Run workflow"
4. 选择是否发布到测试 PyPI
5. 点击 "Run workflow"

## ✅ 发布检查清单

- [ ] 更新版本号（pyproject.toml）
- [ ] 运行测试（`pytest tests/`）
- [ ] 运行发布前检查（`bash scripts/pre-publish-check.sh`）
- [ ] 提交所有更改到 Git
- [ ] 在测试 PyPI 上验证（首次发布）
- [ ] 发布到正式 PyPI
- [ ] 创建 Git 标签
- [ ] 创建 GitHub Release
- [ ] 更新 README 标记已发布
- [ ] 测试安装：`uvx easy-code-reader --help`

## 📝 版本号规则

遵循[语义化版本](https://semver.org/lang/zh-CN/)：

- **MAJOR.MINOR.PATCH** (例如：1.2.3)
- **补丁版本** (0.1.0 → 0.1.1): Bug 修复
- **次版本** (0.1.0 → 0.2.0): 新功能，向后兼容
- **主版本** (0.1.0 → 1.0.0): 破坏性变更

## 🔧 常见问题

**Q: 上传时提示版本已存在？**
- PyPI 不允许重复上传相同版本，必须更新版本号

**Q: 提示 API token 无效？**
- 确认 token 包含 `pypi-` 前缀
- 检查 `~/.pypirc` 格式是否正确

**Q: 如何撤回已发布的版本？**
- PyPI 不支持删除已发布的版本
- 只能发布新版本（yank 旧版本可以标记为不推荐）

## 📚 相关文档

- [完整发布指南](./PUBLISH_TO_PYPI.md)
- [PyPI 官方文档](https://pypi.org/help/)
- [Python 打包指南](https://packaging.python.org/)

## 🎉 发布后

1. 更新 README 标记"已发布到 PyPI"
2. 在 GitHub 创建 Release
3. 分享到社交媒体
4. 监控下载统计和用户反馈
