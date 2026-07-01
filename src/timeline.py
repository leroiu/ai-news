"""
AI Intelligence Platform — Timeline (向后兼容 re-export)

此模块已拆分为 timeline_data + timeline_renderer。
从本路径的 import 保持不变。
"""
from src.frontend.timeline_renderer import generate_timeline

__all__ = ["generate_timeline"]
