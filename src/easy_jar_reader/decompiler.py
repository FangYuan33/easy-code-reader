"""
Java 反编译器集成模块 - Easy JAR Reader MCP 服务器

提供 Fernflower 反编译器集成。
"""

import subprocess
import zipfile
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class JavaDecompiler:
    """
    Java 字节码反编译器
    
    使用 Fernflower (IntelliJ IDEA 使用的反编译器) 进行反编译。
    """
    
    def __init__(self):
        """
        初始化 Java 反编译器
        
        检测 Fernflower 反编译器是否可用。
        """
        self.fernflower_jar = self._detect_fernflower()
    
    def _detect_fernflower(self) -> Optional[Path]:
        """
        检测 Fernflower 反编译器
        
        扫描系统以查找 Fernflower 反编译器。
        
        返回:
            Fernflower JAR 文件路径，如果未找到则返回 None
        """
        # 检查 Fernflower
        try:
            # 获取当前模块文件的目录
            current_module_dir = Path(__file__).parent

            # 首先检查包内的 decompilers/ 目录（用于已安装的包）
            fernflower_path = current_module_dir / "decompilers" / "fernflower.jar"
            logger.info(f"尝试从包内查找 Fernflower: {fernflower_path}")
            if fernflower_path.exists():
                logger.info(f"找到 Fernflower 反编译器: {fernflower_path}")
                return fernflower_path

            # 回退到检查项目根目录的 decompilers/（用于开发环境）
            project_root = current_module_dir.parent.parent
            fernflower_path = project_root / "decompilers" / "fernflower.jar"
            logger.info(f"尝试从项目根目录查找 Fernflower: {fernflower_path}")
            if fernflower_path.exists():
                logger.info(f"找到 Fernflower 反编译器: {fernflower_path}")
                return fernflower_path
        except Exception as e:
            logger.debug(f"Fernflower 检测失败: {e}")
        
        # 调试信息：在返回 None 前显示详细的搜索信息
        logger.warning("🔍 Fernflower 检测失败，显示调试信息:")
        try:
            current_module_dir = Path(__file__).parent
            project_root = current_module_dir.parent.parent
            
            logger.info(f"  📂 当前模块目录: {current_module_dir}")
            logger.info(f"  🏠 项目根目录: {project_root}")
            logger.info(f"  💼 当前工作目录: {Path.cwd()}")
            
            # 检查并显示相关目录内容
            if current_module_dir.exists():
                logger.info(f"  📁 模块目录内容: {list(current_module_dir.iterdir())}")
            
            if project_root.exists():
                logger.info(f"  📁 项目根目录内容: {list(project_root.iterdir())}")
                decompilers_dir = project_root / "decompilers"
                if decompilers_dir.exists():
                    logger.info(f"  📁 decompilers 目录内容: {list(decompilers_dir.iterdir())}")
            
            # 递归搜索所有 fernflower.jar 文件
            logger.info("  🔍 递归搜索所有 fernflower.jar 文件:")
            for jar_file in project_root.rglob("fernflower.jar"):
                logger.info(f"    🎯 发现: {jar_file}")
                
        except Exception as debug_e:
            logger.debug(f"调试信息收集失败: {debug_e}")
        
        return None
    
    def decompile_class(self, jar_path: Path, class_name: str) -> Optional[str]:
        """
        反编译 JAR 文件中的特定类
        
        从指定的 JAR 文件中提取并反编译特定的 Java 类。
        使用缓存机制：如果已经反编译过，直接从缓存读取。
        
        参数:
            jar_path: JAR 文件路径
            class_name: 要反编译的类的完全限定名（如 com.example.MyClass）
            
        返回:
            反编译后的源代码字符串，如果失败则返回基本的类信息
        """
        logger.info(f"尝试从 {jar_path} 反编译类 {class_name}")
        
        # 检查是否有可用的反编译器
        if not self.fernflower_jar:
            logger.warning("Fernflower 反编译器不可用，使用回退方案")
            return self._fallback_class_info(jar_path, class_name)
        
        # 获取输出目录（jar 包所在目录的 easy-jar-reader 子目录）
        jar_dir = jar_path.parent
        output_base_dir = jar_dir / "easy-jar-reader"
        
        # 从 jar 文件名中提取名称（不包含扩展名）作为子目录
        output_dir = output_base_dir
        
        # 定义反编译后的 JAR 路径和类文件在 JAR 中的路径
        decompiled_jar = output_dir / jar_path.name
        java_file_path_in_jar = class_name.replace('.', '/') + '.java'
        
        # 检查缓存：查看是否已经反编译过
        # 反编译后的文件存储在一个与原 jar 同名的 jar 中
        if decompiled_jar.exists():
            logger.info(f"发现缓存的反编译 JAR: {decompiled_jar}")
            try:
                with zipfile.ZipFile(decompiled_jar, 'r') as zf:
                    if java_file_path_in_jar in zf.namelist():
                        logger.info(f"从缓存 JAR 中读取已反编译的类: {java_file_path_in_jar}")
                        return zf.read(java_file_path_in_jar).decode('utf-8')
                    else:
                        logger.warning(f"缓存 JAR 中未找到类文件: {java_file_path_in_jar}，将重新反编译")
            except Exception as e:
                logger.warning(f"读取缓存 JAR 失败: {e}，将重新反编译")
        
        # 创建输出目录（如果不存在）
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建输出目录: {output_dir}")
        except Exception as e:
            logger.error(f"创建输出目录失败: {e}")
            return self._fallback_class_info(jar_path, class_name)
        
        # 执行 Fernflower 反编译
        # 注意：Fernflower 只支持反编译整个 JAR，不支持单个 class 文件
        # 但这是可接受的，因为：
        # 1. 反编译后的所有类都会被缓存
        # 2. 后续访问该 JAR 中的任何类都会直接从缓存读取
        # 3. 避免了对同一 JAR 的重复反编译操作
        try:
            logger.info(f"使用 Fernflower 反编译 JAR: {jar_path}")
            result = subprocess.run([
                'java', '-jar', self.fernflower_jar,
                str(jar_path), str(output_dir)
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                logger.error(f"Fernflower 反编译失败: {result.stderr}")
                return self._fallback_class_info(jar_path, class_name)
            
            # Fernflower 会将输出放在一个与原 jar 同名的 jar 中
            # 直接从该 jar 文件中读取 .java 文件，无需解压
            decompiled_jar = output_dir / jar_path.name
            if not decompiled_jar.exists():
                logger.error(f"Fernflower 未生成预期的 JAR 文件: {decompiled_jar}")
                return self._fallback_class_info(jar_path, class_name)
            
            try:
                logger.info(f"从反编译后的 JAR 中读取 .java 文件: {decompiled_jar}")
                with zipfile.ZipFile(decompiled_jar, 'r') as zf:
                    if java_file_path_in_jar in zf.namelist():
                        logger.info(f"成功反编译类: {class_name}")
                        return zf.read(java_file_path_in_jar).decode('utf-8')
                    else:
                        logger.error(f"反编译后的 JAR 中未找到文件: {java_file_path_in_jar}")
                        return self._fallback_class_info(jar_path, class_name)
            except zipfile.BadZipFile as e:
                logger.error(f"反编译后的 JAR 文件损坏: {e}")
                return self._fallback_class_info(jar_path, class_name)
            except Exception as e:
                logger.error(f"读取反编译后的 JAR 失败: {e}")
                return self._fallback_class_info(jar_path, class_name)
                
        except Exception as e:
            logger.error(f"反编译失败: {e}", exc_info=True)
            return self._fallback_class_info(jar_path, class_name)
    
    def _fallback_class_info(self, jar_path: Path, class_name: str) -> str:
        """当反编译失败时的回退方案，返回基本类信息"""
        try:
            class_file_path = class_name.replace('.', '/') + '.class'
            
            with zipfile.ZipFile(jar_path, 'r') as jar:
                if class_file_path in jar.namelist():
                    class_data = jar.read(class_file_path)
                    
                    # Basic bytecode analysis
                    info = "// 反编译不可用\n"
                    info += f"// 类: {class_name}\n"
                    info += f"// 大小: {len(class_data)} 字节\n"
                    info += f"// 位置: {jar_path}\n\n"
                    
                    # Try to extract some basic info from bytecode
                    magic = class_data[:4]
                    if magic == b'\xca\xfe\xba\xbe':
                        minor_version = int.from_bytes(class_data[4:6], 'big')
                        major_version = int.from_bytes(class_data[6:8], 'big')
                        info += f"// Java 字节码版本: {major_version}.{minor_version}\n"
                        
                        # Map major version to Java version
                        java_version = self._map_bytecode_version(major_version)
                        if java_version:
                            info += f"// 编译 Java 版本: {java_version}\n"
                    
                    info += f"\npublic class {class_name.split('.')[-1]} {{\n"
                    info += "    // 反编译需要 Fernflower\n"
                    info += "    // 请确保 Fernflower 反编译器可用\n"
                    info += "}\n"
                    
                    return info
        
        except Exception as e:
            return f"// 读取类文件时出错: {e}"
        
        return f"// 未找到类: {class_name}"
    
    def _map_bytecode_version(self, major_version: int) -> Optional[str]:
        """将字节码主版本号映射到 Java 版本"""
        version_map = {
            45: "1.1", 46: "1.2", 47: "1.3", 48: "1.4", 49: "5",
            50: "6", 51: "7", 52: "8", 53: "9", 54: "10",
            55: "11", 56: "12", 57: "13", 58: "14", 59: "15",
            60: "16", 61: "17", 62: "18", 63: "19", 64: "20", 65: "21"
        }
        return version_map.get(major_version)
