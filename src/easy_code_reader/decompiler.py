"""
Java 反编译器集成模块 - Easy Code Reader MCP 服务器

提供 Fernflower 和 CFR 反编译器集成。
根据 Java 版本自动选择合适的反编译器：
- Java < 21: 使用 CFR (兼容 Java 8+)
- Java >= 21: 使用 Fernflower
"""

import subprocess
import zipfile
import re
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class JavaDecompiler:
    """
    Java 字节码反编译器
    
    支持多个反编译器并根据 Java 版本自动选择：
    - CFR: 兼容 Java 8+，用于较旧的 JVM
    - Fernflower: IntelliJ IDEA 使用的反编译器，需要 Java 21+
    """
    
    def __init__(self):
        """
        初始化 Java 反编译器
        
        检测可用的反编译器和 Java 版本。
        """
        self.java_version = self._detect_java_version()
        self.fernflower_jar = self._detect_fernflower()
        self.cfr_jar = self._detect_cfr()
    
    def _detect_java_version(self) -> Optional[int]:
        """
        检测当前 Java 运行时版本
        
        返回:
            Java 主版本号（如 8, 11, 17, 21），如果检测失败则返回 None
        """
        try:
            result = subprocess.run(
                ['java', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            # java -version 输出到 stderr
            version_output = result.stderr + result.stdout
            
            # 尝试匹配版本号（例如 "1.8.0", "11.0.1", "17.0.2", "21.0.1"）
            match = re.search(r'version\s+"(\d+)\.(\d+)', version_output)
            if match:
                major = int(match.group(1))
                minor = int(match.group(2))
                # Java 1.8 -> 8, Java 11+ -> 直接使用主版本号
                java_version = minor if major == 1 else major
                logger.info(f"检测到 Java 版本: {java_version}")
                return java_version
            
            # 尝试另一种格式: openjdk version "21" 2023-09-19
            match = re.search(r'version\s+"(\d+)"', version_output)
            if match:
                java_version = int(match.group(1))
                logger.info(f"检测到 Java 版本: {java_version}")
                return java_version
            
        except FileNotFoundError:
            logger.error("未找到 Java 命令，请确保 Java 已安装并添加到 PATH")
        except subprocess.TimeoutExpired:
            logger.error("Java 版本检测超时")
        except Exception as e:
            logger.warning(f"检测 Java 版本失败: {e}")
        
        return None
    
    def _detect_fernflower(self) -> Optional[Path]:
        """
        检测 Fernflower 反编译器
        
        扫描系统以查找 Fernflower 反编译器。
        
        返回:
            Fernflower JAR 文件路径，如果未找到则返回 None
        """
        try:
            current_module_dir = Path(__file__).parent
            fernflower_path = current_module_dir / "decompilers" / "fernflower.jar"
            
            if fernflower_path.exists():
                logger.info(f"找到 Fernflower: {fernflower_path}")
                return fernflower_path
            else:
                logger.warning("未找到 Fernflower 反编译器")

        except Exception as e:
            logger.error(f"检测 Fernflower 失败: {e}")
        
        return None
    
    def _detect_cfr(self) -> Optional[Path]:
        """
        检测 CFR 反编译器
        
        CFR 是一个兼容 Java 8+ 的反编译器，适合在低版本 JVM 上运行。
        
        返回:
            CFR JAR 文件路径，如果未找到则返回 None
        """
        try:
            current_module_dir = Path(__file__).parent
            cfr_path = current_module_dir / "decompilers" / "cfr.jar"
            
            if cfr_path.exists():
                logger.info(f"找到 CFR: {cfr_path}")
                return cfr_path
            else:
                logger.warning("未找到 CFR 反编译器")
                
        except Exception as e:
            logger.error(f"检测 CFR 失败: {e}")
        
        return None
    
    def decompile_class(self, jar_path: Path, class_name: str, cache_jar_name: Optional[str] = None) -> Tuple[Optional[str], str]:
        """
        反编译 JAR 文件中的特定类
        
        从指定的 JAR 文件中提取并反编译特定的 Java 类。
        使用缓存机制：如果已经反编译过，直接从缓存读取。
        对于 SNAPSHOT 版本，使用带时间戳的缓存目录以支持版本更新。
        
        根据 Java 版本自动选择反编译器：
        - Java < 21: 使用 CFR (兼容 Java 8+)
        - Java >= 21: 使用 Fernflower
        
        参数:
            jar_path: 实际要反编译的 JAR 文件路径
            class_name: 要反编译的类的完全限定名（如 com.example.MyClass）
            cache_jar_name: 缓存使用的 jar 名称（可选），用于 SNAPSHOT 版本的缓存命名
            
        返回:
            (源代码字符串, 来源类型) 元组
            来源类型可能是: "decompiled_cache" (从缓存读取) 或 "decompiled" (新反编译)
            如果失败，源代码为基本类信息，来源类型为 "decompiled_cache" 或 "decompiled"
        """
        # 选择合适的反编译器
        decompiler_jar, decompiler_type = self._choose_decompiler()
        
        if not decompiler_jar:
            logger.error("没有可用的反编译器")
            return (self._fallback_class_info(jar_path, class_name), "decompiled")
        
        logger.info(f"反编译 {class_name} 使用 {decompiler_type} (Java {self.java_version or 'unknown'})")
        
        # 获取输出目录（jar 包所在目录的 easy-code-reader 子目录）
        jar_dir = jar_path.parent
        output_dir = jar_dir / "easy-code-reader"
        
        # 确定用于缓存命名的 jar 名称
        # 如果提供了 cache_jar_name，使用它；否则使用实际 jar 的名称
        cache_name = cache_jar_name if cache_jar_name else jar_path.name
        cache_name_without_ext = Path(cache_name).stem
        
        # 检查是否为 SNAPSHOT 版本的带时间戳 jar
        # 格式如: artifact-1.0.11-20251030.085053-1.jar
        is_snapshot = '-SNAPSHOT' in str(jar_dir) or self._is_timestamped_snapshot(cache_name_without_ext)
        
        # 如果是 SNAPSHOT，清理旧的缓存
        if is_snapshot:
            # 清理旧的 SNAPSHOT 缓存
            if output_dir.exists():
                self._cleanup_old_snapshot_cache(output_dir, cache_name_without_ext)
        
        # 定义反编译后的 JAR 路径和类文件在 JAR 中的路径
        # 反编译后的 jar 使用 cache_name 进行命名
        decompiled_jar = output_dir / cache_name
        java_file_path_in_jar = class_name.replace('.', '/') + '.java'
        
        # 检查缓存：查看是否已经反编译过
        # 反编译后的文件存储在一个与原 jar 同名的 jar 中
        if decompiled_jar.exists():
            try:
                with zipfile.ZipFile(decompiled_jar, 'r') as zf:
                    if java_file_path_in_jar in zf.namelist():
                        code = zf.read(java_file_path_in_jar).decode('utf-8')
                        logger.info(f"从缓存读取: {class_name}")
                        return (code, "decompiled_cache")
                    else:
                        logger.warning(f"缓存中未找到 {java_file_path_in_jar}，重新反编译")
            except Exception as e:
                logger.warning(f"读取缓存失败: {e}，重新反编译")
        
        # 创建输出目录（如果不存在）
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建输出目录失败 {output_dir}: {e}")
            return (self._fallback_class_info(jar_path, class_name), "decompiled")
        
        # 执行反编译
        if decompiler_type == 'cfr':
            return self._decompile_with_cfr(jar_path, class_name, output_dir, decompiled_jar, 
                                           java_file_path_in_jar, cache_name)
        else:  # fernflower
            return self._decompile_with_fernflower(jar_path, class_name, output_dir, decompiled_jar,
                                                   java_file_path_in_jar, cache_name)
    
    def _choose_decompiler(self) -> Tuple[Optional[Path], Optional[str]]:
        """
        根据 Java 版本选择合适的反编译器
        
        返回:
            (反编译器 JAR 路径, 反编译器类型) 元组
        """
        # 如果无法检测到 Java 版本，默认尝试使用 CFR（兼容性更好）
        if self.java_version is None:
            logger.warning("无法检测 Java 版本，默认使用 CFR")
            if self.cfr_jar:
                return (self.cfr_jar, 'cfr')
            elif self.fernflower_jar:
                logger.warning("CFR 不可用，回退到 Fernflower")
                return (self.fernflower_jar, 'fernflower')
            return (None, None)
        
        # Java < 21: 使用 CFR
        if self.java_version < 21:
            if self.cfr_jar:
                return (self.cfr_jar, 'cfr')
            else:
                logger.warning(f"Java {self.java_version} 建议使用 CFR，但未找到，回退到 Fernflower")
                if self.fernflower_jar:
                    return (self.fernflower_jar, 'fernflower')
        
        # Java >= 21: 使用 Fernflower
        else:
            if self.fernflower_jar:
                return (self.fernflower_jar, 'fernflower')
            else:
                logger.warning(f"Java {self.java_version} 推荐 Fernflower，但未找到，回退到 CFR")
                if self.cfr_jar:
                    return (self.cfr_jar, 'cfr')
        
        return (None, None)
    
    def _decompile_with_cfr(self, jar_path: Path, class_name: str, output_dir: Path,
                           decompiled_jar: Path, java_file_path_in_jar: str, 
                           cache_name: str) -> Tuple[Optional[str], str]:
        """
        使用 CFR 反编译 JAR 文件
        
        CFR 支持反编译整个 JAR 并输出到目录。
        """
        try:
            # CFR 输出到临时目录
            temp_output = output_dir / "cfr_temp"
            temp_output.mkdir(exist_ok=True)
            
            # CFR 命令: java -jar cfr.jar <jar-file> --outputdir <output-dir>
            result = subprocess.run([
                'java', '-jar', str(self.cfr_jar),
                str(jar_path),
                '--outputdir', str(temp_output)
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                stderr = result.stderr or ''
                # 检测 Java 版本不兼容错误
                if 'UnsupportedClassVersionError' in stderr or 'compiled by a more recent version' in stderr:
                    logger.error(
                        f"CFR 反编译失败: 需要更高版本的 JVM\n"
                        f"建议: 升级 Java 版本或使用 Fernflower"
                    )
                else:
                    logger.error(f"CFR 反编译失败: {stderr}")
                return (self._fallback_class_info(jar_path, class_name), "decompiled")
            
            # CFR 会将文件按包结构输出到目录中
            # 需要将它们打包成 jar
            import shutil
            
            # 将临时输出打包成 jar
            try:
                shutil.make_archive(
                    str(decompiled_jar.with_suffix('')),  # 不带 .jar 后缀
                    'zip',
                    temp_output
                )
                # shutil.make_archive 创建 .zip，重命名为 .jar
                zip_file = decompiled_jar.with_suffix('.zip')
                if zip_file.exists():
                    zip_file.rename(decompiled_jar)
            except Exception as e:
                logger.error(f"打包反编译结果失败: {e}")
                # 清理临时目录
                shutil.rmtree(temp_output, ignore_errors=True)
                return (self._fallback_class_info(jar_path, class_name), "decompiled")
            
            # 清理临时目录
            shutil.rmtree(temp_output, ignore_errors=True)
            
            # 从打包的 jar 中读取反编译后的类
            try:
                with zipfile.ZipFile(decompiled_jar, 'r') as zf:
                    if java_file_path_in_jar in zf.namelist():
                        code = zf.read(java_file_path_in_jar).decode('utf-8')
                        logger.info(f"反编译成功: {class_name}")
                        return (code, "decompiled")
                    else:
                        logger.error(f"反编译后未找到文件: {java_file_path_in_jar}")
                        return (self._fallback_class_info(jar_path, class_name), "decompiled")
            except zipfile.BadZipFile as e:
                logger.error(f"反编译后的 JAR 损坏: {e}")
                return (self._fallback_class_info(jar_path, class_name), "decompiled")
            except Exception as e:
                logger.error(f"读取反编译结果失败: {e}")
                return (self._fallback_class_info(jar_path, class_name), "decompiled")
                
        except Exception as e:
            logger.error(f"CFR 反编译失败: {e}", exc_info=True)
            return (self._fallback_class_info(jar_path, class_name), "decompiled")
    
    def _decompile_with_fernflower(self, jar_path: Path, class_name: str, output_dir: Path,
                                   decompiled_jar: Path, java_file_path_in_jar: str,
                                   cache_name: str) -> Tuple[Optional[str], str]:
        """
        使用 Fernflower 反编译 JAR 文件
        
        Fernflower 支持反编译整个 JAR，输出也是 JAR 格式。
        """
        try:
            result = subprocess.run([
                'java', '-jar', str(self.fernflower_jar),
                str(jar_path), str(output_dir)
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                stderr = result.stderr or ''
                # 检测 Java 版本不兼容错误
                if 'UnsupportedClassVersionError' in stderr or 'compiled by a more recent version' in stderr:
                    logger.error(
                        f"Fernflower 反编译失败: 需要 Java 21+\n"
                        f"建议: 升级到 Java 21 或使用 CFR"
                    )
                else:
                    logger.error(f"Fernflower 反编译失败: {stderr}")
                return (self._fallback_class_info(jar_path, class_name), "decompiled")
            
            # Fernflower 会将输出放在一个与原 jar 同名的 jar 中
            # 如果提供了 cache_jar_name，需要将生成的 jar 重命名
            fernflower_output_jar = output_dir / jar_path.name
            
            # 如果缓存名称与实际jar名称不同，需要重命名
            if cache_name and fernflower_output_jar.name != cache_name:
                if fernflower_output_jar.exists():
                    fernflower_output_jar.rename(decompiled_jar)
                else:
                    logger.error(f"Fernflower 未生成预期文件: {fernflower_output_jar}")
                    return (self._fallback_class_info(jar_path, class_name), "decompiled")
            elif not decompiled_jar.exists():
                logger.error(f"Fernflower 未生成预期文件: {decompiled_jar}")
                return (self._fallback_class_info(jar_path, class_name), "decompiled")
            
            try:
                with zipfile.ZipFile(decompiled_jar, 'r') as zf:
                    if java_file_path_in_jar in zf.namelist():
                        logger.info(f"反编译成功: {class_name}")
                        return (zf.read(java_file_path_in_jar).decode('utf-8'), "decompiled")
                    else:
                        logger.error(f"反编译后未找到文件: {java_file_path_in_jar}")
                        return (self._fallback_class_info(jar_path, class_name), "decompiled")
            except zipfile.BadZipFile as e:
                logger.error(f"反编译后的 JAR 损坏: {e}")
                return (self._fallback_class_info(jar_path, class_name), "decompiled")
            except Exception as e:
                logger.error(f"读取反编译结果失败: {e}")
                return (self._fallback_class_info(jar_path, class_name), "decompiled")
                
        except Exception as e:
            logger.error(f"Fernflower 反编译失败: {e}", exc_info=True)
            return (self._fallback_class_info(jar_path, class_name), "decompiled")
    
    def _is_timestamped_snapshot(self, jar_name: str) -> bool:
        """
        检查 jar 文件名是否为带时间戳的 SNAPSHOT 版本
        格式如: artifact-1.0.11-20251030.085053-1
        """
        import re
        # 匹配时间戳模式: YYYYMMDD.HHMMSS-BUILD_NUMBER
        pattern = r'-\d{8}\.\d{6}-\d+$'
        return bool(re.search(pattern, jar_name))
    
    def _cleanup_old_snapshot_cache(self, cache_base_dir: Path, current_jar_name: str):
        """
        清理旧的 SNAPSHOT 缓存 jar 文件
        
        参数:
            cache_base_dir: 缓存基础目录
            current_jar_name: 当前 jar 文件名（不含扩展名）
        """
        try:
            # 提取 artifact 名称和版本前缀
            import re
            match = re.match(r'^(.*?-\d+\.\d+\.\d+)-\d{8}\.\d{6}-\d+$', current_jar_name)
            if not match:
                return
            
            artifact_prefix = match.group(1)
            
            # 查找所有匹配该前缀的缓存 jar 文件
            for cached_file in cache_base_dir.iterdir():
                if cached_file.is_file() and cached_file.name.startswith(artifact_prefix) and cached_file.name.endswith('.jar'):
                    cached_name_without_ext = cached_file.stem
                    if cached_name_without_ext != current_jar_name:
                        logger.info(f"删除旧 SNAPSHOT 缓存: {cached_file.name}")
                        cached_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"清理 SNAPSHOT 缓存失败: {e}")
    
    
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
                    info += f"// 位置: {jar_path}\n"
                    info += f"// 当前 Java 版本: {self.java_version or '未知'}\n\n"
                    
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
                    
                    info += "\n// 反编译失败，可能的原因:\n"
                    if self.java_version and self.java_version < 21:
                        info += "// 1. 当前 Java 版本较低，建议升级到 Java 21+\n"
                        info += "// 2. 或者确保 CFR 反编译器可用 (兼容 Java 8+)\n"
                    else:
                        info += "// 1. 请确保 Fernflower 或 CFR 反编译器可用\n"
                        info += "// 2. 检查 Java 版本是否与反编译器兼容\n"
                    
                    info += f"\npublic class {class_name.split('.')[-1]} {{\n"
                    info += "    // 完整源代码需要反编译器\n"
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
