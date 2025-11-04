#!/bin/bash

# Easy JAR Reader - PyPI 发布脚本
# 简化发布流程

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
TEST_PYPI=false
SKIP_CONFIRM=false
SKIP_TESTS=false
SKIP_CHECKS=false

# 打印函数
print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}  Easy JAR Reader - PyPI 发布脚本${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_step() {
    echo -e "\n${BLUE}>>> $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}! $1${NC}"
}

print_info() {
    echo -e "${BLUE}[i] $1${NC}"
}

# 显示帮助信息
show_usage() {
    cat << EOF
用法: $0 [选项]

选项:
    --test              发布到测试 PyPI (https://test.pypi.org)
    --yes, -y           跳过确认提示
    --skip-tests        跳过测试
    --skip-checks       跳过发布前检查
    --help, -h          显示此帮助信息

示例:
    $0                  # 发布到正式 PyPI（会有确认提示）
    $0 --test           # 发布到测试 PyPI
    $0 --yes            # 发布到正式 PyPI（跳过确认）
    $0 --test --yes     # 发布到测试 PyPI（跳过确认）

EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --test)
            TEST_PYPI=true
            shift
            ;;
        --yes|-y)
            SKIP_CONFIRM=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-checks)
            SKIP_CHECKS=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}未知选项: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

print_header

# 确定目标仓库
if [ "$TEST_PYPI" = true ]; then
    REPOSITORY="testpypi"
    REPOSITORY_URL="https://test.pypi.org"
    print_info "目标仓库: 测试 PyPI (${REPOSITORY_URL})"
else
    REPOSITORY="pypi"
    REPOSITORY_URL="https://pypi.org"
    print_info "目标仓库: 正式 PyPI (${REPOSITORY_URL})"
fi

# 获取版本号
if [ -f "pyproject.toml" ]; then
    VERSION=$(grep "^version = " pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
    print_info "当前版本: ${VERSION}"
else
    print_error "找不到 pyproject.toml 文件"
    exit 1
fi

# 运行发布前检查
if [ "$SKIP_CHECKS" = false ]; then
    print_step "运行发布前检查..."
    if [ -f "scripts/pre-publish-check.sh" ]; then
        if bash scripts/pre-publish-check.sh; then
            print_success "发布前检查通过"
        else
            print_error "发布前检查失败"
            echo -e "\n使用 ${YELLOW}--skip-checks${NC} 跳过检查（不推荐）"
            exit 1
        fi
    else
        print_warning "找不到 pre-publish-check.sh 脚本，跳过检查"
    fi
else
    print_warning "跳过发布前检查"
fi

# 确认发布
if [ "$SKIP_CONFIRM" = false ]; then
    echo -e "\n${YELLOW}准备发布到 $REPOSITORY_URL${NC}"
    echo -e "版本: ${GREEN}${VERSION}${NC}"
    echo -e "包名: ${GREEN}easy-jar-reader${NC}"
    echo -e "\n${RED}警告: 发布到 PyPI 后无法删除或覆盖已发布的版本！${NC}"
    read -p "确认发布？(yes/no): " CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
        print_info "取消发布"
        exit 0
    fi
fi

# 步骤 1: 清理旧的构建文件
print_step "步骤 1/5: 清理旧的构建文件..."
rm -rf dist/ build/ *.egg-info src/*.egg-info
print_success "清理完成"

# 步骤 2: 运行测试（可选）
if [ "$SKIP_TESTS" = false ] && [ -d "tests" ]; then
    print_step "步骤 2/5: 运行测试..."
    if command -v pytest &> /dev/null || python3 -c "import pytest" 2>/dev/null; then
        if python3 -m pytest tests/ -v; then
            print_success "测试通过"
        else
            print_error "测试失败"
            exit 1
        fi
    else
        print_warning "pytest 未安装，跳过测试"
    fi
else
    print_step "步骤 2/5: 跳过测试"
fi

# 步骤 3: 构建包
print_step "步骤 3/5: 构建包..."
if ! python3 -c "import build" 2>/dev/null; then
    print_warning "build 模块未安装，正在安装..."
    pip3 install build
fi

python3 -m build
print_success "构建完成"

# 显示构建的文件
echo -e "\n${BLUE}构建的文件:${NC}"
ls -lh dist/

# 步骤 4: 检查包
print_step "步骤 4/5: 检查包..."
if ! python3 -c "import twine" 2>/dev/null; then
    print_warning "twine 模块未安装，正在安装..."
    pip3 install twine
fi

if twine check dist/*; then
    print_success "包检查通过"
else
    print_error "包检查失败"
    exit 1
fi

# 步骤 5: 上传到 PyPI
print_step "步骤 5/5: 上传到 ${REPOSITORY}..."

if [ "$TEST_PYPI" = true ]; then
    # 上传到测试 PyPI
    if twine upload --repository testpypi dist/*; then
        print_success "上传成功！"
        echo -e "\n${GREEN}========================================${NC}"
        echo -e "${GREEN}发布成功！${NC}"
        echo -e "${GREEN}========================================${NC}\n"
        echo -e "包地址: ${BLUE}${REPOSITORY_URL}/project/easy-jar-reader/${NC}"
        echo -e "\n测试安装:"
        echo -e "  ${BLUE}pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ easy-jar-reader${NC}"
        echo -e "\n测试运行:"
        echo -e "  ${BLUE}easy-jar-reader --help${NC}"
        echo -e "  ${BLUE}uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ easy-jar-reader --help${NC}\n"
    else
        print_error "上传失败"
        exit 1
    fi
else
    # 上传到正式 PyPI
    if twine upload dist/*; then
        print_success "上传成功！"
        echo -e "\n${GREEN}========================================${NC}"
        echo -e "${GREEN}发布成功！🎉${NC}"
        echo -e "${GREEN}========================================${NC}\n"
        echo -e "包地址: ${BLUE}${REPOSITORY_URL}/project/easy-jar-reader/${NC}"
        echo -e "\n安装命令:"
        echo -e "  ${BLUE}pip install easy-jar-reader${NC}"
        echo -e "  ${BLUE}uvx easy-jar-reader${NC}"
        echo -e "\n下一步建议:"
        echo -e "  1. 创建 Git 标签: ${BLUE}git tag -a v${VERSION} -m \"Release v${VERSION}\"${NC}"
        echo -e "  2. 推送标签: ${BLUE}git push origin v${VERSION}${NC}"
        echo -e "  3. 在 GitHub 创建 Release"
        echo -e "  4. 更新文档标记包已发布\n"
    else
        print_error "上传失败"
        exit 1
    fi
fi
