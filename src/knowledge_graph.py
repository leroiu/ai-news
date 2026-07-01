"""
AI News - 知识图谱生成器 (向后兼容 re-export)

此模块已拆分为 kg_data / kg_mermaid / kg_d3。
从本路径的 import 保持不变，所有符号透明转发。
"""
from src.engine.kg_data import build_graph, TYPE_COLORS, EDGE_STYLES
from src.engine.kg_mermaid import to_mermaid, generate_mermaid_report
from src.frontend.kg_d3 import generate_html

__all__ = [
    "build_graph",
    "generate_mermaid_report",
    "generate_html",
    "to_mermaid",
    "TYPE_COLORS",
    "EDGE_STYLES",
]
