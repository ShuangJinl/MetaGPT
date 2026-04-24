#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GeneratePaperSummary - 生成学术论文摘要 Action

功能：
- 使用 LLM 生成论文核心贡献摘要
- 提取研究方法和实验结果
- 生成论文亮点总结
- 支持中英文输出
- 支持多篇论文对比摘要

@Time    : 2024
@Author  : MetaGPT Extension
@File    : generate_summary.py
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


SINGLE_PAPER_SUMMARY_PROMPT = """
## Paper Information
- **Title**: {title}
- **Authors**: {authors}
- **Year**: {year}
- **Venue**: {venue}
- **Abstract**: {abstract}

## Requirements
Please provide a comprehensive summary of this paper in {language}, including:
1. **Core Contribution**: What is the main contribution of this paper?
2. **Methodology**: What methods or approaches does the paper use?
3. **Key Findings**: What are the most important results or discoveries?
4. **Highlights**: What are the standout aspects of this work?
5. **Limitations**: What are the potential limitations or areas for improvement?

## Output Format
Provide a well-structured summary with clear sections. Use bullet points where appropriate.

Length: 300-500 words for a comprehensive summary.
"""


COMPARATIVE_SUMMARY_PROMPT = """
## Papers to Compare
{papers_info}

## Requirements
Please provide a comparative analysis of these papers in {language}, including:
1. **Overview**: Brief description of each paper (1-2 sentences)
2. **Similarities**: What common themes or approaches do these papers share?
3. **Differences**: How do they differ in methodology, scope, or findings?
4. **Complementary Aspects**: How might these papers complement each other?
5. **Comparative Summary**: A table comparing key aspects (Methodology, Scope, Results, Limitations)

## Output Format
Use a structured format with clear sections and a comparison table.
"""


EXTENDED_ABSTRACT_PROMPT = """
## Paper Information
- **Title**: {title}
- **Authors**: {authors}
- **Year**: {year}
- **Venue**: {venue}
- **Keywords**: {keywords}
- **Full Abstract**: {abstract}

## Requirements
Expand the paper's abstract into a more detailed research summary in {language}, including:
1. **Background**: The problem context and motivation
2. **Problem Statement**: What specific problem does this paper address?
3. **Proposed Approach**: Detailed description of the proposed method
4. **Experimental Setup**: Key experimental settings and datasets used
5. **Main Results**: Quantitative and qualitative results
6. **Conclusions**: Key takeaways and implications for the field

## Output Format
Provide a well-structured extended abstract with clear sections.
Length: 800-1200 words.
"""


