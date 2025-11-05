"""测试项目目录相关工具"""

import json
import pytest
import tempfile
from pathlib import Path
from easy_code_reader.server import EasyCodeReaderServer


@pytest.fixture
def mock_project_dir():
    """创建一个模拟的项目目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # 创建几个项目
        project1 = project_dir / "test-project1"
        project1.mkdir()
        
        # 在项目1中创建Java文件
        java_dir = project1 / "src" / "main" / "java" / "com" / "example"
        java_dir.mkdir(parents=True)
        
        java_file = java_dir / "TestClass.java"
        java_file.write_text("""package com.example;

public class TestClass {
    public static void main(String[] args) {
        System.out.println("Hello from TestClass");
    }
}
""")
        
        # 创建另一个文件
        another_file = java_dir / "AnotherClass.java"
        another_file.write_text("""package com.example;

public class AnotherClass {
    private String name;
    
    public AnotherClass(String name) {
        this.name = name;
    }
}
""")
        
        # 创建项目2
        project2 = project_dir / "test-project2"
        project2.mkdir()
        
        # 在项目2中创建Kotlin文件
        kotlin_dir = project2 / "src" / "main" / "kotlin" / "com" / "example"
        kotlin_dir.mkdir(parents=True)
        
        kotlin_file = kotlin_dir / "KotlinClass.kt"
        kotlin_file.write_text("""package com.example

