#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Paper Research Example - 学术论文研究使用示例

这个脚本展示了如何使用 PaperResearcher 角色进行学术论文研究。

@Time    : 2024
@Author  : MetaGPT Extension
"""

import asyncio
import platform

from metagpt.roles.paper_researcher import PaperResearcher, ResearchConfig


async def example_basic_search():
    """基本搜索示例"""
    print("\n" + "="*60)
    print("Example 1: Basic Paper Search")
    print("="*60)
    
    # 创建研究员
    researcher = PaperResearcher(language="zh")
    
    # 执行简单搜索
    topic = "large language model code generation"
    results = await researcher.simple_search(topic, max_results=5)
    
    print(results)


async def example_full_research():
    """完整研究流程示例"""
    print("\n" + "="*60)
    print("Example 2: Full Research Workflow")
    print("="*60)
    
    # 自定义研究配置
    config = ResearchConfig(
        max_papers=10,
        min_citations=10,
        year_range=(2020, 2024),
        language="zh",
        ranking_dimension="recency",
        top_k=5,
    )
    
    researcher = PaperResearcher(language="zh", research_config=config)
    
    topic = "transformer architecture"
    report = await researcher.run(topic, save_report=True)
    
    print(f"\n研究主题: {report.topic}")
    print(f"找到论文数: {len(report.papers)}")
    print(f"生成时间: {report.generated_at}")


async def example_paper_details():
    """获取单篇论文详情示例"""
    print("\n" + "="*60)
    print("Example 3: Get Paper Details")
    print("="*60)
    
    researcher = PaperResearcher(language="zh")
    
    # 使用一个已知的 paper ID (这是一个示例 ID)
    paper_id = "649def34fd0c6884072b5c1a7a47e4c3f1e23f3d"  # 替换为实际的 paper ID
    
    details = await researcher.get_paper_full_details(paper_id)
    
    print(details)


async def example_custom_config():
    """自定义配置示例"""
    print("\n" + "="*60)
    print("Example 4: Custom Configuration")
    print("="*60)
    
    # 配置：只搜索高引用论文
    config = ResearchConfig(
        max_papers=20,
        min_citations=100,  # 只搜索引用数 > 100 的论文
        year_range=(2019, 2024),
        language="en",
        ranking_dimension="citations",
    )
    
    researcher = PaperResearcher(
        name="ResearchBot",
        profile="Paper Researcher",
        language="en",
        research_config=config
    )
    
    topic = "neural network optimization"
    report = await researcher.run(topic, save_report=True)
    
    print(f"\nTopic: {report.topic}")
    print(f"High-impact papers found: {len(report.papers)}")


async def main():
    print("\n" + "#"*60)
    print("# Academic Paper Research - Usage Examples")
    print("#"*60)
    
    # 运行基本搜索示例
    await example_basic_search()
    
    # 运行完整研究流程示例
    await example_full_research()
    
    # 可以取消注释来测试更多示例
    # await example_paper_details()
    # await example_custom_config()
    
    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60)
    print("\n查看 workspace/paper_research/ 目录获取生成的研究报告")


if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
