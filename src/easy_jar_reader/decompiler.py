"""
Java 反编译器集成模块 - Easy JAR Reader MCP 服务器

提供 Java 反编译器和字节码分析工具的集成。
支持 CFR、Procyon、Fernflower 和内置的 javap 工具。
"""

import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class JavaDecompiler:
    """
    Java 字节码反编译器
    
    支持的反编译器：
    - CFR: 现代化的 Java 反编译器，支持最新的 Java 特性
    - Procyon: 高质量的开源反编译器
    - Fernflower: IntelliJ IDEA 使用的反编译器
    - javap: JDK 内置的字节码反汇编工具
    """
    
    def __init__(self):
        """
        初始化 Java 反编译器
        
        自动检测系统中可用的反编译器。
        """
        self.available_decompilers = self._detect_decompilers()
        logger.info(f"可用的反编译器: {list(self.available_decompilers.keys())}")
    
    def _detect_decompilers(self) -> Dict[str, str]:
        """
        检测系统中可用的反编译器
        
        扫描系统以查找可用的 Java 反编译器。
        
        返回:
            字典，键为反编译器名称，值为可执行文件路径
        """
        decompilers = {}
        
        # 检查 CFR
        try:
            cfr_paths = ['cfr.jar', 'decompilers/cfr.jar']
            for cfr_path in cfr_paths:
                if Path(cfr_path).exists():
                    result = subprocess.run(['java', '-jar', cfr_path, '--help'],
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0 or 'CFR' in result.stdout or 'CFR' in result.stderr:
                        decompilers['cfr'] = cfr_path
                        logger.info(f"Found CFR decompiler at {cfr_path}")
                        break
        except Exception as e:
            logger.debug(f"CFR detection failed: {e}")
        
        # 检查 Fernflower
        try:
            fernflower_paths = ['fernflower.jar', 'decompilers/fernflower.jar']
            for fernflower_path in fernflower_paths:
                if Path(fernflower_path).exists():
                    decompilers['fernflower'] = fernflower_path
                    logger.info(f"Found Fernflower decompiler at {fernflower_path}")
                    break
        except Exception as e:
            logger.debug(f"Fernflower detection failed: {e}")
        
        # 检查 Procyon
        try:
            procyon_paths = ['procyon-decompiler.jar', 'decompilers/procyon-decompiler.jar']
            for procyon_path in procyon_paths:
                if Path(procyon_path).exists():
                    result = subprocess.run(['java', '-jar', procyon_path, '--help'],
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0 or 'Procyon' in result.stdout or 'Procyon' in result.stderr:
                        decompilers['procyon'] = procyon_path
                        logger.info(f"Found Procyon decompiler at {procyon_path}")
                        break
        except Exception as e:
            logger.debug(f"Procyon detection failed: {e}")
        
        # 检查 javap
        try:
            result = subprocess.run(['javap', '-help'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 or result.returncode == 2:  # javap returns 2 on --help
                decompilers['javap'] = 'javap'
                logger.info("Found javap")
        except Exception as e:
            logger.debug(f"javap detection failed: {e}")
        
        return decompilers
    
    def decompile_class(self, jar_path: Path, class_name: str,
                       decompiler: Optional[str] = None) -> Optional[str]:
        """
        反编译 JAR 文件中的特定类
        
        从指定的 JAR 文件中提取并反编译特定的 Java 类。
        
        参数:
            jar_path: JAR 文件路径
            class_name: 要反编译的类的完全限定名（如 com.example.MyClass）
            decompiler: 指定使用的反编译器名称，如果为 None 则自动选择
            
        返回:
            反编译后的源代码字符串，如果失败则返回基本的类信息
        """
        logger.info(f"尝试从 {jar_path} 反编译类 {class_name}")
        
        # 检查是否有可用的反编译器
        if not self.available_decompilers:
            logger.warning("没有可用的反编译器，使用回退方案")
            return self._fallback_class_info(jar_path, class_name)
        
        # 选择反编译器
        if not decompiler:
            # 按优先级选择
            from .config import Config
            for preferred in Config.DECOMPILER_PRIORITY:
                if preferred in self.available_decompilers:
                    decompiler = preferred
                    break
            if not decompiler:
                decompiler = next(iter(self.available_decompilers.keys()))
        
        if decompiler not in self.available_decompilers:
            logger.warning(f"反编译器 {decompiler} 不可用")
            return self._fallback_class_info(jar_path, class_name)
        
        logger.info(f"使用反编译器: {decompiler}")
        
        try:
            # 使用临时目录进行反编译操作
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # 提取类文件
                class_file_path = class_name.replace('.', '/') + '.class'
                logger.debug(f"查找类文件: {class_file_path}")
                
                with zipfile.ZipFile(jar_path, 'r') as jar:
                    if class_file_path not in jar.namelist():
                        logger.error(f"在 JAR 中未找到类文件: {class_file_path}")
                        return self._fallback_class_info(jar_path, class_name)
                    
                    # 提取类文件到临时目录
                    extracted_class = temp_path / 'extracted.class'
                    logger.debug(f"提取到: {extracted_class}")
                    with open(extracted_class, 'wb') as f:
                        f.write(jar.read(class_file_path))
                    
                    # 执行反编译
                    result = self._run_decompiler(decompiler, extracted_class, temp_path)
                    if result:
                        logger.info(f"使用 {decompiler} 反编译成功")
                        return result
                    else:
                        logger.warning(f"使用 {decompiler} 反编译失败，尝试回退方案")
                        return self._fallback_class_info(jar_path, class_name)
        
        except Exception as e:
            logger.error(f"反编译失败: {e}", exc_info=True)
            return self._fallback_class_info(jar_path, class_name)
    
    def _run_decompiler(self, decompiler: str, class_file: Path, temp_dir: Path) -> Optional[str]:
        """
        运行指定的反编译器
        
        参数:
            decompiler: 反编译器名称（javap、cfr、procyon、fernflower）
            class_file: 要反编译的类文件路径
            temp_dir: 临时工作目录路径
            
        返回:
            反编译后的源代码字符串，失败时返回 None
        """
        logger.debug(f"在 {class_file} 上运行反编译器 {decompiler}")
        
        try:
            if decompiler == 'javap':
                # Use javap for disassembly
                logger.debug("Using javap for disassembly")
                result = subprocess.run([
                    'javap', '-v', '-p', '-c', str(class_file)
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    return result.stdout
                else:
                    logger.error(f"javap failed: {result.stderr}")
            
            elif decompiler == 'cfr':
                # Use CFR decompiler
                output_dir = temp_dir / 'output'
                output_dir.mkdir()
                
                result = subprocess.run([
                    'java', '-jar', self.available_decompilers[decompiler],
                    str(class_file), '--outputdir', str(output_dir)
                ], capture_output=True, text=True, timeout=30)
                
                # Look for generated .java file
                java_files = list(output_dir.rglob('*.java'))
                if java_files:
                    with open(java_files[0], 'r', encoding='utf-8') as f:
                        return f.read()
            
            elif decompiler == 'procyon':
                # Use Procyon decompiler
                result = subprocess.run([
                    'java', '-jar', self.available_decompilers[decompiler],
                    str(class_file)
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    return result.stdout
            
            elif decompiler == 'fernflower':
                # Use Fernflower decompiler
                output_dir = temp_dir / 'output'
                output_dir.mkdir()
                
                result = subprocess.run([
                    'java', '-jar', self.available_decompilers[decompiler],
                    str(class_file), str(output_dir)
                ], capture_output=True, text=True, timeout=30)
                
                # Look for generated .java file
                java_files = list(output_dir.rglob('*.java'))
                if java_files:
                    with open(java_files[0], 'r', encoding='utf-8') as f:
                        return f.read()
        
        except Exception as e:
            logger.error(f"Decompiler {decompiler} failed: {e}", exc_info=True)
        
        return None
    
    def _fallback_class_info(self, jar_path: Path, class_name: str) -> str:
        """当反编译失败时的回退方案，返回基本类信息"""
        try:
            class_file_path = class_name.replace('.', '/') + '.class'
            
            with zipfile.ZipFile(jar_path, 'r') as jar:
                if class_file_path in jar.namelist():
                    class_data = jar.read(class_file_path)
                    
                    # Basic bytecode analysis
                    info = f"// 反编译不可用\n"
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
                    info += "    // 反编译需要外部工具\n"
                    info += "    // 请安装 CFR、Procyon 或 Fernflower 以获取完整的反编译结果\n"
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
