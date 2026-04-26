#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Paper Research Actions - 学术论文研究相关 Action 模块

本模块包含学术论文检索、分析和总结所需的各类 Action。

Actions:
    - SearchAcademicPapers: 搜索学术论文
    - FetchPaperDetails: 获取论文详情
    - AnalyzeCitations: 分析论文引用关系
    - GeneratePaperSummary: 生成论文摘要
    - RankPapers: 论文排序
"""

from metagpt.actions.paper_research.analyze_citations import AnalyzeCitations
from metagpt.actions.paper_research.fetch_paper_details import FetchPaperDetails
from metagpt.actions.paper_research.generate_summary import GeneratePaperSummary
from metagpt.actions.paper_research.rank_papers import RankPapers
from metagpt.actions.paper_research.search_papers import SearchAcademicPapers

__all__ = [
    "SearchAcademicPapers",
    "FetchPaperDetails",
    "AnalyzeCitations",
    "GeneratePaperSummary",
    "RankPapers",
]
