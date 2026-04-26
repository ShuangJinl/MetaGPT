#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

SOFTWARE_INTENT_KEYWORDS = {
    "build",
    "create",
    "develop",
    "implement",
    "design",
    "code",
    "app",
    "website",
    "web",
    "game",
    "system",
    "platform",
    "tool",
    "api",
    "backend",
    "frontend",
    "cli",
    "agent",
    "project",
    "软件",
    "系统",
    "应用",
    "开发",
    "实现",
    "网站",
    "游戏",
    "项目",
}

PAPER_RESEARCH_PATTERNS = (
    r"\b(search|find|look\s+for|explore|survey|review|research|analyze|summarize)\b.*\b(paper|papers|literature|essay|essays|article|articles)\b",
    r"\b(paper|papers|literature|essay|essays|article|articles)\b.*\b(search|find|review|survey|research|analysis|summarize)\b",
    r"\b(topic|subject|field)\s+is\s+[\w\s\-]+",
    r"\bstate\s+of\s+the\s+art\b",
    r"(检索|搜索|查找|调研|综述|总结|分析).*(论文|文献|文章|essay)",
    r"(论文|文献|文章|essay).*(检索|搜索|调研|综述|分析|总结)",
)

SOFTWARE_INTENT_PATTERNS = (
    r"\b(build|create|develop|implement|design|code)\b.*\b(app|website|system|platform|tool|api|game|project|software)\b",
    r"\b(app|website|system|platform|tool|api|game|project|software)\b.*\b(build|create|develop|implement|design|code)\b",
    r"(开发|实现|设计|编写).*(软件|系统|应用|网站|工具|接口|项目|游戏)",
)


TOPIC_EXTRACTION_PATTERNS = (
    r"\btopic\s+is\s+(?P<topic>.+)$",
    r"\bsubject\s+is\s+(?P<topic>.+)$",
    r"\b(?:essay|paper|papers|article|articles|literature)\s+of\s+(?P<topic>.+)$",
    r"\b(?:essay|paper|papers|article|articles|literature)\s+on\s+(?P<topic>.+)$",
    r"\b(?:essay|paper|papers|article|articles|literature)\s+about\s+(?P<topic>.+)$",
    r"\bfind\s+me\s+(?:the\s+)?(?:essay|paper|papers|article|articles|literature)\s+of\s+(?P<topic>.+)$",
    r"\babout\s+(?P<topic>.+)$",
    r"\bon\s+(?P<topic>.+)$",
    r"(?:检索|搜索|查找|调研|综述|总结|分析).*(?:论文|文献|文章|essay).*(?:主题|话题)[是为:]*(?P<topic>.+)$",
    r"(?:关于|围绕)(?P<topic>.+?)(?:的)?(?:论文|文献|文章|essay)",
)


FILLER_PREFIX_PATTERNS = (
    r"^i\s+want\s+to\s+",
    r"^please\s+",
    r"^can\s+you\s+",
    r"^help\s+me\s+",
    r"^find\s+me\s+",
    r"^(?:the\s+)?essay\s+of\s+",
    r"^(?:the\s+)?paper\s+of\s+",
)

TOPIC_NORMALIZATION_MAP = {
    "software engining": "software engineering",
}

LITERATURE_REVIEW_KEYWORDS = {
    "paper",
    "papers",
    "literature",
    "research",
    "survey",
    "sota",
    "state-of-the-art",
    "state of the art",
    "academic",
    "论文",
    "文献",
    "调研",
    "综述",
    "学术",
}


def looks_like_paper_research_topic(idea: str) -> bool:
    """Infer whether input should route to paper research workflow."""
    normalized = idea.strip().lower()
    if not normalized:
        return False

    has_paper_intent = any(re.search(pattern, normalized) for pattern in PAPER_RESEARCH_PATTERNS)
    has_software_intent = any(re.search(pattern, normalized) for pattern in SOFTWARE_INTENT_PATTERNS)
    if has_paper_intent and not has_software_intent:
        return True
    if has_software_intent and not has_paper_intent:
        return False

    tokens = re.findall(r"[\w\u4e00-\u9fff]+", normalized)
    if not tokens:
        return False

    has_software_keywords = any(token in SOFTWARE_INTENT_KEYWORDS for token in tokens)
    if has_software_keywords and not has_paper_intent:
        return False

    # Fallback: short noun-like topic phrases default to paper research.
    is_short_phrase = len(tokens) <= 10
    has_terminal_punctuation = normalized.endswith((".", "?", "!", "。", "？", "！"))
    return is_short_phrase and not has_terminal_punctuation


def extract_paper_research_topic(idea: str) -> str:
    """Extract clean research topic from natural language request."""
    topic = idea.strip()
    if not topic:
        return topic

    normalized = topic.lower().strip()
    for filler_pattern in FILLER_PREFIX_PATTERNS:
        normalized = re.sub(filler_pattern, "", normalized).strip()

    for pattern in TOPIC_EXTRACTION_PATTERNS:
        match = re.search(pattern, normalized)
        if match and match.groupdict().get("topic"):
            candidate = match.group("topic").strip(" .,!?:;\"'，。！？；：")
            if candidate:
                for wrong, correct in TOPIC_NORMALIZATION_MAP.items():
                    candidate = candidate.replace(wrong, correct)
                return candidate

    normalized = normalized.strip(" .,!?:;\"'，。！？；：")
    for wrong, correct in TOPIC_NORMALIZATION_MAP.items():
        normalized = normalized.replace(wrong, correct)
    return normalized


def should_trigger_literature_review(idea: str) -> bool:
    """Decide whether software collaboration should run literature pre-review."""
    normalized = idea.lower()
    if any(keyword in normalized for keyword in LITERATURE_REVIEW_KEYWORDS):
        return True
    return bool(re.search(r"\b(sota|state\s+of\s+the\s+art|evidence-based|research-backed)\b", normalized))
