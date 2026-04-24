#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Academic Paper Research Test Script

用于手动验证论文检索能力（扩展调试脚本）。

Usage:
    # 推荐：统一入口（已融合到主流程）
    metagpt "search papers about machine learning"

    # 兼容：直接运行扩展脚本
    python -m metagpt.ext.paper_research.test_paper_research "your research topic"
"""

import asyncio
import platform
import sys

from metagpt.roles.paper_researcher import PaperResearcher


async def test_paper_research(topic: str):
    """测试学术论文检索功能"""
    print(f"\n{'='*60}")
    print(f"Academic Paper Research Test")
    print(f"{'='*60}")
    print(f"Topic: {topic}\n")
    
    # 创建论文研究员角色
    researcher = PaperResearcher(language="zh")
    
    # 运行研究
    report = await researcher.run(topic, save_report=True)
    
    # 打印结果
    print(f"\n{'='*60}")
    print("Research Complete!")
    print(f"{'='*60}")
    print(f"Topic: {report.topic}")
    print(f"Papers Found: {len(report.papers)}")
    print(f"Generated at: {report.generated_at}")
    
    if report.suggestions:
        print(f"\nReading Suggestions:")
        for i, suggestion in enumerate(report.suggestions, 1):
            print(f"  {i}. {suggestion}")
    
    print(f"\nReport saved to: {researcher.get_research_path()}")
    
    return report


async def test_simple_search(topic: str):
    """测试简单搜索（快速测试）"""
    print(f"\n{'='*60}")
    print(f"Simple Paper Search Test")
    print(f"{'='*60}")
    
    researcher = PaperResearcher(language="zh")
    results = await researcher.simple_search(topic, max_results=5)
    
    print(results)
    
    return results


async def main():
    if len(sys.argv) < 2:
        print('Usage: python -m metagpt.ext.paper_research.test_paper_research "<research_topic>"')
        print('Example: python -m metagpt.ext.paper_research.test_paper_research "large language models in code generation"')
        print("\nOr use simple search mode:")
        print('Usage: python -m metagpt.ext.paper_research.test_paper_research --simple "<topic>"')
        print('Recommended: metagpt "<topic>"')
        return
    
    # 处理参数
    args = sys.argv[1:]
    simple_mode = "--simple" in args
    
    if simple_mode:
        args.remove("--simple")
    
    topic = " ".join(args)
    
    if simple_mode:
        await test_simple_search(topic)
    else:
        await test_paper_research(topic)


if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
