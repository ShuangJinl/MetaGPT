#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SearchAcademicPapers - 学术论文搜索 Action

功能：
- 根据研究主题/关键词搜索学术论文
- 支持 Semantic Scholar 和 arXiv 双源搜索
- 支持过滤条件：时间范围、引用数阈值
- 返回结构化论文列表

@Time    : 2024
@Author  : MetaGPT Extension
@File    : search_papers.py
"""

from typing import Optional

from pydantic import Field, model_validator

from metagpt.actions import Action
from metagpt.logs import logger
from metagpt.schema import Message
from metagpt.tools.academic_search import (
    AcademicSearchTool,
    Paper,
    get_academic_search_tool,
)


SEARCH_PAPERS_SYSTEM = """You are an academic paper search assistant. Your task is to help users find relevant academic papers based on their research topics."""


SEARCH_PAPERS_PROMPT = """
## Research Topic
{topic}

## Search Results
{search_results}

## Requirements
Based on the search results above, please:
1. Filter out papers that are not directly related to the research topic
2. Organize the remaining papers in a clear format with:
   - Paper title
   - Authors (first 3 authors + "et al." if more)
   - Year
   - Venue/Publication
   - Citation count
   - A brief relevance comment (1-2 sentences)
3. Provide the final filtered list with paper IDs for further investigation

## Output Format
Return a structured list of relevant papers in the following format:
{papers_format}
"""


PAPER_LIST_FORMAT = """
### Paper 1
- Paper ID: [ID]
- Title: [Title]
- Authors: [Authors]
- Year: [Year]
- Venue: [Venue]
- Citations: [Count]
- Relevance: [Brief comment]

### Paper 2
...
"""


class SearchAcademicPapers(Action):
    """
    学术论文搜索 Action
    
    Attributes:
        name: Action 名称
        desc: Action 描述
        academic_search: 学术搜索引擎实例
        max_results: 最大搜索结果数
        year_range: 发表年份范围
        min_citations: 最小引用数阈值
    """
    
    name: str = "SearchAcademicPapers"
    desc: str = "Search for academic papers based on research topic"
    academic_search: Optional[AcademicSearchTool] = None
    max_results: int = Field(default=10, description="Maximum number of search results")
    year_range: Optional[tuple[int, int]] = Field(default=None, description="Publication year range (min_year, max_year)")
    min_citations: int = Field(default=0, description="Minimum citation count")
    
    @model_validator(mode="after")
    def validate_academic_search(self):
        """初始化学术搜索引擎"""
        if self.academic_search is None:
            self.academic_search = get_academic_search_tool()
        return self
    
    async def run(
        self,
        topic: str,
        sources: Optional[list[str]] = None,
        language: str = "en"
    ) -> str:
        """
        执行论文搜索
        
        Args:
            topic: 研究主题/搜索关键词
            sources: 搜索来源列表 ["semantic_scholar", "arxiv"]，默认两者都搜索
            language: 输出语言，"en" 或 "zh"
            
        Returns:
            str: 格式化的搜索结果
        """
        if sources is None:
            sources = ["arxiv"]
        
        logger.info(f"Searching for papers on topic: {topic}")
        
        try:
            # 执行搜索
            result = await self.academic_search.search_multiple(
                query=topic,
                max_results=self.max_results,
                sources=sources
            )
            
            papers = result.papers
            
            # 应用过滤条件
            if self.year_range:
                papers = [p for p in papers if self.year_range[0] <= p.year <= self.year_range[1]]
            
            if self.min_citations > 0:
                papers = [p for p in papers if p.citation_count >= self.min_citations]
            
            # 保存论文数据供其他组件使用
            self._last_search_papers = papers
            
            logger.info(f"Found {len(papers)} papers after filtering")
            
            # 格式化结果
            formatted_results = self._format_papers(papers, topic, language)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching papers: {e}")
            return f"Error searching papers: {str(e)}"
    
    def get_last_search_papers(self) -> list:
        """获取最后一次搜索的论文列表"""
        return getattr(self, '_last_search_papers', [])
    
    def _format_papers(self, papers: list[Paper], topic: str, language: str = "en") -> str:
        """格式化论文列表"""
        if not papers:
            if language == "zh":
                return f"未找到与「{topic}」相关的新论文。"
            return f"No papers found related to '{topic}'."
        
        lines = []
        if language == "zh":
            lines.append(f"## 与「{topic}」相关的新论文（共 {len(papers)} 篇）\n")
        else:
            lines.append(f"## Relevant Papers for '{topic}' ({len(papers)} found)\n")
        
        for idx, paper in enumerate(papers, 1):
            # 格式化作者
            if paper.authors:
                if len(paper.authors) > 3:
                    authors_str = ", ".join(paper.authors[:3]) + " et al."
                else:
                    authors_str = ", ".join(paper.authors)
            else:
                authors_str = "Unknown"
            
            # 格式化关键词
            keywords_str = ", ".join(paper.keywords[:5]) if paper.keywords else "None"
            
            lines.append(f"### {idx}. {paper.title}")
            lines.append(f"- **Paper ID**: {paper.paper_id}")
            lines.append(f"- **Authors**: {authors_str}")
            lines.append(f"- **Year**: {paper.year}")
            lines.append(f"- **Venue**: {paper.venue or 'N/A'}")
            if paper.keywords:
                lines.append(f"- **Keywords**: {keywords_str}")
            if paper.open_access_pdf:
                lines.append(f"- **PDF**: [Link]({paper.open_access_pdf})")
            if paper.url and not paper.open_access_pdf:
                lines.append(f"- **URL**: [Link]({paper.url})")
            lines.append("")
        
        return "\n".join(lines)
    
    async def search_by_author(
        self,
        author_name: str,
        max_results: int = 10
    ) -> str:
        """
        根据作者搜索论文
        
        Args:
            author_name: 作者姓名
            max_results: 最大结果数
            
        Returns:
            str: 搜索结果
        """
        logger.info(f"Searching papers by author: {author_name}")
        
        query = f"author:{author_name}"
        result = await self.academic_search.search_semantic_scholar(
            query=query,
            max_results=max_results
        )
        
        return self._format_papers(result.papers, f"papers by {author_name}")
    
    async def search_by_doi(self, doi: str) -> str:
        """
        根据 DOI 搜索论文
        
        Args:
            doi: 论文 DOI
            
        Returns:
            str: 论文详情
        """
        logger.info(f"Searching paper by DOI: {doi}")
        
        # 在 Semantic Scholar 中搜索
        result = await self.academic_search.search_semantic_scholar(
            query=f"DOI:{doi}",
            max_results=1
        )
        
        if result.papers:
            paper = result.papers[0]
            return self._format_papers([paper], f"paper with DOI {doi}")
        
        return f"Paper with DOI '{doi}' not found."
    
    def get_paper_ids_from_results(self, results: str) -> list[str]:
        """
        从搜索结果中提取论文 ID
        
        Args:
            results: 格式化后的搜索结果
            
        Returns:
            list[str]: 论文 ID 列表
        """
        import re
        paper_ids = re.findall(r'\*\*Paper ID\*\*: (.+)', results)
        return [pid.strip() for pid in paper_ids]
