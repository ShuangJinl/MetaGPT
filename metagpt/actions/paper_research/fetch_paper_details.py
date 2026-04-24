#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FetchPaperDetails - 获取学术论文详细信息 Action

功能：
- 根据论文 ID 获取完整论文信息
- 获取论文的参考文献和被引列表
- 提取论文元数据（DOI、arXiv ID 等）

@Time    : 2024
@Author  : MetaGPT Extension
@File    : fetch_paper_details.py
"""

from typing import Optional

from pydantic import Field, model_validator

from metagpt.actions import Action
from metagpt.logs import logger
from metagpt.tools.academic_search import (
    AcademicSearchTool,
    Paper,
    get_academic_search_tool,
)


FETCH_DETAILS_PROMPT = """
## Paper Information

{formatted_info}

## References ({ref_count})
{references}

## Citations ({cit_count})
{citations}

## Requirements
Please analyze the paper information above and provide:
1. A comprehensive overview of the paper's contributions
2. The research methodology used
3. Key findings and results
4. Potential applications or implications
5. Any notable limitations mentioned

## Output Language
Output in: {language}
"""


class FetchPaperDetails(Action):
    """
    获取论文详细信息 Action
    
    Attributes:
        name: Action 名称
        desc: Action 描述
        academic_search: 学术搜索引擎实例
    """
    
    name: str = "FetchPaperDetails"
    desc: str = "Fetch detailed information about a specific paper"
    academic_search: Optional[AcademicSearchTool] = None
    max_references: int = Field(default=10, description="Maximum number of references to fetch")
    max_citations: int = Field(default=10, description="Maximum number of citations to fetch")
    
    @model_validator(mode="after")
    def validate_academic_search(self):
        """初始化学术搜索引擎"""
        if self.academic_search is None:
            self.academic_search = get_academic_search_tool()
        return self
    
    async def run(
        self,
        paper_id: str,
        source: str = "semantic_scholar",
        include_references: bool = True,
        include_citations: bool = True,
        language: str = "en"
    ) -> str:
        """
        获取论文详细信息
        
        Args:
            paper_id: 论文 ID
            source: 数据来源 ("semantic_scholar")
            include_references: 是否包含参考文献
            include_citations: 是否包含被引列表
            language: 输出语言
            
        Returns:
            str: 格式化的论文详细信息
        """
        logger.info(f"Fetching details for paper: {paper_id}")
        
        try:
            # 获取论文基本信息
            paper = await self.academic_search.get_paper_by_id(paper_id, source)
            
            if paper is None:
                return f"Paper with ID '{paper_id}' not found."
            
            # 格式化基本信息
            formatted_info = self._format_paper_info(paper, language)
            
            # 获取参考文献
            references = ""
            if include_references and paper.references:
                ref_papers = await self.academic_search.get_paper_citations(paper_id)
                references = self._format_paper_list(ref_papers[:self.max_references])
            
            # 获取被引列表
            citations = ""
            if include_citations:
                cit_papers = await self.academic_search.get_paper_cited_by(paper_id)
                citations = self._format_paper_list(cit_papers[:self.max_citations])
            
            # 构建完整信息
            result = [formatted_info]
            
            if references:
                result.append(f"\n## References ({len(paper.references)})")
                result.append(references)
            
            if citations:
                result.append(f"\n## Cited By ({len(paper.cited_by)})")
                result.append(citations)
            
            return "\n".join(result)
            
        except Exception as e:
            logger.error(f"Error fetching paper details: {e}")
            return f"Error fetching paper details: {str(e)}"
    
    async def run_batch(
        self,
        paper_ids: list[str],
        source: str = "semantic_scholar"
    ) -> list[tuple[str, str]]:
        """
        批量获取论文详细信息
        
        Args:
            paper_ids: 论文 ID 列表
            source: 数据来源
            
        Returns:
            list[tuple[paper_id, details]]:论文 ID 和详情的元组列表
        """
        import asyncio
        
        tasks = [
            self.run(paper_id, source, include_references=False, include_citations=False)
            for paper_id in paper_ids
        ]
        
        results = await asyncio.gather(*tasks)
        
        return list(zip(paper_ids, results))
    
    def _format_paper_info(self, paper: Paper, language: str = "en") -> str:
        """格式化论文基本信息"""
        lines = []
        
        # 标题
        lines.append(f"# {paper.title}")
        lines.append("")
        
        # 元数据
        lines.append("## Basic Information")
        lines.append("")
        
        if paper.authors:
            lines.append(f"- **Authors**: {', '.join(paper.authors)}")
        lines.append(f"- **Year**: {paper.year}")
        lines.append(f"- **Venue**: {paper.venue or 'N/A'}")
        lines.append(f"- **Citations**: {paper.citation_count}")
        if paper.influential_citation_count > 0:
            lines.append(f"- **Influential Citations**: {paper.influential_citation_count}")
        
        # 标识符
        lines.append("")
        lines.append("## Identifiers")
        lines.append("")
        if paper.doi:
            lines.append(f"- **DOI**: {paper.doi}")
        if paper.arxiv_id:
            lines.append(f"- **arXiv ID**: {paper.arxiv_id}")
        lines.append(f"- **Semantic Scholar ID**: {paper.paper_id}")
        
        # 摘要
        if paper.abstract:
            lines.append("")
            lines.append("## Abstract")
            lines.append("")
            lines.append(paper.abstract)
        
        # 关键词
        if paper.keywords:
            lines.append("")
            lines.append("## Keywords")
            lines.append("")
            lines.append(", ".join(paper.keywords))
        
        # 研究领域
        if paper.fields_of_study:
            lines.append("")
            lines.append("## Fields of Study")
            lines.append("")
            lines.append(", ".join(paper.fields_of_study))
        
        # 链接
        lines.append("")
        lines.append("## Links")
        lines.append("")
        lines.append(f"- **Paper URL**: [{paper.url}]({paper.url})")
        if paper.open_access_pdf:
            lines.append(f"- **PDF**: [{paper.open_access_pdf}]({paper.open_access_pdf})")
        
        return "\n".join(lines)
    
    def _format_paper_list(self, papers: list[Paper]) -> str:
        """格式化论文列表"""
        if not papers:
            return "No papers found."
        
        lines = []
        for idx, paper in enumerate(papers, 1):
            authors_str = ", ".join(paper.authors[:3]) + " et al." if len(paper.authors) > 3 else ", ".join(paper.authors)
            
            lines.append(f"{idx}. **{paper.title}**")
            lines.append(f"   - Authors: {authors_str or 'Unknown'}")
            lines.append(f"   - Year: {paper.year}, Citations: {paper.citation_count}")
            if paper.url:
                lines.append(f"   - URL: [{paper.paper_id}]({paper.url})")
            lines.append("")
        
        return "\n".join(lines)
    
    async def get_paper_abstract(self, paper_id: str) -> str:
        """
        仅获取论文摘要
        
        Args:
            paper_id: 论文 ID
            
        Returns:
            str: 论文摘要
        """
        paper = await self.academic_search.get_paper_by_id(paper_id)
        
        if paper and paper.abstract:
            return paper.abstract
        
        return "Abstract not available."
    
    async def get_paper_metadata(self, paper_id: str) -> dict:
        """
        获取论文元数据（简洁版本）
        
        Args:
            paper_id: 论文 ID
            
        Returns:
            dict: 论文元数据
        """
        paper = await self.academic_search.get_paper_by_id(paper_id)
        
        if paper:
            return {
                "paper_id": paper.paper_id,
                "title": paper.title,
                "authors": paper.authors,
                "year": paper.year,
                "venue": paper.venue,
                "citation_count": paper.citation_count,
                "doi": paper.doi,
                "arxiv_id": paper.arxiv_id,
            }
        
        return {"error": f"Paper '{paper_id}' not found"}
