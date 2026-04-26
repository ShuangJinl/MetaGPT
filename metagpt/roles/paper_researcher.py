#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PaperResearcher - 学术论文研究员角色

功能：
- 接收研究主题，自动进行论文检索
- 支持多源搜索（Semantic Scholar, arXiv）
- 生成研究摘要和对比分析
- 提供阅读建议和优先级排序
- 输出完整的研究报告

@Time    : 2024
@Author  : MetaGPT Extension
@File    : paper_researcher.py
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from metagpt.actions import Action, UserRequirement
from metagpt.actions.paper_research import (
    GeneratePaperSummary,
    RankPapers,
    SearchAcademicPapers,
)
from metagpt.const import get_metagpt_package_root
from metagpt.logs import logger
from metagpt.roles.role import Role, RoleReactMode
from metagpt.tools.academic_search import get_academic_search_tool


class ResearchConfig(BaseModel):
    """研究配置"""
    max_papers: int = Field(default=15, description="最大搜索论文数")
    min_citations: int = Field(default=0, description="最小引用数")
    year_range: Optional[tuple[int, int]] = Field(default=None, description="年份范围")
    language: str = Field(default="en", description="输出语言: 'en' 或 'zh'")
    include_citations: bool = Field(default=True, description="是否分析引用关系")
    ranking_dimension: str = Field(default="recency", description="排序维度")
    top_k: int = Field(default=10, description="报告中展示的论文数")
    save_report: bool = Field(default=True, description="是否保存报告到文件")


class PaperResearchReport(BaseModel):
    """论文研究报告"""
    topic: str
    papers: list[dict] = Field(default_factory=list)
    summaries: dict[str, str] = Field(default_factory=dict)
    comparisons: str = ""
    suggestions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


# 研究报告保存路径
RESEARCH_PATH = get_metagpt_package_root() / "workspace" / "paper_research"


