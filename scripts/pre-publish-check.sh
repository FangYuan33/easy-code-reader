#!/bin/bash

# Easy JAR Reader - 发布前检查脚本
# 用于在发布到 PyPI 之前验证项目状态

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 计数器
PASSED=0
FAILED=0
WARNINGS=0

# 打印函数
print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}  Easy JAR Reader - 发布前检查${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_check() {
    echo -e "${BLUE}[检查]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((PASSED++))
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((FAILED++))
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
    ((WARNINGS++))
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

print_summary() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}  检查摘要${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo -e "${GREEN}通过: $PASSED${NC}"
    echo -e "${RED}失败: $FAILED${NC}"
    echo -e "${YELLOW}警告: $WARNINGS${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

print_header

# 1. 检查 Python 版本
print_check "检查 Python 版本..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
        print_success "Python 版本: $PYTHON_VERSION (满足要求: >=3.10)"
    else
        print_error "Python 版本: $PYTHON_VERSION (需要: >=3.10)"
    fi
else
    print_error "未找到 Python 3"
fi

# 2. 检查必要的工具
print_check "检查必要的构建工具..."

if command -v pip3 &> /dev/null; then
    print_success "pip3 已安装"
else
    print_error "pip3 未安装"
fi

if python3 -c "import build" 2>/dev/null; then
    print_success "build 模块已安装"
else
    print_warning "build 模块未安装，运行: pip3 install build"
fi

if python3 -c "import twine" 2>/dev/null; then
    print_success "twine 模块已安装"
else
    print_warning "twine 模块未安装，运行: pip3 install twine"
fi

# 3. 检查项目文件
print_check "检查项目文件..."

if [ -f "pyproject.toml" ]; then
    print_success "pyproject.toml 存在"
else
    print_error "pyproject.toml 不存在"
fi

if [ -f "README.md" ]; then
    print_success "README.md 存在"
else
    print_warning "README.md 不存在"
fi

if [ -f "LICENSE" ]; then
    print_success "LICENSE 存在"
else
    print_warning "LICENSE 不存在"
fi

if [ -d "src/easy_jar_reader" ]; then
    print_success "源代码目录存在"
else
    print_error "源代码目录不存在"
fi

# 4. 检查 pyproject.toml 配置
print_check "检查 pyproject.toml 配置..."

if grep -q "name = \"easy-jar-reader\"" pyproject.toml; then
    print_success "包名称已设置"
else
    print_error "包名称未设置或不正确"
fi

if grep -q "version = " pyproject.toml; then
    VERSION=$(grep "version = " pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
    print_success "版本号: $VERSION"
else
    print_error "版本号未设置"
fi

if grep -q "description = " pyproject.toml; then
    print_success "包描述已设置"
else
    print_warning "包描述未设置"
fi

if grep -q "authors = " pyproject.toml; then
    print_success "作者信息已设置"
else
    print_warning "作者信息未设置"
fi

if grep -q "\[project.scripts\]" pyproject.toml; then
    print_success "脚本入口点已配置"
else
    print_error "脚本入口点未配置"
fi

# 5. 检查依赖
print_check "检查项目依赖..."

if python3 -c "import mcp" 2>/dev/null; then
    print_success "mcp 依赖已安装"
else
    print_warning "mcp 依赖未安装（发布时会自动处理）"
fi

# 6. 运行测试
print_check "运行测试..."

if [ -d "tests" ]; then
    if command -v pytest &> /dev/null || python3 -c "import pytest" 2>/dev/null; then
        print_info "运行 pytest..."
        if python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20; then
            print_success "测试通过"
        else
            print_error "测试失败"
        fi
    else
        print_warning "pytest 未安装，跳过测试"
    fi
else
    print_warning "tests 目录不存在"
fi

# 7. 检查 Git 状态
print_check "检查 Git 状态..."

if command -v git &> /dev/null && [ -d ".git" ]; then
    if git diff-index --quiet HEAD -- 2>/dev/null; then
        print_success "Git 工作区干净"
    else
        print_warning "有未提交的更改"
        git status --short
    fi
    
    # 检查当前分支
    BRANCH=$(git branch --show-current)
    print_info "当前分支: $BRANCH"
    
    # 检查是否有未推送的提交
    if git rev-parse @{u} >/dev/null 2>&1; then
        UNPUSHED=$(git log @{u}.. --oneline | wc -l)
        if [ "$UNPUSHED" -gt 0 ]; then
            print_warning "有 $UNPUSHED 个未推送的提交"
        else
            print_success "所有提交已推送"
        fi
    fi
else
    print_warning "不是 Git 仓库或 Git 未安装"
fi

# 8. 检查是否有旧的构建文件
print_check "检查构建文件..."

if [ -d "dist" ] || [ -d "build" ] || ls *.egg-info 2>/dev/null; then
    print_warning "发现旧的构建文件，建议运行: rm -rf dist/ build/ *.egg-info"
else
    print_success "没有旧的构建文件"
fi

# 9. 检查 PyPI 认证配置
print_check "检查 PyPI 认证配置..."

if [ -f "$HOME/.pypirc" ]; then
    print_success "~/.pypirc 文件存在"
    
    # 检查文件权限
    PERMS=$(stat -f "%Lp" "$HOME/.pypirc" 2>/dev/null || stat -c "%a" "$HOME/.pypirc" 2>/dev/null)
    if [ "$PERMS" = "600" ]; then
        print_success "文件权限正确 (600)"
    else
        print_warning "文件权限建议设置为 600: chmod 600 ~/.pypirc"
    fi
else
    print_warning "~/.pypirc 不存在，发布时需要手动输入凭据"
fi

# 10. 检查必要的文件是否在 Git 中
print_check "检查关键文件是否已跟踪..."

if [ -d ".git" ]; then
    for file in "pyproject.toml" "README.md" "src/easy_jar_reader/__init__.py"; do
        if git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
            print_success "$file 已在版本控制中"
        else
            print_warning "$file 未在版本控制中"
        fi
    done
fi

# 打印摘要
print_summary

# 提供下一步建议
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有关键检查都通过了！${NC}\n"
    echo -e "下一步操作："
    echo -e "  1. 清理旧构建: ${BLUE}rm -rf dist/ build/ *.egg-info src/*.egg-info${NC}"
    echo -e "  2. 构建包: ${BLUE}python3 -m build${NC}"
    echo -e "  3. 检查包: ${BLUE}twine check dist/*${NC}"
    echo -e "  4. 发布到测试 PyPI: ${BLUE}bash scripts/publish.sh --test${NC}"
    echo -e "  5. 发布到正式 PyPI: ${BLUE}bash scripts/publish.sh${NC}\n"
    exit 0
else
    echo -e "${RED}✗ 有 $FAILED 个检查失败，请修复后再发布${NC}\n"
    exit 1
fi
