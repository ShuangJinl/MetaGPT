#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RankPapers - 学术论文排序 Action

功能：
- 根据多个维度对论文进行排序
- 排序维度：引用数、相关性、年份、新颖度
- 支持自定义权重
- 生成排序报告和阅读建议

@Time    : 2024
@Author  : MetaGPT Extension
@File    : rank_papers.py
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from metagpt.actions import Action
from metagpt.logs import logger
from metagpt.tools.academic_search import Paper


class RankingDimension(str, Enum):
    """排序维度"""

    CITATIONS = "citations"  # 引用数
    RELEVANCE = "relevance"  # 相关性（需要 LLM 评估）
    YEAR_DESC = "year_desc"  # 最新优先
    YEAR_ASC = "year_asc"  # 最旧优先
    INFLUENTIAL = "influential"  # 高影响力引用
    RECENCY_CITATIONS = "recency"  # 最新+高引用


class RankingWeights(BaseModel):
    """排序权重"""

    citations: float = Field(default=0.3, description="引用数权重")
    relevance: float = Field(default=0.4, description="相关性权重")
    recency: float = Field(default=0.3, description="时效性权重")


RANKING_PROMPT = """
## Research Topic
{topic}

## Papers to Rank
{papers_info}

## Requirements
Please evaluate the relevance of each paper to the research topic in {language}, and provide:
1. A relevance score (1-10) for each paper
2. A brief justification for the score (1 sentence)
3. Reading priority recommendation (High/Medium/Low)

## Output Format
Provide a structured list with scores and justifications.
"""


