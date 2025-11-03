"""
Maven Decoder MCP Server

An MCP (Model Context Protocol) server for reading and decompiling Maven .m2 jar files.
Provides comprehensive Java project analysis including:
- Jar file exploration and analysis
- Java class decompilation (CFR, Procyon, javap)
- Maven dependency resolution
- Source code extraction
- Class structure analysis

Usage:
    from maven_decoder_mcp import MavenDecoderServer
    
    # Create and run server
    server = MavenDecoderServer()
    server.run()

Command line:
    maven-decoder-mcp
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your-email@example.com"

from .maven_decoder_server import MavenDecoderServer
from .decompiler import JavaDecompiler
from .maven_analyzer import MavenDependencyAnalyzer

__all__ = [
    "MavenDecoderServer",
    "JavaDecompiler", 
    "MavenDependencyAnalyzer",
]
