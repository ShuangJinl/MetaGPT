#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AnalyzeCitations - 分析论文引用关系 Action

功能：
- 分析论文的引用网络
- 识别高影响力引用
- 生成引用关系图谱描述
- 计算相关学术指标

@Time    : 2024
@Author  : MetaGPT Extension
@File    : analyze_citations.py
"""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from metagpt.actions import Action
from metagpt.logs import logger
from metagpt.tools.academic_search import (
    AcademicSearchTool,
    Paper,
    get_academic_search_tool,
)


CITATION_ANALYSIS_PROMPT = """
## Paper Information
- **Title**: {title}
- **Authors**: {authors}
- **Year**: {year}
- **Venue**: {venue}
- **Total Citations**: {citation_count}
- **Influential Citations**: {influential_count}

## Citation Network
### References (Papers cited by this paper)
{references}

### Cited By (Papers citing this paper)
{cited_by}

## Requirements
Please analyze the citation network of this paper and provide:
1. **Citation Overview**: Overview of the paper's academic impact based on citation metrics
2. **Key References**: Identify the most influential papers in the reference list
3. **Follow-up Research**: Analyze papers that cite this work and identify research trends
4. **Research Impact**: Assess the paper's contribution to the field
5. **Research Gap**: Identify potential areas not yet explored based on this work

## Output Language
Output in: {language}
"""


NETWORK_SUMMARY_PROMPT = """
## Papers to Analyze
{papers_info}

## Requirements
Based on the papers above, please:
1. Build a citation network overview showing relationships between papers
2. Identify hub papers (highly cited papers that bridge different topics)
3. Identify emerging papers (recent papers gaining citations)
4. Suggest reading order based on citation relationships
5. Identify research clusters (groups of papers addressing similar topics)

## Output Format
Provide a structured analysis with clear sections for each analysis point.