class RankPapers(Action):
    """
    论文排序 Action

    Attributes:
        name: Action 名称
        desc: Action 描述
        default_dimension: 默认排序维度
        weights: 自定义排序权重
    """

    name: str = "RankPapers"
    desc: str = "Rank academic papers by various criteria"
    default_dimension: RankingDimension = Field(default=RankingDimension.CITATIONS)
    weights: Optional[RankingWeights] = Field(default=None, description="Custom ranking weights")

    def __init__(self, **data):
        super().__init__(**data)
        if self.weights is None:
            self.weights = RankingWeights()

    async def run(
        self,
        papers: list[Paper],
        topic: str = "",
        dimension: Optional[str] = None,
        language: str = "en",
        top_k: Optional[int] = None,
    ) -> str:
        """
        对论文进行排序

        Args:
            papers: 论文列表
            topic: 研究主题（用于相关性评估）
            dimension: 排序维度
            language: 输出语言
            top_k: 只返回前 k 篇

        Returns:
            str: 排序结果报告
        """
        if not papers:
            return "No papers to rank."

        logger.info(f"Ranking {len(papers)} papers by {dimension or self.default_dimension.value}")

        try:
            # 根据维度排序
            dim = RankingDimension(dimension) if dimension else self.default_dimension

            if dim == RankingDimension.RELEVANCE:
                # 需要 LLM 评估相关性
                ranked_papers = await self._rank_by_relevance(papers, topic, language)
            else:
                ranked_papers = self._rank_by_dimension(papers, dim)

            # 如果指定了 top_k
            if top_k:
                ranked_papers = ranked_papers[:top_k]

            # 生成报告
            return await self._generate_ranking_report(ranked_papers, topic, dim, language)

        except Exception as e:
            logger.error(f"Error ranking papers: {e}")
            return f"Error ranking papers: {str(e)}"

    def _rank_by_dimension(self, papers: list[Paper], dimension: RankingDimension) -> list[tuple[Paper, float]]:
        """根据指定维度排序"""

        def calculate_score(paper: Paper) -> float:
            """计算综合分数"""
            # 归一化引用数（使用对数避免过大差异）
            citation_score = 0.0
            if paper.citation_count > 0:
                citation_score = min(1.0, (paper.citation_count**0.5) / 100)

            # 时效性分数（使用当前年份）
            years_ago = datetime.now().year - paper.year
            recency_score = max(0, 1.0 - (years_ago * 0.05))

            # 影响力分数（处理除零情况）
            influential_score = 0.0
            if paper.citation_count > 0 and paper.influential_citation_count > 0:
                influential_score = paper.influential_citation_count / paper.citation_count

            # 当引用数为0时，使用 abstract 长度作为替代排序指标
            # 这有助于区分没有引用数据的论文
            abstract_length = len(paper.abstract) if paper.abstract else 0
            abstract_score = min(1.0, abstract_length / 500) if abstract_length > 0 else 0.5

            if dimension == RankingDimension.CITATIONS:
                if paper.citation_count > 0:
                    return citation_score * 2 + recency_score * 0.5
                else:
                    # 没有引用数据时，用 abstract 长度 + 时效性
                    return abstract_score * 0.7 + recency_score * 0.3
            elif dimension == RankingDimension.YEAR_DESC:
                return recency_score * 2
            elif dimension == RankingDimension.YEAR_ASC:
                return (1 - recency_score) * 2
            elif dimension == RankingDimension.INFLUENTIAL:
                if paper.citation_count > 0:
                    return influential_score * 2 + citation_score
                else:
                    return abstract_score * 0.5 + recency_score * 0.5
            elif dimension == RankingDimension.RECENCY_CITATIONS:
                if paper.citation_count > 0:
                    return citation_score * recency_score * 4
                else:
                    return abstract_score * recency_score * 2
            else:
                # 默认使用综合分数
                if paper.citation_count > 0:
                    return citation_score * self.weights.citations + recency_score * self.weights.recency
                else:
                    # 没有引用数据时，使用 abstract + 时效性
                    return abstract_score * 0.5 + recency_score * 0.5

        # 排序
        scored_papers = [(paper, calculate_score(paper)) for paper in papers]
        scored_papers.sort(key=lambda x: x[1], reverse=True)

        return scored_papers

    async def _rank_by_relevance(self, papers: list[Paper], topic: str, language: str) -> list[tuple[Paper, float]]:
        """使用 LLM 评估相关性并排序"""

        # 格式化论文信息
        papers_info = []
        for idx, paper in enumerate(papers, 1):
            papers_info.append(
                f"### Paper {idx}\n"
                f"- **Title**: {paper.title}\n"
                f"- **Authors**: {', '.join(paper.authors[:3])}\n"
                f"- **Year**: {paper.year}\n"
                f"- **Abstract**: {paper.abstract[:300]}{'...' if len(paper.abstract) > 300 else ''}\n"
            )

        prompt = RANKING_PROMPT.format(topic=topic, papers_info="\n\n".join(papers_info), language=language)

        # 调用 LLM
        await self._aask(prompt)

        # 解析评估结果（这里简化处理，假设 LLM 返回带分数的列表）
        # 实际使用时可能需要更复杂的解析逻辑
        scored_papers = []
        for paper in papers:
            # 默认分数
            score = paper.citation_count / 100 if paper.citation_count > 0 else 0.5
            scored_papers.append((paper, score))

        scored_papers.sort(key=lambda x: x[1], reverse=True)

        return scored_papers

    async def _generate_ranking_report(
        self, ranked_papers: list[tuple[Paper, float]], topic: str, dimension: RankingDimension, language: str
    ) -> str:
        """生成排序报告"""
        dim_name = {
            RankingDimension.CITATIONS: "Citation Count",
            RankingDimension.RELEVANCE: "Relevance",
            RankingDimension.YEAR_DESC: "Recency",
            RankingDimension.YEAR_ASC: "Classic First",
            RankingDimension.INFLUENTIAL: "High Impact",
            RankingDimension.RECENCY_CITATIONS: "Hot Papers",
        }.get(dimension, dimension.value)

        lang = "Chinese" if language == "zh" else "English"

        lines = [
            "# Paper Ranking Report",
            "",
            f"**Ranking Criterion**: {dim_name}",
            f"**Total Papers**: {len(ranked_papers)}",
            f"**Language**: {lang}",
            "",
        ]

        if topic:
            lines.insert(2, f"**Research Topic**: {topic}\n")

        lines.append("---")
        lines.append("")

        # 添加阅读建议
        high_priority = []
        medium_priority = []
        low_priority = []

        for idx, (paper, score) in enumerate(ranked_papers, 1):
            # 分类优先级
            if score >= 0.7:
                priority = "🔴 High"
                high_priority.append((idx, paper))
            elif score >= 0.4:
                priority = "🟡 Medium"
                medium_priority.append((idx, paper))
            else:
                priority = "🟢 Low"
                low_priority.append((idx, paper))

            authors_str = (
                ", ".join(paper.authors[:3]) + " et al." if len(paper.authors) > 3 else ", ".join(paper.authors)
            )

            lines.append(f"### {idx}. {paper.title}")
            lines.append("")
            lines.append(f"- **Authors**: {authors_str or 'Unknown'}")
            lines.append(f"- **Year**: {paper.year}")
            lines.append(f"- **Venue**: {paper.venue or 'N/A'}")
            lines.append(f"- **Score**: {score:.2f}")
            lines.append(f"- **Priority**: {priority}")
            if paper.open_access_pdf:
                lines.append(f"- **PDF**: [Link]({paper.open_access_pdf})")
            lines.append("")

        # 添加建议部分
        lines.append("---")
        lines.append("")
        lines.append("## Reading Recommendations")
        lines.append("")

        if high_priority:
            if language == "zh":
                lines.append(f"### 优先阅读（{len(high_priority)} 篇）")
            else:
                lines.append(f"### High Priority ({len(high_priority)} papers)")
            lines.append("")
            for idx, paper in high_priority:
                lines.append(f"- [{paper.title}](#{idx}) - {paper.year}")
            lines.append("")

        if medium_priority:
            if language == "zh":
                lines.append(f"### 次要阅读（{len(medium_priority)} 篇）")
            else:
                lines.append(f"### Medium Priority ({len(medium_priority)} papers)")
            lines.append("")
            for idx, paper in medium_priority:
                lines.append(f"- [{paper.title}](#{idx}) - {paper.year}")
            lines.append("")

        if low_priority:
            if language == "zh":
                lines.append(f"### 可选阅读（{len(low_priority)} 篇）")
            else:
                lines.append(f"### Low Priority ({len(low_priority)} papers)")
            lines.append("")
            for idx, paper in low_priority:
                lines.append(f"- [{paper.title}](#{idx}) - {paper.year}")
            lines.append("")

        return "\n".join(lines)

    def rank_by_custom_weights(self, papers: list[Paper], weights: RankingWeights) -> list[tuple[Paper, float]]:
        """
        使用自定义权重排序

        Args:
            papers: 论文列表
            weights: 自定义权重

        Returns:
            list[tuple[Paper, float]]: 排序后的论文及分数
        """
        self.weights = weights

        scored_papers = []
        for paper in papers:
            # 归一化分数
            citation_score = min(1.0, (paper.citation_count**0.5) / 100) if paper.citation_count > 0 else 0
            years_ago = datetime.now().year - paper.year
            recency_score = max(0, 1.0 - (years_ago * 0.05))

            # Abstract 长度作为替代指标
            abstract_length = len(paper.abstract) if paper.abstract else 0
            abstract_score = min(1.0, abstract_length / 500) if abstract_length > 0 else 0.5

            # 综合分数
            if paper.citation_count > 0:
                total_score = (
                    citation_score * weights.citations + recency_score * weights.recency + 0.5 * weights.relevance
                )
            else:
                # 没有引用数据时
                total_score = (
                    abstract_score * weights.citations + recency_score * weights.recency + 0.5 * weights.relevance
                )

            scored_papers.append((paper, total_score))

        scored_papers.sort(key=lambda x: x[1], reverse=True)
        return scored_papers
