"""
Java 反编译器集成模块 - Easy Code Reader MCP 服务器

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

        except Exception as e:
            logger.debug(f"Fernflower 检测失败: {e}")
        
        return None
    
    def decompile_class(self, jar_path: Path, class_name: str, cache_jar_name: Optional[str] = None) -> Optional[str]:
        """
        反编译 JAR 文件中的特定类
        
        从指定的 JAR 文件中提取并反编译特定的 Java 类。
        使用缓存机制：如果已经反编译过，直接从缓存读取。
        对于 SNAPSHOT 版本，使用带时间戳的缓存目录以支持版本更新。
        
        参数:
            jar_path: 实际要反编译的 JAR 文件路径
            class_name: 要反编译的类的完全限定名（如 com.example.MyClass）
            cache_jar_name: 缓存使用的 jar 名称（可选），用于 SNAPSHOT 版本的缓存命名
            
        返回:
            反编译后的源代码字符串，如果失败则返回基本的类信息
        """
        logger.info(f"尝试从 {jar_path} 反编译类 {class_name}")
        
        # 检查是否有可用的反编译器
        if not self.fernflower_jar:
            logger.warning("Fernflower 反编译器不可用，使用回退方案")
            return self._fallback_class_info(jar_path, class_name)
        
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
            # 如果提供了 cache_jar_name，需要将生成的 jar 重命名
            fernflower_output_jar = output_dir / jar_path.name
            
            # 如果缓存名称与实际jar名称不同，需要重命名
            if cache_jar_name and fernflower_output_jar.name != cache_name:
                if fernflower_output_jar.exists():
                    logger.info(f"重命名反编译输出 {fernflower_output_jar.name} -> {cache_name}")
                    fernflower_output_jar.rename(decompiled_jar)
                else:
                    logger.error(f"Fernflower 未生成预期的 JAR 文件: {fernflower_output_jar}")
                    return self._fallback_class_info(jar_path, class_name)
            elif not decompiled_jar.exists():
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
            # 例如从 "athena-bugou-trade-export-1.0.11-20251030.085053-1" 
            # 提取 "athena-bugou-trade-export-1.0.11"
            import re
            match = re.match(r'^(.*?-\d+\.\d+\.\d+)-\d{8}\.\d{6}-\d+$', current_jar_name)
            if not match:
                # 不是时间戳格式，无需清理
                return
            
            artifact_prefix = match.group(1)
            logger.info(f"检查是否有旧的 SNAPSHOT 缓存需要清理，前缀: {artifact_prefix}")
            
            # 查找所有匹配该前缀的缓存 jar 文件
            for cached_file in cache_base_dir.iterdir():
                if cached_file.is_file() and cached_file.name.startswith(artifact_prefix) and cached_file.name.endswith('.jar'):
                    # 如果不是当前版本的缓存，删除它
                    cached_name_without_ext = cached_file.stem
                    if cached_name_without_ext != current_jar_name:
                        logger.info(f"删除旧的 SNAPSHOT 缓存 jar: {cached_file}")
                        cached_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"清理旧 SNAPSHOT 缓存时出错: {e}")
    
    
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