## Output Language
Output in: {language}
"""


class CitationMetrics(BaseModel):
    """引用指标"""
    total_citations: int
    influential_citations: int
    influence_ratio: float
    year: int
    citation_velocity: float  # citations per year


class CitationAnalysis(BaseModel):
    """引用分析结果"""
    paper_id: str
    paper_title: str
    metrics: Optional[CitationMetrics] = None
    key_references: list[dict] = Field(default_factory=list)
    follow_up_research: list[dict] = Field(default_factory=list)
    research_impact_summary: str = ""
    research_gaps: list[str] = Field(default_factory=list)


from pydantic import BaseModel


class AnalyzeCitations(Action):
    """
    分析论文引用关系 Action
    
    Attributes:
        name: Action 名称
        desc: Action 描述
        academic_search: 学术搜索引擎实例
        max_references: 最大分析参考文献数
        max_citations: 最大分析被引数
    """
    
    name: str = "AnalyzeCitations"
    desc: str = "Analyze citation relationships of academic papers"
    academic_search: Optional[AcademicSearchTool] = None
    max_references: int = Field(default=15, description="Maximum references to analyze")
    max_citations: int = Field(default=15, description="Maximum citations to analyze")
    
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
        language: str = "en"
    ) -> str:
        """
        分析单篇论文的引用关系
        
        Args:
            paper_id: 论文 ID
            source: 数据来源
            language: 输出语言
            
        Returns:
            str: 引用分析结果
        """
        logger.info(f"Analyzing citations for paper: {paper_id}")
        
        try:
            # 获取论文基本信息
            paper = await self.academic_search.get_paper_by_id(paper_id, source)
            
            if paper is None:
                return f"Paper with ID '{paper_id}' not found."
            
            # 获取参考文献和被引列表
            ref_task = self.academic_search.get_paper_citations(paper_id)
            cit_task = self.academic_search.get_paper_cited_by(paper_id)
            
            references, cited_by = await self._fetch_citations(ref_task, cit_task)
            
            # 计算引用指标
            metrics = self._calculate_metrics(paper, references, cited_by)
            
            # 生成分析报告
            return await self._generate_analysis_report(
                paper, references, cited_by, metrics, language
            )
            
        except Exception as e:
            logger.error(f"Error analyzing citations: {e}")
            return f"Error analyzing citations: {str(e)}"
    
    async def _fetch_citations(self, ref_task, cit_task):
        """并行获取引用信息"""
        import asyncio
        try:
            results = await asyncio.gather(ref_task, cit_task, return_exceptions=True)
            references = results[0] if not isinstance(results[0], Exception) else []
            cited_by = results[1] if not isinstance(results[1], Exception) else []
        except:
            references = await ref_task if hasattr(ref_task, '__await__') else ref_task
            cited_by = await cit_task if hasattr(cit_task, '__await__') else cit_task
        
        return references[:self.max_references], cited_by[:self.max_citations]
    
    def _calculate_metrics(
        self,
        paper: Paper,
        references: list[Paper],
        cited_by: list[Paper]
    ) -> CitationMetrics:
        """计算引用指标"""
        # 计算引用速度（每年引用数）
        years_since_publication = max(1, 2024 - paper.year)
        citation_velocity = paper.citation_count / years_since_publication
        
        # 计算影响力比率
        influence_ratio = (
            paper.influential_citation_count / paper.citation_count
            if paper.citation_count > 0 else 0
        )
        
        return CitationMetrics(
            total_citations=paper.citation_count,
            influential_citations=paper.influential_citation_count,
            influence_ratio=round(influence_ratio, 3),
            year=paper.year,
            citation_velocity=round(citation_velocity, 2)
        )
    
    async def _generate_analysis_report(
        self,
        paper: Paper,
        references: list[Paper],
        cited_by: list[Paper],
        metrics: CitationMetrics,
        language: str
    ) -> str:
        """生成分析报告"""
        # 格式化参考文献
        ref_text = self._format_paper_list(references, max_count=10)
        
        # 格式化被引列表
        cit_text = self._format_paper_list(cited_by, max_count=10)
        
        # 构建提示
        prompt = CITATION_ANALYSIS_PROMPT.format(
            title=paper.title,
            authors=", ".join(paper.authors[:3]) + (" et al." if len(paper.authors) > 3 else ""),
            year=paper.year,
            venue=paper.venue or "N/A",
            citation_count=paper.citation_count,
            influential_count=paper.influential_citation_count,
            references=ref_text or "No references available.",
            cited_by=cit_text or "No citations available yet.",
            language=language
        )
        
        # 调用 LLM 进行分析
        analysis = await self._aask(prompt)
        
        # 构建完整报告
        report = [
            f"# Citation Analysis: {paper.title}",
            "",
            "## Citation Metrics",
            "",
            f"- **Total Citations**: {metrics.total_citations}",
            f"- **Influential Citations**: {metrics.influential_citations}",
            f"- **Influence Ratio**: {metrics.influence_ratio:.1%}",
            f"- **Years Since Publication**: {2024 - metrics.year}",
            f"- **Citation Velocity**: {metrics.citation_velocity:.1} citations/year",
            "",
            "---",
            "",
            "## Analysis Report",
            "",
            analysis
        ]
        
        return "\n".join(report)
    
    async def run_network_analysis(
        self,
        paper_ids: list[str],
        language: str = "en"
    ) -> str:
        """
        对多篇论文进行引用网络分析
        
        Args:
            paper_ids: 论文 ID 列表
            language: 输出语言
            
        Returns:
            str: 网络分析结果
        """
        logger.info(f"Running citation network analysis for {len(paper_ids)} papers")
        
        try:
            # 批量获取论文信息
            papers = []
            for pid in paper_ids:
                paper = await self.academic_search.get_paper_by_id(pid)
                if paper:
                    papers.append(paper)
            
            if not papers:
                return "No valid papers found for network analysis."
            
            # 格式化论文信息
            papers_info = []
            for paper in papers:
                papers_info.append(
                    f"- **Title**: {paper.title}\n"
                    f"  **ID**: {paper.paper_id}\n"
                    f"  **Authors**: {', '.join(paper.authors[:3])}\n"
                    f"  **Year**: {paper.year}\n"
                    f"  **Citations**: {paper.citation_count}\n"
                )
            
            # 生成网络分析报告
            prompt = NETWORK_SUMMARY_PROMPT.format(
                papers_info="\n\n".join(papers_info),
                language=language
            )
            
            analysis = await self._aask(prompt)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in network analysis: {e}")
            return f"Error in network analysis: {str(e)}"
    
    def _format_paper_list(self, papers: list[Paper], max_count: int = 10) -> str:
        """格式化论文列表"""
        if not papers:
            return "No papers available."
        
        lines = []
        for idx, paper in enumerate(papers[:max_count], 1):
            authors_str = (
                ", ".join(paper.authors[:2]) + " et al."
                if len(paper.authors) > 2 else ", ".join(paper.authors)
            )
            
            lines.append(
                f"{idx}. **{paper.title}** ({paper.year})\n"
                f"   Author(s): {authors_str or 'Unknown'} | "
                f"Citations: {paper.citation_count}"
            )
        
        if len(papers) > max_count:
            lines.append(f"\n... and {len(papers) - max_count} more papers.")
        
        return "\n\n".join(lines)
    
    async def get_influential_papers(
        self,
        paper_id: str,
        threshold: float = 0.5
    ) -> list[Paper]:
        """
        获取高影响力参考文献
        
        Args:
            paper_id: 论文 ID
            threshold: 影响力阈值（引用数高于此值的论文被视为高影响力）
            
        Returns:
            list[Paper]: 高影响力论文列表
        """
        references = await self.academic_search.get_paper_citations(paper_id)
        
        # 筛选高影响力论文（引用数高于阈值或高于平均）
        if references:
            avg_citations = sum(p.citation_count for p in references) / len(references)
            threshold = max(threshold, avg_citations)
        
        influential = [p for p in references if p.citation_count >= threshold]
        
        return sorted(influential, key=lambda x: x.citation_count, reverse=True)
    
    def calculate_h_index(self, papers: list[Paper]) -> int:
        """
        计算 H-index
        
        基于论文列表计算 H-index：至少有 h 篇论文被引用 h 次
        
        Args:
            papers: 论文列表
            
        Returns:
            int: H-index 值
        """
        if not papers:
            return 0
        
        citations = sorted([p.citation_count for p in papers], reverse=True)
        
        h_index = 0
        for idx, cit in enumerate(citations, 1):
            if cit >= idx:
                h_index = idx
            else:
                break
        
        return h_index