class PaperResearcher(Role):
    """
    学术论文研究员角色
    
    这个角色能够：
    1. 接收研究主题并搜索相关论文
    2. 获取论文详细信息和摘要
    3. 分析引用关系
    4. 生成排序报告和阅读建议
    5. 输出完整的研究报告
    
    Attributes:
        name: 角色名称
        profile: 角色描述
        goal: 角色目标
        constraints: 约束条件
        language: 输出语言
        research_config: 研究配置
    """
    
    name: str = Field(default="Dr. Smith")
    profile: str = Field(default="Academic Paper Researcher")
    goal: str = Field(default="Help users efficiently search, analyze, and summarize academic papers")
    constraints: str = Field(
        default="Ensure information sources are reliable and citations are accurate"
    )
    language: str = Field(default="en", description="Output language: 'en' or 'zh'")
    research_config: ResearchConfig = Field(
        default_factory=ResearchConfig,
        description="Research configuration"
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 初始化学术论文相关的 Actions
        self.set_actions([
            SearchAcademicPapers(),
            GeneratePaperSummary(),
            RankPapers(),
        ])
        
        # 设置反应模式：按顺序执行
        self._set_react_mode(RoleReactMode.BY_ORDER.value, len(self.actions))
        
        # 监听用户需求
        self._watch([UserRequirement])
        
        # 研究报告存储
        self._current_report: Optional[PaperResearchReport] = None
        self._searched_papers: list = []
        self._search_result: str = ""
        self._current_topic: str = ""
        
        # 学术搜索引擎
        self._academic_search = get_academic_search_tool()
    
    @property
    def watch_tags(self) -> set:
        """监听的消息标签"""
        return {UserRequirement}
    
    async def run(self, topic: str, save_report: bool = True) -> PaperResearchReport:
        """
        运行完整的研究流程
        
        Args:
            topic: 研究主题
            save_report: 是否保存报告
            
        Returns:
            PaperResearchReport: 研究报告
        """
        self._current_topic = topic
        
        logger.info(f"Starting research on: {topic}")
        
        # 初始化报告
        self._current_report = PaperResearchReport(topic=topic)
        
        try:
            # Step 1: 搜索论文
            search_result = await self._run_search(topic)
            self._search_result = search_result
            
            # 提取论文 ID
            paper_ids = self._extract_paper_ids(search_result)
            self._searched_papers = paper_ids
            
            if not paper_ids:
                logger.warning("No papers found for the topic")
                self._current_report.suggestions = ["No relevant papers found. Try a different search term."]
                return self._current_report
            
            # Step 2: 获取论文详情（简化处理，使用搜索结果中的数据）
            papers_info = await self._get_papers_info(paper_ids)
            self._current_report.papers = papers_info
            
            # Step 3: 生成摘要
            if self.research_config.top_k:
                top_papers = paper_ids[:self.research_config.top_k]
                summaries = await self._generate_summaries(top_papers)
                self._current_report.summaries = summaries
            
            # Step 4: 排序并生成最终报告
            final_report = await self._rank_papers(topic, papers_info)
            
            # Step 5: 保存报告
            if save_report and self.research_config.save_report:
                self._save_report_to_file(final_report)
            
            return self._current_report
            
        except Exception as e:
            logger.error(f"Error during research: {e}")
            self._current_report.suggestions = [f"Error: {str(e)}"]
            return self._current_report
    
    async def _run_search(self, topic: str) -> str:
        """执行论文搜索"""
        logger.info(f"Step 1: Searching papers for '{topic}'")
        
        config = self.research_config
        
        self._search_action = SearchAcademicPapers(
            max_results=config.max_papers,
            min_citations=config.min_citations,
            year_range=config.year_range
        )
        self._search_action.set_context(self.context)
        self._search_action.set_llm(self.llm)
        
        result = await self._search_action.run(
            topic=topic,
            sources=["semantic_scholar", "arxiv"],
            language=config.language
        )
        
        return result
    
    def _extract_paper_ids(self, search_result: str) -> list[str]:
        """从搜索结果中提取论文 ID"""
        import re
        
        # 匹配格式: - **Paper ID**: xxxxxxxx
        paper_ids = re.findall(r'\*\*Paper ID\*\*: (.+)', search_result)
        
        # 去除空格
        paper_ids = [pid.strip() for pid in paper_ids if pid.strip()]
        
        logger.info(f"Extracted {len(paper_ids)} paper IDs")
        return paper_ids
    
    async def _get_papers_info(self, paper_ids: list[str]) -> list[dict]:
        """获取论文信息"""
        logger.info(f"Step 2: Fetching details for {len(paper_ids)} papers")
        
        # 直接使用搜索结果中的论文数据，避免额外 API 调用
        papers = self._search_action.get_last_search_papers()
        paper_map = {p.paper_id: p for p in papers}
        
        papers_info = []
        for pid in paper_ids:
            paper = paper_map.get(pid)
            if paper:
                papers_info.append({
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "authors": paper.authors[:5] if paper.authors else [],
                    "year": paper.year,
                    "venue": paper.venue or "arXiv",
                    "citation_count": paper.citation_count,
                    "abstract": paper.abstract[:300] if paper.abstract else "",
                    "url": paper.url,
                    "pdf_url": paper.open_access_pdf,
                })
            else:
                logger.warning(f"Paper {pid} not found in search results")
        
        return papers_info
    
    async def _generate_summaries(self, paper_ids: list[str]) -> dict[str, str]:
        """生成论文摘要"""
        logger.info(f"Step 3: Generating summaries for {len(paper_ids)} papers")
        
        # 获取搜索结果中的论文数据
        papers = self._search_action.get_last_search_papers()
        paper_map = {p.paper_id: p for p in papers}
        
        summaries = {}
        summary_action = GeneratePaperSummary()
        summary_action.set_context(self.context)
        summary_action.set_llm(self.llm)
        
        for pid in paper_ids[:5]:  # 限制摘要数量以节省成本
            try:
                paper_data = paper_map.get(pid)
                summary = await summary_action.run(
                    paper_id=pid,
                    source="arxiv",
                    language=self.research_config.language,
                    paper_data=paper_data
                )
                summaries[pid] = summary
            except Exception as e:
                logger.warning(f"Failed to generate summary for {pid}: {e}")
                summaries[pid] = f"Summary generation failed: {str(e)}"
        
        return summaries
    
    async def _rank_papers(self, topic: str, papers_info: list[dict]) -> str:
        """排序论文并生成最终报告"""
        logger.info("Step 4: Ranking papers and generating report")
        
        # 将字典转换为 Paper 对象（简化处理）
        from metagpt.tools.academic_search import Paper
        
        papers = []
        for info in papers_info:
            paper = Paper(
                paper_id=info["paper_id"],
                title=info["title"],
                authors=info["authors"],
                year=info["year"],
                venue=info["venue"],
                citation_count=info["citation_count"],
                abstract=info["abstract"],
                url=info["url"],
            )
            papers.append(paper)
        
        # 排序
        rank_action = RankPapers(
            default_dimension=self.research_config.ranking_dimension
        )
        rank_action.set_context(self.context)
        rank_action.set_llm(self.llm)
        
        ranked_report = await rank_action.run(
            papers=papers,
            topic=topic,
            language=self.research_config.language,
            top_k=self.research_config.top_k
        )
        
        # 生成总结
        self._current_report.suggestions = self._generate_recommendations(papers_info)
        
        return ranked_report
    
    def _generate_recommendations(self, papers_info: list[dict]) -> list[str]:
        """生成阅读建议"""
        suggestions = []
        
        if not papers_info:
            return ["No papers found. Please try a different search term."]
        
        # 最新论文
        recent = sorted(papers_info, key=lambda x: x.get("year", 0), reverse=True)[:3]
        if recent:
            suggestions.append(
                f"Recent papers ({len(recent)} papers from recent years)"
            )
        
        # 开源论文
        open_access = [p for p in papers_info if p.get("pdf_url")]
        if open_access:
            suggestions.append(
                f"{len(open_access)} papers have free PDF access"
            )
        
        return suggestions
    
    def _save_report_to_file(self, content: str):
        """保存报告到文件"""
        try:
            RESEARCH_PATH.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = "".join(c for c in self._current_topic[:30] if c.isalnum() or c in (' ', '-', '_'))
            safe_topic = safe_topic.replace(' ', '_')
            
            filename = RESEARCH_PATH / f"research_{safe_topic}_{timestamp}.md"
            
            # 完整报告内容
            full_content = f"""# Academic Paper Research Report
Generated by PaperResearcher

**Topic**: {self._current_topic}
**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Papers Found**: {len(self._searched_papers)}

---

"""
            full_content += content
            
            # 添加建议部分
            full_content += "\n\n---\n\n## Reading Suggestions\n\n"
            for i, suggestion in enumerate(self._current_report.suggestions, 1):
                full_content += f"{i}. {suggestion}\n"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            logger.info(f"Report saved to: {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
    
    async def simple_search(self, topic: str, max_results: int = 10) -> str:
        """
        简单搜索（不执行完整流程）
        
        Args:
            topic: 搜索主题
            max_results: 最大结果数
            
        Returns:
            str: 搜索结果
        """
        search_action = SearchAcademicPapers(max_results=max_results)
        search_action.set_context(self.context)
        search_action.set_llm(self.llm)
        
        return await search_action.run(topic=topic, language=self.language)
    
    def get_research_path(self) -> Path:
        """获取研究报告保存路径"""
        return RESEARCH_PATH


__all__ = [
    "PaperResearcher",
    "PaperResearchReport",
    "ResearchConfig",
]