class KotlinClass {
    fun hello() {
        println("Hello from Kotlin")
    }
}
""")
        
        # 创建一个空项目
        project3 = project_dir / "empty-project"
        project3.mkdir()
        
        yield project_dir


@pytest.mark.asyncio
async def test_list_all_project_with_dir_parameter(mock_project_dir):
    """测试使用 project_dir 参数列举项目"""
    server = EasyCodeReaderServer()
    
    result = await server._list_all_project(project_dir=str(mock_project_dir))
    
    assert len(result) == 1
    response_text = result[0].text
    response_data = json.loads(response_text)
    
    assert response_data["project_dir"] == str(mock_project_dir)
    assert response_data["project_count"] == 3
    assert "test-project1" in response_data["projects"]
    assert "test-project2" in response_data["projects"]
    assert "empty-project" in response_data["projects"]


@pytest.mark.asyncio
async def test_list_all_project_with_configured_dir(mock_project_dir):
    """测试使用配置的 project_dir 列举项目"""
    server = EasyCodeReaderServer(project_dir=str(mock_project_dir))
    
    result = await server._list_all_project()
    
    assert len(result) == 1
    response_text = result[0].text
    response_data = json.loads(response_text)
    
    assert response_data["project_count"] == 3
    assert "test-project1" in response_data["projects"]


@pytest.mark.asyncio
async def test_list_all_project_no_dir_configured():
    """测试没有配置 project_dir 时的错误"""
    server = EasyCodeReaderServer()
    
    result = await server._list_all_project()
    
    assert len(result) == 1
    response_text = result[0].text
    assert "项目目录信息为空" in response_text


@pytest.mark.asyncio
async def test_list_all_project_dir_not_exists():
    """测试项目目录不存在时的错误"""
    server = EasyCodeReaderServer()
    
    result = await server._list_all_project(project_dir="/non/existent/path")
    
    assert len(result) == 1
    response_text = result[0].text
    assert "项目目录不存在" in response_text


@pytest.mark.asyncio
async def test_read_project_code_with_class_name(mock_project_dir):
    """测试使用类名读取项目代码"""
    server = EasyCodeReaderServer(project_dir=str(mock_project_dir))
    
    result = await server._read_project_code(
        project_name="test-project1",
        class_name="com.example.TestClass"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    response_data = json.loads(response_text)
    
    assert response_data["project_name"] == "test-project1"
    assert response_data["class_name"] == "com.example.TestClass"
    assert "Hello from TestClass" in response_data["code"]
    assert "public class TestClass" in response_data["code"]


@pytest.mark.asyncio
async def test_read_project_code_with_path(mock_project_dir):
    """测试使用相对路径读取项目代码"""
    server = EasyCodeReaderServer(project_dir=str(mock_project_dir))
    
    result = await server._read_project_code(
        project_name="test-project1",
        class_name="src/main/java/com/example/AnotherClass.java"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    response_data = json.loads(response_text)
    
    assert response_data["project_name"] == "test-project1"
    assert "AnotherClass" in response_data["code"]
    assert "private String name" in response_data["code"]


@pytest.mark.asyncio
async def test_read_project_code_kotlin_file(mock_project_dir):
    """测试读取 Kotlin 文件"""
    server = EasyCodeReaderServer(project_dir=str(mock_project_dir))
    
    result = await server._read_project_code(
        project_name="test-project2",
        class_name="com.example.KotlinClass"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    response_data = json.loads(response_text)
    
    assert "KotlinClass" in response_data["code"]
    assert "Hello from Kotlin" in response_data["code"]


@pytest.mark.asyncio
async def test_read_project_code_with_dir_parameter(mock_project_dir):
    """测试使用 project_dir 参数读取代码"""
    server = EasyCodeReaderServer()
    
    result = await server._read_project_code(
        project_name="test-project1",
        class_name="com.example.TestClass",
        project_dir=str(mock_project_dir)
    )
    
    assert len(result) == 1
    response_text = result[0].text
    response_data = json.loads(response_text)
    
    assert "Hello from TestClass" in response_data["code"]


@pytest.mark.asyncio
async def test_read_project_code_project_not_exists(mock_project_dir):
    """测试项目不存在时的错误"""
    server = EasyCodeReaderServer(project_dir=str(mock_project_dir))
    
    result = await server._read_project_code(
        project_name="non-existent-project",
        class_name="com.example.TestClass"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    assert "项目不存在" in response_text
    assert "list_all_project" in response_text


@pytest.mark.asyncio
async def test_read_project_code_class_not_found(mock_project_dir):
    """测试类不存在时的错误"""
    server = EasyCodeReaderServer(project_dir=str(mock_project_dir))
    
    result = await server._read_project_code(
        project_name="test-project1",
        class_name="com.example.NonExistentClass"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    assert "未找到类" in response_text


@pytest.mark.asyncio
async def test_read_project_code_no_dir_configured():
    """测试没有配置 project_dir 时的错误"""
    server = EasyCodeReaderServer()
    
    result = await server._read_project_code(
        project_name="test-project1",
        class_name="com.example.TestClass"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    assert "项目目录信息为空" in response_text


@pytest.mark.asyncio
async def test_read_project_code_empty_project_name(mock_project_dir):
    """测试空项目名称的错误"""
    server = EasyCodeReaderServer(project_dir=str(mock_project_dir))
    
    result = await server._read_project_code(
        project_name="",
        class_name="com.example.TestClass"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    assert "project_name 不能为空" in response_text


@pytest.mark.asyncio
async def test_read_project_code_empty_class_name(mock_project_dir):
    """测试空类名的错误"""
    server = EasyCodeReaderServer(project_dir=str(mock_project_dir))
    
    result = await server._read_project_code(
        project_name="test-project1",
        class_name=""
    )
    
    assert len(result) == 1
    response_text = result[0].text
    assert "class_name 不能为空" in response_text


@pytest.fixture
def mock_multimodule_project():
    """创建一个模拟的多模块项目"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # 创建一个多模块 Maven 项目
        main_project = project_dir / "bugou-outer"
        main_project.mkdir()
        
        # 创建主项目的 pom.xml
        (main_project / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.jd.bugou</groupId>
    <artifactId>bugou-outer</artifactId>
    <version>1.0.0</version>
    <packaging>pom</packaging>
    
    <modules>
        <module>bugou-outer-common</module>
        <module>bugou-outer-service</module>
        <module>bugou-outer-domain</module>
    </modules>
</project>
""")
        
        # 创建 bugou-outer-common 模块
        common_module = main_project / "bugou-outer-common"
        common_module.mkdir()
        (common_module / "pom.xml").write_text("<project></project>")
        
        common_java_dir = common_module / "src" / "main" / "java" / "com" / "jd" / "bugou" / "outer" / "common"
        common_java_dir.mkdir(parents=True)
        (common_java_dir / "CommonUtils.java").write_text("""package com.jd.bugou.outer.common;

public class CommonUtils {
    public static String getVersion() {
        return "1.0.0";
    }
}
""")
        
        # 创建 bugou-outer-service 模块
        service_module = main_project / "bugou-outer-service"
        service_module.mkdir()
        (service_module / "pom.xml").write_text("<project></project>")
        
        service_java_dir = service_module / "src" / "main" / "java" / "com" / "jd" / "bugou" / "outer" / "service" / "facade" / "impl"
        service_java_dir.mkdir(parents=True)
        (service_java_dir / "AddBuyFacadeServiceImpl.java").write_text("""package com.jd.bugou.outer.service.facade.impl;

public class AddBuyFacadeServiceImpl {
    public void addBuy() {
        System.out.println("Adding buy operation");
    }
}
""")
        
        # 创建 bugou-outer-domain 模块
        domain_module = main_project / "bugou-outer-domain"
        domain_module.mkdir()
        (domain_module / "pom.xml").write_text("<project></project>")
        
        domain_java_dir = domain_module / "src" / "main" / "java" / "com" / "jd" / "bugou" / "outer" / "domain"
        domain_java_dir.mkdir(parents=True)
        (domain_java_dir / "BuyOrder.java").write_text("""package com.jd.bugou.outer.domain;

public class BuyOrder {
    private String orderId;
    private String userId;
}
""")
        
        # 创建一个非模块目录（没有 pom.xml）
        (main_project / "target").mkdir()
        (main_project / "target" / "SomeFile.java").write_text("// Should not be found")
        
        yield project_dir


@pytest.mark.asyncio
async def test_read_project_code_multimodule_service(mock_multimodule_project):
    """测试从多模块项目的 service 模块读取类"""
    server = EasyCodeReaderServer(project_dir=str(mock_multimodule_project))
    
    result = await server._read_project_code(
        project_name="bugou-outer",
        class_name="com.jd.bugou.outer.service.facade.impl.AddBuyFacadeServiceImpl"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    response_data = json.loads(response_text)
    
    assert response_data["project_name"] == "bugou-outer"
    assert "AddBuyFacadeServiceImpl" in response_data["code"]
    assert "addBuy()" in response_data["code"]
    assert "bugou-outer-service" in response_data["file_path"]


@pytest.mark.asyncio
async def test_read_project_code_multimodule_common(mock_multimodule_project):
    """测试从多模块项目的 common 模块读取类"""
    server = EasyCodeReaderServer(project_dir=str(mock_multimodule_project))
    
    result = await server._read_project_code(
        project_name="bugou-outer",
        class_name="com.jd.bugou.outer.common.CommonUtils"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    response_data = json.loads(response_text)
    
    assert "CommonUtils" in response_data["code"]
    assert "getVersion()" in response_data["code"]
    assert "bugou-outer-common" in response_data["file_path"]


@pytest.mark.asyncio
async def test_read_project_code_multimodule_domain(mock_multimodule_project):
    """测试从多模块项目的 domain 模块读取类"""
    server = EasyCodeReaderServer(project_dir=str(mock_multimodule_project))
    
    result = await server._read_project_code(
        project_name="bugou-outer",
        class_name="com.jd.bugou.outer.domain.BuyOrder"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    response_data = json.loads(response_text)
    
    assert "BuyOrder" in response_data["code"]
    assert "orderId" in response_data["code"]
    assert "bugou-outer-domain" in response_data["file_path"]


@pytest.mark.asyncio
async def test_read_project_code_multimodule_not_found(mock_multimodule_project):
    """测试在多模块项目中找不到类的情况"""
    server = EasyCodeReaderServer(project_dir=str(mock_multimodule_project))
    
    result = await server._read_project_code(
        project_name="bugou-outer",
        class_name="com.jd.bugou.outer.NotExistClass"
    )
    
    assert len(result) == 1
    response_text = result[0].text
    assert "未找到类" in response_text
