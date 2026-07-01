"""Research Assistant 兼容入口：后端研究引擎与前端页面生成器。"""
import json

from src.engine.research_engine import generate_research_report
from src.frontend.research_page import generate_research_page

__all__ = ["generate_research_report", "generate_research_page"]


def main() -> int:
    """CLI：测试研究功能。"""
    from src.engine.utils import setup_logging

    setup_logging("INFO")
    topic = input("研究主题: ").strip()
    if not topic:
        print("请输入研究主题")
        return 1
    result = generate_research_report(topic)
    if "error" in result:
        print(f"错误: {result['error']}")
        return 1
    print(json.dumps(result["report"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
