"""
Java 反编译器集成模块 - Maven Decoder MCP 服务器

为 Maven Decoder MCP 服务器提供各种 Java 反编译器和字节码分析工具的集成。
支持多种反编译器，包括 CFR、Procyon、Fernflower 和内置的 javap 工具。

主要功能：
- 自动检测系统中可用的反编译器
- 将 Java 字节码反编译为可读的源代码
- 提供字节码分析和结构信息
- 支持多种反编译器的回退机制
- JAR 文件结构分析
"""

import subprocess
import tempfile
import os
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class JavaDecompiler:
    """
    Java 字节码反编译器和分析器
    
    这个类提供了完整的 Java 字节码反编译功能，支持多种反编译器：
    - CFR: 现代化的 Java 反编译器，支持最新的 Java 特性
    - Procyon: 高质量的开源反编译器
    - Fernflower: IntelliJ IDEA 使用的反编译器
    - javap: JDK 内置的字节码反汇编工具
    
    特性：
    - 自动检测可用的反编译器
    - 智能选择最佳反编译器
    - 提供回退机制确保总能获取类信息
    - 支持 JAR 文件结构分析
    """
    
    def __init__(self):
        """
        初始化 Java 反编译器
        
        自动检测系统中可用的反编译器，并建立反编译器映射表。
        """
        self.available_decompilers = self._detect_decompilers()
    
    def _detect_decompilers(self) -> Dict[str, str]:
        """
        检测系统中可用的反编译器
        
        扫描系统以查找可用的 Java 反编译器，包括：
        - CFR 反编译器（cfr.jar）
        - Fernflower 反编译器（fernflower.jar）
        - Procyon 反编译器（procyon-decompiler.jar）
        - javap 工具（JDK 内置）
        
        返回:
            字典，键为反编译器名称，值为可执行文件路径
        """
        decompilers = {}
        
        # 检查 CFR（免费的 Java 反编译器）
        try:
            cfr_paths = ['cfr.jar', 'decompilers/cfr.jar']
            for cfr_path in cfr_paths:
                if Path(cfr_path).exists():
                    result = subprocess.run(['java', '-jar', cfr_path, '--help'],
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        decompilers['cfr'] = cfr_path
                        break
        except Exception:
            pass
        
        # 检查 Fernflower（IntelliJ 的反编译器）
        try:
            if Path('fernflower.jar').exists():
                result = subprocess.run(['java', '-jar', 'fernflower.jar'],
                                      capture_output=True, text=True, timeout=5)
                decompilers['fernflower'] = 'fernflower.jar'
        except Exception:
            pass
        
        # 检查 Procyon 反编译器
        try:
            procyon_paths = ['procyon-decompiler.jar', 'decompilers/procyon-decompiler.jar']
            for procyon_path in procyon_paths:
                if Path(procyon_path).exists():
                    result = subprocess.run(['java', '-jar', procyon_path, '--help'],
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        decompilers['procyon'] = procyon_path
                        break
        except Exception:
            pass
        
        # 检查 javap（JDK 内置工具）
        try:
            result = subprocess.run(['javap', '-help'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                decompilers['javap'] = 'javap'
        except Exception:
            pass
        
        return decompilers
    
    def decompile_class(self, jar_path: Path, class_name: str,
                       decompiler: Optional[str] = None) -> Optional[str]:
        """
        反编译 JAR 文件中的特定类
        
        从指定的 JAR 文件中提取并反编译特定的 Java 类，将字节码转换为可读的源代码。
        支持多种反编译器，如果指定的反编译器不可用，会自动选择可用的反编译器。
        
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
            logger.error(f"反编译失败: {e}")
            return self._fallback_class_info(jar_path, class_name)
    
    def _run_decompiler(self, decompiler: str, class_file: Path, temp_dir: Path) -> Optional[str]:
        """
        运行指定的反编译器
        
        根据指定的反编译器类型，使用相应的工具对类文件进行反编译。
        支持不同反编译器的特定参数和输出处理方式。
        
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
                
                logger.debug(f"javap return code: {result.returncode}")
                if result.stderr:
                    logger.warning(f"javap stderr: {result.stderr}")
                
                if result.returncode == 0:
                    return result.stdout
                else:
                    logger.error(f"javap failed with return code {result.returncode}: {result.stderr}")
            
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
            logger.error(f"Decompiler {decompiler} failed: {e}")
        
        return None
    
    def _fallback_class_info(self, jar_path: Path, class_name: str) -> str:
        """Fallback to basic class information when decompilation fails"""
        try:
            class_file_path = class_name.replace('.', '/') + '.class'
            
            with zipfile.ZipFile(jar_path, 'r') as jar:
                if class_file_path in jar.namelist():
                    class_data = jar.read(class_file_path)
                    
                    # Basic bytecode analysis
                    info = f"// Decompilation not available\n"
                    info += f"// Class: {class_name}\n"
                    info += f"// Size: {len(class_data)} bytes\n"
                    info += f"// Location: {jar_path}\n\n"
                    
                    # Try to extract some basic info from bytecode
                    magic = class_data[:4]
                    if magic == b'\xca\xfe\xba\xbe':
                        minor_version = int.from_bytes(class_data[4:6], 'big')
                        major_version = int.from_bytes(class_data[6:8], 'big')
                        info += f"// Java bytecode version: {major_version}.{minor_version}\n"
                        
                        # Map major version to Java version
                        java_version = self._map_bytecode_version(major_version)
                        if java_version:
                            info += f"// Compiled for Java: {java_version}\n"
                    
                    info += f"\npublic class {class_name.split('.')[-1]} {{\n"
                    info += "    // Decompilation requires external tools\n"
                    info += "    // Install CFR, Procyon, or Fernflower for full decompilation\n"
                    info += "}\n"
                    
                    return info
        
        except Exception as e:
            return f"// Error reading class file: {e}"
        
        return f"// Class not found: {class_name}"
    
    def _map_bytecode_version(self, major_version: int) -> Optional[str]:
        """Map bytecode major version to Java version"""
        version_map = {
            45: "1.1",
            46: "1.2",
            47: "1.3",
            48: "1.4",
            49: "5",
            50: "6",
            51: "7",
            52: "8",
            53: "9",
            54: "10",
            55: "11",
            56: "12",
            57: "13",
            58: "14",
            59: "15",
            60: "16",
            61: "17",
            62: "18",
            63: "19",
            64: "20",
            65: "21"
        }
        return version_map.get(major_version)
    
    def analyze_jar_structure(self, jar_path: Path) -> Dict[str, Any]:
        """Analyze the overall structure of a jar file"""
        analysis = {
            "jar_path": str(jar_path),
            "total_size": jar_path.stat().st_size,
            "packages": {},
            "class_count": 0,
            "resource_count": 0,
            "manifest": {},
            "services": [],
            "annotations": []
        }
        
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                entries = jar.namelist()
                
                # Analyze entries
                for entry in entries:
                    if entry.endswith('.class'):
                        analysis["class_count"] += 1
                        
                        # Extract package info
                        if '/' in entry:
                            package = '/'.join(entry.split('/')[:-1]).replace('/', '.')
                            if package not in analysis["packages"]:
                                analysis["packages"][package] = 0
                            analysis["packages"][package] += 1
                    
                    elif not entry.endswith('/'):
                        analysis["resource_count"] += 1
                
                # Read manifest
                if "META-INF/MANIFEST.MF" in entries:
                    manifest_content = jar.read("META-INF/MANIFEST.MF").decode('utf-8', errors='ignore')
                    analysis["manifest"] = self._parse_manifest(manifest_content)
                
                # Look for services
                service_entries = [e for e in entries if e.startswith("META-INF/services/")]
                for service_entry in service_entries:
                    service_name = service_entry.replace("META-INF/services/", "")
                    try:
                        service_content = jar.read(service_entry).decode('utf-8', errors='ignore')
                        analysis["services"].append({
                            "interface": service_name,
                            "implementations": [line.strip() for line in service_content.split('\n') if line.strip()]
                        })
                    except Exception:
                        pass
        
        except Exception as e:
            analysis["error"] = str(e)
        
        return analysis
    
    def _parse_manifest(self, manifest_content: str) -> Dict[str, str]:
        """Parse JAR manifest file"""
        manifest = {}
        current_key = None
        
        for line in manifest_content.split('\n'):
            line = line.rstrip('\r')
            
            if line.startswith(' ') and current_key:
                # Continuation line
                manifest[current_key] += line[1:]
            elif ':' in line:
                key, value = line.split(':', 1)
                current_key = key.strip()
                manifest[current_key] = value.strip()
        
        return manifest
