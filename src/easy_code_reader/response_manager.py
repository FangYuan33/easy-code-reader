"""
响应管理器 - 管理大型响应的分页和摘要功能

该类负责处理可能很大的响应数据，通过分页和内容摘要来确保
响应大小在合理范围内，避免超出 MCP 协议的限制。
"""

import json
import re
from typing import Any, Dict, Optional


class ResponseManager:
    """
    响应管理器 - 管理大型响应的分页和摘要功能
    
    主要功能：
    - 自动分页处理大量数据
    - 智能摘要长文本内容
    - 响应大小控制和优化
    """
    
    def __init__(self, max_response_size: Optional[int] = None, 
                 max_items_per_page: Optional[int] = None,
                 max_text_length: Optional[int] = None, 
                 max_lines: Optional[int] = None):
        """
        初始化响应管理器
        
        参数:
            max_response_size: 最大响应大小（字节），默认 50000
            max_items_per_page: 每页最大项目数，默认 20
            max_text_length: 最大文本长度，默认 10000
            max_lines: 最大行数，默认 500
        """
        from .config import Config
        
        self.max_response_size = max_response_size or Config.MAX_RESPONSE_SIZE
        self.max_items_per_page = max_items_per_page or Config.MAX_ITEMS_PER_PAGE
        self.max_text_length = max_text_length or Config.MAX_TEXT_LENGTH
        self.max_lines = max_lines or Config.MAX_LINES
    
    def summarize_large_text(self, text: str, max_length: Optional[int] = None) -> str:
        """
        摘要大型文本内容
        
        对于过长的文本（特别是 Java 源代码），生成智能摘要以保留关键信息。
        优先保留包声明、导入语句、类声明、方法签名和结束部分。
        
        参数:
            text: 要摘要的文本内容
            max_length: 最大长度限制，默认使用配置值
            
        返回:
            摘要后的文本，如果原文本不超长则返回原文本
        """
        if max_length is None:
            max_length = self.max_text_length
            
        if len(text) <= max_length:
            return text
        
        # 对于 Java 代码，尝试保留重要部分
        lines = text.split('\n')
        if len(lines) <= self.max_lines:
            return text
        
        # 保留前20行（通常是包声明、导入、类声明）
        # 保留后10行（通常是结束大括号）
        # 保留中间的方法签名
        summary_lines = []
        
        # 添加摘要头部信息
        summary_lines.append("// 摘要: 大型类内容（显示关键部分）")
        summary_lines.append(f"// 总行数: {len(lines)}")
        summary_lines.append("// 显示内容: 包声明/导入、方法签名、结束大括号")
        summary_lines.append("")
        
        # 添加前20行
        summary_lines.extend(lines[:20])
        
        # 查找方法签名（包含 public/private/protected 的行）
        method_lines = []
        for i, line in enumerate(lines[20:-10]):
            stripped = line.strip()
            if (re.match(r'^\s*(public|private|protected|static|final)\s+', stripped) and
                '(' in stripped and ')' in stripped and
                not stripped.startswith('//') and not stripped.startswith('/*')):
                method_lines.append((i + 20, line))
        
        # 添加一些方法签名（最多10个）
        if method_lines:
            summary_lines.append("")
            summary_lines.append("// ... 关键方法签名 ...")
            for idx, line in method_lines[:10]:
                summary_lines.append(f"// 第 {idx + 1} 行: {line.strip()}")
        
        # 添加结束大括号
        summary_lines.append("")
        summary_lines.append("// ... 结束大括号 ...")
        summary_lines.extend(lines[-10:])
        
        summary_lines.append("")
        summary_lines.append(f"// 使用 max_lines=0 参数获取完整内容")
        
        return '\n'.join(summary_lines)
    
    def should_summarize(self, text: str) -> bool:
        """
        检查文本是否应该摘要
        
        参数:
            text: 要检查的文本
            
        返回:
            如果文本长度超过限制则返回 True
        """
        return len(text) > self.max_text_length
