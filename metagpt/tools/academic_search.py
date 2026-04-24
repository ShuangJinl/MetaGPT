#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Academic Search Tools - 学术论文搜索工具
支持 Semantic Scholar 和 arXiv API

@Time    : 2024
@Author  : MetaGPT Extension
@File    : academic_search.py
"""

import asyncio
import xml.etree.ElementTree as ET
from typing import Any, ClassVar, Dict, Optional
from urllib.parse import urlencode

import aiohttp
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from metagpt.logs import logger


class Paper(BaseModel):
    """学术论文数据模型"""
    paper_id: str = Field(default="", description="论文唯一标识 (Semantic Scholar ID 或 arXiv ID)")
    title: str = Field(default="", description="论文标题")
    authors: list[str] = Field(default_factory=list, description="作者列表")
    abstract: str = Field(default="", description="论文摘要")
    year: int = Field(default=2024, description="发表年份")
    venue: str = Field(default="", description="发表 venue (期刊/会议名称)")
    citation_count: int = Field(default=0, description="引用数")
    influential_citation_count: int = Field(default=0, description="高影响力引用数")
    doi: Optional[str] = Field(default=None, description="DOI")
    arxiv_id: Optional[str] = Field(default=None, description="arXiv ID")
    url: str = Field(default="", description="论文链接")
    keywords: list[str] = Field(default_factory=list, description="关键词列表")
    references: list[str] = Field(default_factory=list, description="参考文献 ID 列表")
    cited_by: list[str] = Field(default_factory=list, description="被引用 ID 列表")
    open_access_pdf: Optional[str] = Field(default=None, description="开源 PDF 链接")
    fields_of_study: list[str] = Field(default_factory=list, description="研究领域")
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return self.model_dump()
    
    def to_short_dict(self) -> dict:
        """转换为简短字典（用于搜索结果展示）"""
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "authors": ", ".join(self.authors[:3]) + (" et al." if len(self.authors) > 3 else ""),
            "year": self.year,
            "venue": self.venue,
            "citation_count": self.citation_count,
        }


class AcademicSearchResult(BaseModel):
    """学术搜索结果"""
    total: int = Field(default=0, description="总结果数")
    papers: list[Paper] = Field(default_factory=list, description="论文列表")
    offset: int = Field(default=0, description="偏移量")
    next_offset: Optional[int] = Field(default=None, description="下一页偏移量")


class AcademicSearchTool(BaseModel):
    """学术搜索工具，支持 Semantic Scholar 和 arXiv"""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    semantic_scholar_api_key: Optional[str] = Field(default=None, description="Semantic Scholar API Key")
    timeout: int = Field(default=30, description="请求超时时间（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")
    
    _session: PrivateAttr = PrivateAttr(default=None)
    
    SEMANTIC_SCHOLAR_API: ClassVar = "https://api.semanticscholar.org/graph/v1"
    ARXIV_API: ClassVar = "http://export.arxiv.org/api/query"
    
    @property
    def session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _make_request(
        self, 
        url: str, 
        params: Optional[dict] = None, 
        headers: Optional[dict] = None,
        retry_count: int = 0,
        return_xml: bool = False
    ) -> dict:
        """发起 HTTP 请求，支持重试
        
        Args:
            return_xml: 是否返回 XML 格式（用于 arXiv API）
        """
        try:
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    if return_xml:
                        text = await response.text()
                        return self._parse_xml(text)
                    try:
                        return await response.json()
                    except Exception:
                        text = await response.text()
                        logger.error(f"JSON parse error: {text[:200]}")
                        return {}
                elif response.status == 429 and retry_count < self.max_retries:
                    wait_time = 2 ** retry_count
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    return await self._make_request(url, params, headers, retry_count + 1, return_xml)
                else:
                    logger.error(f"Request failed with status {response.status}")
                    return {}
        except Exception as e:
            if retry_count < self.max_retries:
                logger.warning(f"Request failed: {e}, retrying...")
                await asyncio.sleep(1)
                return await self._make_request(url, params, headers, retry_count + 1, return_xml)
            logger.error(f"Request failed after {self.max_retries} retries: {e}")
            return {}
    
    def _parse_xml(self, xml_text: str) -> dict:
        """解析 arXiv API 返回的 XML"""
        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return {"feed": {"entry": []}}
        
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        
        entries = []
        for entry in root.findall("atom:entry", ns):
            e = {}
            for child in entry:
                tag = child.tag
                if "}" in tag:
                    tag = tag.split("}")[-1]
                
                if tag == "author":
                    name_elem = child.find("atom:name", ns)
                    if name_elem is None:
                        for subchild in child:
                            if "name" in subchild.tag:
                                name_elem = subchild
                                break
                    if "author" not in e:
                        e["author"] = []
                    e["author"].append({"name": name_elem.text if name_elem is not None else ""})
                elif tag == "category":
                    e["category"] = child.get("term", "") if hasattr(child, "get") else ""
                elif tag == "link":
                    if hasattr(child, "get"):
                        link_type = child.get("type", "")
                        link_href = child.get("href", "")
                    else:
                        link_type = ""
                        link_href = ""
                    if "link" not in e:
                        e["link"] = []
                    e["link"].append({"type": link_type, "href": link_href})
                else:
                    e[tag] = child.text if child.text else ""
            entries.append(e)
        
        return {"feed": {"entry": entries}}
    
    async def search_semantic_scholar(
        self,
        query: str,
        max_results: int = 10,
        offset: int = 0,
        year_range: Optional[tuple[int, int]] = None,
        min_citation_count: int = 0,
        fields: Optional[list[str]] = None
    ) -> AcademicSearchResult:
        """
        搜索 Semantic Scholar 论文数据库
        
        Args:
            query: 搜索查询（支持关键词、作者、论文标题等）
            max_results: 最大返回结果数（最大100）
            offset: 结果偏移量（用于分页）
            year_range: 年份范围，如 (2020, 2024)
            min_citation_count: 最小引用数
            fields: 指定返回字段
            
        Returns:
            AcademicSearchResult: 搜索结果
        """
        if fields is None:
            fields = [
                "paperId", "title", "authors", "abstract", "year", 
                "venue", "citationCount", "influentialCitationCount",
                "doi", "arxivId", "url", "keywords", "references",
                "citations", "openAccessPdf", "fieldsOfStudy"
            ]
        
        params = {
            "query": query,
            "offset": offset,
            "limit": min(max_results, 100),
            "fields": ",".join(fields)
        }
        
        headers = {}
        if self.semantic_scholar_api_key:
            headers["x-api-key"] = self.semantic_scholar_api_key
        
        url = f"{self.SEMANTIC_SCHOLAR_API}/paper/search"
        data = await self._make_request(url, params, headers)
        
        papers = []
        if isinstance(data, dict) and "data" in data:
            for item in data["data"]:
                if not isinstance(item, dict):
                    continue
                paper = self._parse_semantic_scholar_paper(item)
                if paper.citation_count >= min_citation_count:
                    if year_range is None or year_range[0] <= paper.year <= year_range[1]:
                        papers.append(paper)
        
        total = data.get("total", 0) if isinstance(data, dict) else 0
        next_offset = offset + len(papers) if offset + len(papers) < total else None
        
        return AcademicSearchResult(
            total=total,
            papers=papers,
            offset=offset,
            next_offset=next_offset
        )
    
    def _parse_semantic_scholar_paper(self, item: dict) -> Paper:
        """解析 Semantic Scholar API 返回的论文数据"""
        if not isinstance(item, dict):
            item = {}
        
        authors = []
        for author in item.get("authors", []):
            if isinstance(author, dict):
                authors.append(author.get("name", ""))
            elif isinstance(author, str):
                authors.append(author)
        
        references = []
        for ref in item.get("references", []):
            if isinstance(ref, dict):
                references.append(ref.get("paperId", ""))
        
        citations = []
        for cit in item.get("citations", []):
            if isinstance(cit, dict):
                citations.append(cit.get("paperId", ""))
        
        open_access_pdf_url = None
        open_access_pdf = item.get("openAccessPdf")
        if isinstance(open_access_pdf, dict):
            open_access_pdf_url = open_access_pdf.get("url")
        elif isinstance(open_access_pdf, str):
            open_access_pdf_url = open_access_pdf
        
        return Paper(
            paper_id=item.get("paperId", ""),
            title=item.get("title", ""),
            authors=authors,
            abstract=item.get("abstract", "") or "",
            year=item.get("year", 2024),
            venue=item.get("venue", ""),
            citation_count=item.get("citationCount", 0),
            influential_citation_count=item.get("influentialCitationCount", 0),
            doi=item.get("doi"),
            arxiv_id=item.get("arxivId"),
            url=item.get("url", ""),
            keywords=item.get("keywords", []) if isinstance(item.get("keywords"), list) else [],
            references=references,
            cited_by=citations,
            open_access_pdf=open_access_pdf_url,
            fields_of_study=item.get("fieldsOfStudy", []) if isinstance(item.get("fieldsOfStudy"), list) else []
        )
    
    async def search_arxiv(
        self,
        query: str,
        max_results: int = 10,
        start: int = 0,
        sort_by: str = "relevance"  # relevance, lastUpdatedDate, submittedDate
    ) -> AcademicSearchResult:
        """
        搜索 arXiv 预印本数据库
        
        Args:
            query: 搜索查询
            max_results: 最大返回结果数
            start: 结果起始位置（用于分页）
            sort_by: 排序方式
            
        Returns:
            AcademicSearchResult: 搜索结果
        """
        params = {
            "search_query": f"all:{query}",
            "start": start,
            "max_results": min(max_results, 100),
            "sortBy": sort_by
        }
        
        url = f"{self.ARXIV_API}?{urlencode(params)}"
        data = await self._make_request(url, return_xml=True)
        
        papers = []
        if isinstance(data, dict) and "feed" in data:
            entries = data.get("feed", {})
            if isinstance(entries, dict):
                entries = entries.get("entry", [])
            if isinstance(entries, list):
                for entry in entries:
                    paper = self._parse_arxiv_paper(entry)
                    papers.append(paper)
        
        total = len(papers)  # arXiv API 不返回总数
        
        return AcademicSearchResult(
            total=total,
            papers=papers,
            offset=start,
            next_offset=None
        )
    
    def _parse_arxiv_paper(self, entry: dict) -> Paper:
        """解析 arXiv API 返回的论文数据"""
        if not isinstance(entry, dict):
            entry = {}
        
        arxiv_id = ""
        if "id" in entry and isinstance(entry["id"], str):
            arxiv_id = entry["id"].split("/")[-1]
        
        authors = []
        if "author" in entry:
            author_list = entry["author"]
            if isinstance(author_list, list):
                for a in author_list:
                    if isinstance(a, dict):
                        authors.append(a.get("name", ""))
                    elif isinstance(a, str):
                        authors.append(a)
            elif isinstance(author_list, str):
                authors = [author_list]
        
        summary = entry.get("summary", "") if isinstance(entry.get("summary"), str) else ""
        if summary:
            summary = summary.replace("\n", " ").strip()
        
        keywords = []
        if "category" in entry:
            categories = entry["category"]
            if isinstance(categories, list):
                for c in categories:
                    if isinstance(c, dict):
                        keywords.append(c.get("term", ""))
                    elif isinstance(c, str):
                        keywords.append(c)
            elif isinstance(categories, str):
                keywords = [categories]
        
        pdf_url = ""
        if "link" in entry:
            link_list = entry["link"]
            if isinstance(link_list, list):
                for link in link_list:
                    if isinstance(link, dict) and link.get("type") == "application/pdf":
                        pdf_url = link.get("href", "")
                        break
        
        published = entry.get("published", "") if isinstance(entry.get("published"), str) else ""
        year = 2024
        if published:
            try:
                year = int(published[:4])
            except:
                pass
        
        title = entry.get("title", "") if isinstance(entry.get("title"), str) else ""
        if title:
            title = title.replace("\n", " ").strip()
        
        return Paper(
            paper_id=arxiv_id,
            title=title,
            authors=authors,
            abstract=summary,
            year=year,
            venue="arXiv",
            citation_count=0,
            influential_citation_count=0,
            arxiv_id=arxiv_id,
            url=pdf_url or entry.get("id", ""),
            keywords=keywords,
            open_access_pdf=pdf_url
        )
    
    async def get_paper_by_id(
        self, 
        paper_id: str, 
        source: str = "semantic_scholar"
    ) -> Optional[Paper]:
        """
        根据论文 ID 获取详细信息
        
        Args:
            paper_id: 论文 ID
            source: 数据来源 ("semantic_scholar" 或 "arxiv")
            
        Returns:
            Paper 或 None
        """
        if source == "semantic_scholar":
            fields = [
                "paperId", "title", "authors", "abstract", "year",
                "venue", "citationCount", "influentialCitationCount",
                "doi", "arxivId", "url", "keywords", "references",
                "citations", "openAccessPdf", "fieldsOfStudy"
            ]
            url = f"{self.SEMANTIC_SCHOLAR_API}/paper/{paper_id}"
            params = {"fields": ",".join(fields)}
            
            headers = {}
            if self.semantic_scholar_api_key:
                headers["x-api-key"] = self.semantic_scholar_api_key
            
            data = await self._make_request(url, params, headers)
            if data:
                return self._parse_semantic_scholar_paper(data)
        
        return None
    
    async def get_paper_citations(
        self,
        paper_id: str,
        max_results: int = 20
    ) -> list[Paper]:
        """
        获取论文的引用列表（被这篇论文引用的论文）
        
        Args:
            paper_id: 论文 ID
            max_results: 最大返回数量
            
        Returns:
            引用论文列表
        """
        fields = [
            "paperId", "title", "authors", "abstract", "year",
            "venue", "citationCount", "influentialCitationCount"
        ]
        
        url = f"{self.SEMANTIC_SCHOLAR_API}/paper/{paper_id}/references"
        params = {
            "fields": ",".join(fields),
            "limit": min(max_results, 100)
        }
        
        headers = {}
        if self.semantic_scholar_api_key:
            headers["x-api-key"] = self.semantic_scholar_api_key
        
        data = await self._make_request(url, params, headers)
        
        papers = []
        if isinstance(data, dict) and "data" in data:
            for item in data["data"]:
                if not isinstance(item, dict):
                    continue
                if "citedPaper" in item and item["citedPaper"] and isinstance(item["citedPaper"], dict):
                    paper = self._parse_semantic_scholar_paper(item["citedPaper"])
                    papers.append(paper)
        
        return papers
    
    async def get_paper_cited_by(
        self,
        paper_id: str,
        max_results: int = 20
    ) -> list[Paper]:
        """
        获取引用该论文的所有论文列表
        
        Args:
            paper_id: 论文 ID
            max_results: 最大返回数量
            
        Returns:
            引用该论文的论文列表
        """
        fields = [
            "paperId", "title", "authors", "abstract", "year",
            "venue", "citationCount", "influentialCitationCount"
        ]
        
        url = f"{self.SEMANTIC_SCHOLAR_API}/paper/{paper_id}/citations"
        params = {
            "fields": ",".join(fields),
            "limit": min(max_results, 100)
        }
        
        headers = {}
        if self.semantic_scholar_api_key:
            headers["x-api-key"] = self.semantic_scholar_api_key
        
        data = await self._make_request(url, params, headers)
        
        papers = []
        if isinstance(data, dict) and "data" in data:
            for item in data["data"]:
                if not isinstance(item, dict):
                    continue
                if "citingPaper" in item and item["citingPaper"] and isinstance(item["citingPaper"], dict):
                    paper = self._parse_semantic_scholar_paper(item["citingPaper"])
                    papers.append(paper)
        
        return papers
    
    async def search_multiple(
        self,
        query: str,
        max_results: int = 10,
        sources: Optional[list[str]] = None
    ) -> AcademicSearchResult:
        """
        同时搜索多个学术数据库
        
        Args:
            query: 搜索查询
            max_results: 最大返回数量
            sources: 数据源列表，默认 ["semantic_scholar", "arxiv"]
            
        Returns:
            合并后的搜索结果
        """
        if sources is None:
            sources = ["arxiv"]
        
        tasks = []
        if "semantic_scholar" in sources:
            tasks.append(self.search_semantic_scholar(query, max_results))
        if "arxiv" in sources:
            tasks.append(self.search_arxiv(query, max_results))
        
        results = await asyncio.gather(*tasks)
        
        all_papers = []
        for result in results:
            all_papers.extend(result.papers)
        
        # 去重（基于论文 ID）
        seen_ids = set()
        unique_papers = []
        for paper in all_papers:
            if paper.paper_id and paper.paper_id not in seen_ids:
                seen_ids.add(paper.paper_id)
                unique_papers.append(paper)
        
        return AcademicSearchResult(
            total=len(unique_papers),
            papers=unique_papers[:max_results],
            offset=0,
            next_offset=None
        )


from pydantic import ConfigDict

# 全局单例
_academic_search_instance: Optional[AcademicSearchTool] = None


def get_academic_search_tool() -> AcademicSearchTool:
    """获取学术搜索工具单例"""
    global _academic_search_instance
    if _academic_search_instance is None:
        _academic_search_instance = AcademicSearchTool()
    return _academic_search_instance


async def close_academic_search_tool():
    """关闭学术搜索工具"""
    global _academic_search_instance
    if _academic_search_instance:
        await _academic_search_instance.close()
        _academic_search_instance = None