class GeneratePaperSummary(Action):
    """
    生成论文摘要 Action
    
    Attributes:
        name: Action 名称
        desc: Action 描述
        academic_search: 学术搜索引擎实例
    """
    
    name: str = "GeneratePaperSummary"
    desc: str = "Generate comprehensive summaries for academic papers"
    academic_search: Optional[AcademicSearchTool] = None
    summary_length: str = Field(default="medium", description="Summary length: short, medium, or extended")
    
    @model_validator(mode="after")
    def validate_academic_search(self):
        """初始化学术搜索引擎"""
        if self.academic_search is None:
            self.academic_search = get_academic_search_tool()
        return self
    
    async def run(
        self,
        paper_id: str,
        source: str = "arxiv",
        language: str = "en",
        paper_data: Optional[Paper] = None
    ) -> str:
        """
        生成单篇论文摘要
        
        Args:
            paper_id: 论文 ID
            source: 数据来源
            language: 输出语言
            paper_data: 直接传入论文数据（避免额外 API 调用）
            
        Returns:
            str: 论文摘要
        """
        logger.info(f"Generating summary for paper: {paper_id}")
        
        try:
            # 获取论文信息，如果有直接传入则使用传入的数据
            if paper_data is None:
                paper = await self.academic_search.get_paper_by_id(paper_id, source)
            else:
                paper = paper_data
            
            if paper is None:
                return f"Paper with ID '{paper_id}' not found."
            
            # 根据摘要长度选择提示模板
            if self.summary_length == "extended":
                return await self._generate_extended_abstract(paper, language)
            else:
                return await self._generate_standard_summary(paper, language)
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Error generating summary: {str(e)}"
    
    async def _generate_standard_summary(
        self,
        paper: Paper,
        language: str
    ) -> str:
        """生成标准摘要"""
        # 构建提示
        prompt = SINGLE_PAPER_SUMMARY_PROMPT.format(
            title=paper.title,
            authors=", ".join(paper.authors) if paper.authors else "Unknown",
            year=paper.year,
            venue=paper.venue or "N/A",
            abstract=paper.abstract or "No abstract available.",
            language=language
        )
        
        # 调用 LLM 生成摘要
        summary = await self._aask(prompt)
        
        # 构建完整报告
        lang_label = "中文" if language == "zh" else "English"
        
        report = [
            f"# Paper Summary",
            "",
            f"## {paper.title}",
            "",
            "### Metadata",
            "",
            f"- **Authors**: {', '.join(paper.authors[:5])}{' et al.' if len(paper.authors) > 5 else ''}",
            f"- **Year**: {paper.year}",
            f"- **Venue**: {paper.venue or 'N/A'}",
            f"- **Citations**: {paper.citation_count}",
            "",
            "---",
            "",
            summary
        ]
        
        return "\n".join(report)
    
    async def _generate_extended_abstract(
        self,
        paper: Paper,
        language: str
    ) -> str:
        """生成扩展摘要"""
        prompt = EXTENDED_ABSTRACT_PROMPT.format(
            title=paper.title,
            authors=", ".join(paper.authors) if paper.authors else "Unknown",
            year=paper.year,
            venue=paper.venue or "N/A",
            keywords=", ".join(paper.keywords) if paper.keywords else "N/A",
            abstract=paper.abstract or "No abstract available.",
            language=language
        )
        
        extended = await self._aask(prompt)
        
        report = [
            f"# Extended Paper Summary",
            "",
            f"## {paper.title}",
            "",
            "### Metadata",
            "",
            f"- **Authors**: {', '.join(paper.authors[:5])}{' et al.' if len(paper.authors) > 5 else ''}",
            f"- **Year**: {paper.year}",
            f"- **Venue**: {paper.venue or 'N/A'}",
            f"- **Keywords**: {', '.join(paper.keywords) if paper.keywords else 'N/A'}",
            f"- **Citations**: {paper.citation_count}",
            "",
            "---",
            "",
            extended
        ]
        
        return "\n".join(report)
    
    async def run_batch(
        self,
        paper_ids: list[str],
        source: str = "semantic_scholar",
        language: str = "en"
    ) -> str:
        """
        批量生成论文摘要
        
        Args:
            paper_ids: 论文 ID 列表
            source: 数据来源
            language: 输出语言
            
        Returns:
            str: 所有论文的摘要
        """
        import asyncio
        
        logger.info(f"Generating summaries for {len(paper_ids)} papers")
        
        # 并行生成摘要
        tasks = [
            self.run(paper_id, source, language)
            for paper_id in paper_ids
        ]
        
        summaries = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 构建完整报告
        reports = []
        for idx, (pid, summary) in enumerate(zip(paper_ids, summaries)):
            if isinstance(summary, Exception):
                reports.append(f"## Paper {idx + 1} (ID: {pid})\n\nError: {str(summary)}")
            else:
                # 添加分隔
                reports.append(f"{summary}\n\n{'=' * 50}\n")
        
        return "\n".join(reports)
    
    async def run_comparative(
        self,
        paper_ids: list[str],
        source: str = "semantic_scholar",
        language: str = "en"
    ) -> str:
        """
        生成对比摘要
        
        Args:
            paper_ids: 论文 ID 列表
            source: 数据来源
            language: 输出语言
            
        Returns:
            str: 对比分析结果
        """
        logger.info(f"Generating comparative summary for {len(paper_ids)} papers")
        
        try:
            # 获取所有论文信息
            papers = []
            for pid in paper_ids:
                paper = await self.academic_search.get_paper_by_id(pid, source)
                if paper:
                    papers.append(paper)
            
            if len(papers) < 2:
                return "Need at least 2 papers for comparative summary."
            
            # 格式化论文信息
            papers_info = []
            for idx, paper in enumerate(papers, 1):
                papers_info.append(
                    f"### Paper {idx}: {paper.title}\n"
                    f"- **Authors**: {', '.join(paper.authors[:3])}\n"
                    f"- **Year**: {paper.year}\n"
                    f"- **Venue**: {paper.venue or 'N/A'}\n"
                    f"- **Abstract**: {paper.abstract[:500]}{'...' if len(paper.abstract) > 500 else ''}\n"
                )
            
            # 生成对比分析
            prompt = COMPARATIVE_SUMMARY_PROMPT.format(
                papers_info="\n\n".join(papers_info),
                language=language
            )
            
            comparison = await self._aask(prompt)
            
            # 构建完整报告
            report = [
                "# Comparative Paper Summary",
                "",
                f"Analyzing {len(papers)} papers",
                "",
                "---",
                "",
                comparison
            ]
            
            return "\n".join(report)
            
        except Exception as e:
            logger.error(f"Error generating comparative summary: {e}")
            return f"Error generating comparative summary: {str(e)}"
    
    async def generate_key_points(
        self,
        paper_id: str,
        source: str = "semantic_scholar",
        language: str = "en"
    ) -> str:
        """
        生成论文要点列表（简洁版本）
        
        Args:
            paper_id: 论文 ID
            source: 数据来源
            language: 输出语言
            
        Returns:
            str: 论文要点
        """
        logger.info(f"Generating key points for paper: {paper_id}")
        
        try:
            paper = await self.academic_search.get_paper_by_id(paper_id, source)
            
            if paper is None:
                return f"Paper with ID '{paper_id}' not found."
            
            KEY_POINTS_PROMPT = """
## Paper
- **Title**: {title}
- **Authors**: {authors}
- **Abstract**: {abstract}

## Requirements
Extract 5-7 key points from this paper in {language}. Each point should be:
- Concise (1-2 sentences)
- Informative (captures the main idea)
- Ordered by importance

## Output Format
Provide a numbered list of key points.
"""
            
            prompt = KEY_POINTS_PROMPT.format(
                title=paper.title,
                authors=", ".join(paper.authors[:3]),
                abstract=paper.abstract or "No abstract available.",
                language=language
            )
            
            key_points = await self._aask(prompt)
            
            return key_points
            
        except Exception as e:
            logger.error(f"Error generating key points: {e}")
            return f"Error: {str(e)}"
