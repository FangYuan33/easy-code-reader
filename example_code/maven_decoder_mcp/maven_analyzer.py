"""
增强型 Maven 依赖分析器 - MCP 服务器

为 MCP 服务器提供全面的 Maven 依赖分析、版本解析和传递依赖跟踪功能。
支持复杂的依赖关系分析，包括版本冲突检测、传递依赖解析等高级特性。

主要功能：
- 分析 Maven 项目的直接和传递依赖
- 解析 POM 文件中的属性和依赖管理
- 检测版本冲突和依赖问题
- 构建完整的依赖树结构
- 查找依赖的反向引用关系
- 版本信息查询和比较
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import re
from typing import Dict, List, Optional, Set, Tuple, Any
import logging
import requests
import json

logger = logging.getLogger(__name__)

class MavenDependencyAnalyzer:
    """
    高级 Maven 依赖分析器
    
    这个类提供了完整的 Maven 依赖分析功能，能够：
    - 解析 POM 文件并提取依赖信息
    - 处理 Maven 属性和变量替换
    - 分析传递依赖关系
    - 检测版本冲突
    - 构建依赖树结构
    - 查找特定构件的使用情况
    
    特性：
    - 支持多模块项目分析
    - 智能属性解析和继承
    - 传递依赖深度控制
    - 依赖排除规则处理
    - 内存缓存优化性能
    """
    
    def __init__(self, maven_home: Path):
        """
        初始化 Maven 依赖分析器
        
        参数:
            maven_home: Maven 本地仓库路径（通常是 ~/.m2/repository）
        """
        self.maven_home = maven_home
        self.cache = {}  # 简单的内存缓存
    
    def analyze_dependencies(self, group_id: str, artifact_id: str, version: str,
                           include_transitive: bool = False,
                           max_depth: int = 3) -> Dict[str, Any]:
        """
        分析 Maven 依赖关系
        
        解析指定构件的 POM 文件，提取其依赖信息，包括直接依赖、依赖管理、
        属性配置等。可选择性地解析传递依赖关系。
        
        参数:
            group_id: Maven 组 ID
            artifact_id: Maven 构件 ID
            version: 版本号
            include_transitive: 是否包含传递依赖
            max_depth: 传递依赖的最大深度
            
        返回:
            包含依赖分析结果的字典，包括：
            - artifact: 构件标识符
            - pom_path: POM 文件路径
            - direct_dependencies: 直接依赖列表
            - dependency_management: 依赖管理配置
            - properties: Maven 属性
            - parent: 父 POM 信息
            - modules: 子模块列表
            - transitive_dependencies: 传递依赖（如果启用）
            - conflicts: 版本冲突分析
        """
        pom_path = self._get_pom_path(group_id, artifact_id, version)
        
        if not pom_path or not pom_path.exists():
            return {"error": f"未找到 POM 文件: {group_id}:{artifact_id}:{version}"}
        
        try:
            tree = ET.parse(pom_path)
            root = tree.getroot()
            
            # 移除 XML 命名空间以便解析
            self._remove_namespace(root)
            
            result = {
                "artifact": f"{group_id}:{artifact_id}:{version}",
                "pom_path": str(pom_path),
                "direct_dependencies": [],
                "dependency_management": [],
                "properties": {},
                "parent": None,
                "modules": []
            }
            
            # Extract properties
            properties = root.find(".//properties")
            if properties is not None:
                for prop in properties:
                    result["properties"][prop.tag] = prop.text or ""
            
            # Extract parent information
            parent = root.find(".//parent")
            if parent is not None:
                parent_info = {
                    "groupId": self._get_text(parent, "groupId"),
                    "artifactId": self._get_text(parent, "artifactId"),
                    "version": self._get_text(parent, "version")
                }
                result["parent"] = parent_info
                
                # Merge parent properties if available
                parent_props = self._get_parent_properties(parent_info)
                result["properties"].update(parent_props)
            
            # Extract direct dependencies
            dependencies = root.find(".//dependencies")
            if dependencies is not None:
                for dep in dependencies.findall("dependency"):
                    dep_info = self._extract_dependency_info(dep, result["properties"])
                    if dep_info:
                        result["direct_dependencies"].append(dep_info)
            
            # Extract dependency management
            dep_mgmt = root.find(".//dependencyManagement/dependencies")
            if dep_mgmt is not None:
                for dep in dep_mgmt.findall("dependency"):
                    dep_info = self._extract_dependency_info(dep, result["properties"])
                    if dep_info:
                        result["dependency_management"].append(dep_info)
            
            # Extract modules (for multi-module projects)
            modules = root.find(".//modules")
            if modules is not None:
                for module in modules.findall("module"):
                    if module.text:
                        result["modules"].append(module.text)
            
            # Add transitive dependencies if requested
            if include_transitive:
                result["transitive_dependencies"] = self._resolve_transitive_dependencies(
                    result["direct_dependencies"], max_depth, set()
                )
            
            # Add conflict analysis
            result["conflicts"] = self._analyze_conflicts(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing dependencies: {e}")
            return {"error": str(e)}
    
    def _get_pom_path(self, group_id: str, artifact_id: str, version: str) -> Optional[Path]:
        """Get path to POM file"""
        group_path = group_id.replace('.', '/')
        pom_path = self.maven_home / group_path / artifact_id / version / f"{artifact_id}-{version}.pom"
        return pom_path if pom_path.exists() else None
    
    def _remove_namespace(self, elem):
        """Remove XML namespace from element and all children"""
        if elem.tag.startswith('{'):
            elem.tag = elem.tag.split('}')[1]
        for child in elem:
            self._remove_namespace(child)
    
    def _get_text(self, parent, tag_name: str) -> Optional[str]:
        """Get text content of a child element"""
        elem = parent.find(tag_name)
        return elem.text if elem is not None else None
    
    def _extract_dependency_info(self, dep_elem, properties: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Extract dependency information from XML element"""
        group_id = self._get_text(dep_elem, "groupId")
        artifact_id = self._get_text(dep_elem, "artifactId")
        version = self._get_text(dep_elem, "version")
        
        if not group_id or not artifact_id:
            return None
        
        # Resolve properties
        group_id = self._resolve_properties(group_id, properties)
        artifact_id = self._resolve_properties(artifact_id, properties)
        if version:
            version = self._resolve_properties(version, properties)
        
        dep_info = {
            "groupId": group_id,
            "artifactId": artifact_id,
            "version": version,
            "scope": self._get_text(dep_elem, "scope") or "compile",
            "type": self._get_text(dep_elem, "type") or "jar",
            "optional": self._get_text(dep_elem, "optional") == "true",
            "classifier": self._get_text(dep_elem, "classifier")
        }
        
        # Extract exclusions
        exclusions = dep_elem.find("exclusions")
        if exclusions is not None:
            dep_info["exclusions"] = []
            for exclusion in exclusions.findall("exclusion"):
                excl_group = self._get_text(exclusion, "groupId")
                excl_artifact = self._get_text(exclusion, "artifactId")
                if excl_group and excl_artifact:
                    dep_info["exclusions"].append({
                        "groupId": excl_group,
                        "artifactId": excl_artifact
                    })
        
        return dep_info
    
    def _resolve_properties(self, value: str, properties: Dict[str, str]) -> str:
        """Resolve Maven properties in a string"""
        if not value:
            return value
        
        # Replace ${property} patterns
        pattern = r'\$\{([^}]+)\}'
        
        def replace_prop(match):
            prop_name = match.group(1)
            return properties.get(prop_name, match.group(0))
        
        return re.sub(pattern, replace_prop, value)
    
    def _get_parent_properties(self, parent_info: Dict[str, str]) -> Dict[str, str]:
        """Get properties from parent POM"""
        try:
            parent_analysis = self.analyze_dependencies(
                parent_info["groupId"],
                parent_info["artifactId"],
                parent_info["version"],
                include_transitive=False
            )
            return parent_analysis.get("properties", {})
        except Exception:
            return {}
    
    def _resolve_transitive_dependencies(self, direct_deps: List[Dict[str, Any]],
                                       max_depth: int, visited: Set[str]) -> List[Dict[str, Any]]:
        """Resolve transitive dependencies recursively"""
        if max_depth <= 0:
            return []
        
        transitive = []
        
        for dep in direct_deps:
            dep_key = f"{dep['groupId']}:{dep['artifactId']}:{dep.get('version', 'unknown')}"
            
            if dep_key in visited or dep.get('optional', False):
                continue
            
            visited.add(dep_key)
            
            # Skip system scope dependencies
            if dep.get('scope') == 'system':
                continue
            
            try:
                # Analyze this dependency's dependencies
                sub_analysis = self.analyze_dependencies(
                    dep['groupId'],
                    dep['artifactId'],
                    dep.get('version', ''),
                    include_transitive=False
                )
                
                if "direct_dependencies" in sub_analysis:
                    for sub_dep in sub_analysis["direct_dependencies"]:
                        # Check if excluded
                        if not self._is_excluded(sub_dep, dep.get('exclusions', [])):
                            transitive.append({
                                **sub_dep,
                                "via": dep_key,
                                "depth": max_depth
                            })
                    
                    # Recurse for deeper levels
                    deeper_deps = self._resolve_transitive_dependencies(
                        sub_analysis["direct_dependencies"],
                        max_depth - 1,
                        visited
                    )
                    transitive.extend(deeper_deps)
            
            except Exception as e:
                logger.warning(f"Failed to resolve transitive deps for {dep_key}: {e}")
        
        return transitive
    
    def _is_excluded(self, dependency: Dict[str, Any], exclusions: List[Dict[str, str]]) -> bool:
        """Check if dependency is excluded"""
        for exclusion in exclusions:
            if (dependency['groupId'] == exclusion['groupId'] and
                dependency['artifactId'] == exclusion['artifactId']):
                return True
        return False
    
    def _analyze_conflicts(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze version conflicts in dependencies"""
        conflicts = []
        
        # Collect all dependencies by group:artifact
        dep_versions = {}
        
        # Add direct dependencies
        for dep in analysis.get("direct_dependencies", []):
            key = f"{dep['groupId']}:{dep['artifactId']}"
            if key not in dep_versions:
                dep_versions[key] = []
            dep_versions[key].append({
                "version": dep.get('version'),
                "source": "direct",
                "scope": dep.get('scope', 'compile')
            })
        
        # Add transitive dependencies
        for dep in analysis.get("transitive_dependencies", []):
            key = f"{dep['groupId']}:{dep['artifactId']}"
            if key not in dep_versions:
                dep_versions[key] = []
            dep_versions[key].append({
                "version": dep.get('version'),
                "source": "transitive",
                "via": dep.get('via'),
                "scope": dep.get('scope', 'compile')
            })
        
        # Find conflicts (multiple versions of same artifact)
        for artifact, versions in dep_versions.items():
            unique_versions = set(v['version'] for v in versions if v['version'])
            if len(unique_versions) > 1:
                conflicts.append({
                    "artifact": artifact,
                    "versions": list(unique_versions),
                    "sources": versions
                })
        
        return conflicts
    
    def find_dependency_tree(self, group_id: str, artifact_id: str, version: str) -> Dict[str, Any]:
        """Build a complete dependency tree"""
        tree = {
            "root": f"{group_id}:{artifact_id}:{version}",
            "dependencies": []
        }
        
        analysis = self.analyze_dependencies(group_id, artifact_id, version, include_transitive=True)
        
        if "error" in analysis:
            return analysis
        
        # Build tree structure
        tree["dependencies"] = self._build_tree_structure(
            analysis.get("direct_dependencies", []),
            analysis.get("transitive_dependencies", [])
        )
        
        return tree
    
    def _build_tree_structure(self, direct_deps: List[Dict[str, Any]], 
                            transitive_deps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build hierarchical tree structure"""
        tree = []
        
        # Create mapping of transitive deps by their parent
        transitive_by_parent = {}
        for dep in transitive_deps:
            parent = dep.get('via')
            if parent:
                if parent not in transitive_by_parent:
                    transitive_by_parent[parent] = []
                transitive_by_parent[parent].append(dep)
        
        # Build tree for direct dependencies
        for dep in direct_deps:
            dep_key = f"{dep['groupId']}:{dep['artifactId']}:{dep.get('version', 'unknown')}"
            node = {
                **dep,
                "children": transitive_by_parent.get(dep_key, [])
            }
            tree.append(node)
        
        return tree
    
    def get_version_info(self, group_id: str, artifact_id: str) -> Dict[str, Any]:
        """Get available versions for an artifact"""
        versions = []
        
        # Scan local repository
        group_path = group_id.replace('.', '/')
        artifact_path = self.maven_home / group_path / artifact_id
        
        if artifact_path.exists():
            for version_dir in artifact_path.iterdir():
                if version_dir.is_dir():
                    pom_file = version_dir / f"{artifact_id}-{version_dir.name}.pom"
                    jar_file = version_dir / f"{artifact_id}-{version_dir.name}.jar"
                    
                    version_info = {
                        "version": version_dir.name,
                        "has_pom": pom_file.exists(),
                        "has_jar": jar_file.exists(),
                        "path": str(version_dir)
                    }
                    
                    if pom_file.exists():
                        try:
                            stat = pom_file.stat()
                            version_info["pom_size"] = stat.st_size
                            version_info["last_modified"] = stat.st_mtime
                        except Exception:
                            pass
                    
                    versions.append(version_info)
        
        # Sort versions (simple string sort, could be improved with version comparison)
        versions.sort(key=lambda x: x["version"], reverse=True)
        
        return {
            "artifact": f"{group_id}:{artifact_id}",
            "versions": versions,
            "total_versions": len(versions)
        }
    
    def find_dependents(self, target_group: str, target_artifact: str, 
                       search_version: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find artifacts that depend on the target artifact"""
        dependents = []
        
        # This is a simplified implementation that scans local repository
        # A full implementation would need to scan all POMs
        for pom_path in self.maven_home.rglob("*.pom"):
            try:
                tree = ET.parse(pom_path)
                root = tree.getroot()
                self._remove_namespace(root)
                
                # Check dependencies
                dependencies = root.findall(".//dependency")
                for dep in dependencies:
                    group_id = self._get_text(dep, "groupId")
                    artifact_id = self._get_text(dep, "artifactId")
                    version = self._get_text(dep, "version")
                    
                    if (group_id == target_group and artifact_id == target_artifact):
                        if not search_version or version == search_version:
                            # Extract artifact info from POM path
                            artifact_info = self._extract_artifact_from_pom_path(pom_path)
                            if artifact_info:
                                dependents.append({
                                    **artifact_info,
                                    "depends_on_version": version,
                                    "dependency_scope": self._get_text(dep, "scope") or "compile"
                                })
            
            except Exception:
                continue  # Skip malformed POMs
        
        return dependents
    
    def _extract_artifact_from_pom_path(self, pom_path: Path) -> Optional[Dict[str, str]]:
        """Extract artifact coordinates from POM file path"""
        try:
            relative_path = pom_path.relative_to(self.maven_home)
            parts = relative_path.parts
            
            if len(parts) >= 3:
                version = parts[-2]
                artifact_id = parts[-3]
                group_id = '.'.join(parts[:-3])
                
                return {
                    "groupId": group_id,
                    "artifactId": artifact_id,
                    "version": version,
                    "pom_path": str(pom_path)
                }
        except Exception:
            pass
        
        return None
