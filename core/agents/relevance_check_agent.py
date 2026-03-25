from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import GlobalConfig, UserConfig
    from core.models import PaperCandidate

from core.llm import get_llm


@dataclass
class RelevanceAnalysis:
    """LLM对论文相关性的分析结果。"""

    paper_id: str  # 论文标识
    is_relevant: bool  # 是否相关
    relevance_score: float  # 0-1，细粒度评分
    matched_interest: str  # 匹配的具体兴趣
    match_confidence: str  # "high" | "medium" | "low"
    reasoning: str  # 分析理由
    actual_field: str  # 论文实际所属领域
    mismatched_fields: list[str]  # 可能误判的字段


@dataclass
class BatchRelevanceResult:
    """一批论文的相关性分析结果。"""

    analyses: list[RelevanceAnalysis]
    processed_count: int
    error_count: int


class RelevanceCheckAgent:
    """使用LLM批量验证论文与用户兴趣相关性的Agent。"""

    def __init__(
        self,
        global_config: GlobalConfig | None = None,
        user_config: UserConfig | None = None,
        model: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self._llm = get_llm(
            model=model,
            api_base=api_base,
            global_config=global_config,
            user_config=user_config,
        )

    def analyze_batch(
        self,
        papers: list[PaperCandidate],
        interests: list[str],
        threshold: float = 0.6,
    ) -> BatchRelevanceResult:
        """
        批量分析论文与用户兴趣的相关性。

        Args:
            papers: 候选论文列表（一批，建议10-15篇）
            interests: 用户兴趣列表
            threshold: 相关性阈值，低于此值视为不相关

        Returns:
            批量分析结果
        """
        if not papers or not interests:
            return BatchRelevanceResult(analyses=[], processed_count=0, error_count=0)

        # 构建论文列表文本
        papers_text = ""
        for i, paper in enumerate(papers, 1):
            papers_text += f"\n[{i}] Title: {paper.title}\n"
            papers_text += f"    Abstract: {paper.abstract[:500]}{'...' if len(paper.abstract) > 500 else ''}\n"
            papers_text += f"    Source: {paper.source}\n"

        interests_text = "\n".join(f"- {interest}" for interest in interests)

        prompt = f"""你是一位学术研究专家，精通各学科领域的术语体系和研究方法。你的任务是分析一批候选论文，判断它们是否与用户的研究兴趣真正相关。

## 用户研究兴趣
{interests_text}

## 待分析的候选论文
{papers_text}

## 分析要求
对于每篇论文，请深入分析：

1. **核心研究领域识别**
   - 这篇论文实际属于什么领域？（用1-2个词概括，如"computational geometry", "medical imaging", "financial economics"）

2. **兴趣匹配判断**
   - 是否与任何用户兴趣真正相关？
   - 注意：标题含关键词不代表内容相关！例如标题有"factor"但讲几何算法的，应判定为不相关

3. **相关性评分** (0-1)
   - 0.0-0.3: 不相关（主题完全不同）
   - 0.4-0.6: 弱相关（边缘相关或跨学科但非核心）
   - 0.7-0.8: 相关（符合兴趣领域）
   - 0.9-1.0: 高度相关（核心主题匹配）

4. **匹配的兴趣**
   - 如果相关，匹配哪个具体兴趣？
   - 如果不相关，写"none"

5. **置信度**
   - "high": 判断有把握
   - "medium": 判断较有把握但存在一定模糊性
   - "low": 判断不确定（摘要太短或太模糊）

6. **理由说明**
   - 简要说明为什么相关/不相关
   - 如果误判风险高，说明可能误判为什么领域

## 输出格式
输出JSON数组，每篇论文一个对象：
[
  {{
    "paper_index": 1,
    "is_relevant": true/false,
    "relevance_score": 0.85,
    "matched_interest": "factor investing",
    "match_confidence": "high",
    "actual_field": "financial economics",
    "reasoning": "论文讨论多因子模型在资产配置中的应用，属于量化金融核心主题",
    "mismatched_fields": []
  }},
  {{
    "paper_index": 2,
    "is_relevant": false,
    "relevance_score": 0.15,
    "matched_interest": "none",
    "match_confidence": "high",
    "actual_field": "computational geometry",
    "reasoning": "虽然标题有factor，但实际研究几何算法中的稀疏化技术，与金融无关",
    "mismatched_fields": ["computational geometry", "graph algorithms"]
  }},
  ...
]

重要提示：
- 严格基于摘要内容判断，不要被标题中的个别词误导
- 金融领域的factor investing与数学/CS领域的factorization是完全不同的概念
- 当摘要涉及机器学习在金融中的应用时，需判断是否真正用于金融数据（而非医疗图像等其他领域）

只输出JSON，不要其他解释。"""

        analyses = []
        error_count = 0

        try:
            response = self._llm.complete(prompt)
            content = response.content.strip()

            # 提取JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            results = json.loads(content)

            for result in results:
                try:
                    idx = result.get("paper_index", 0) - 1
                    if 0 <= idx < len(papers):
                        paper = papers[idx]
                        analysis = RelevanceAnalysis(
                            paper_id=paper.paper_id or str(idx),
                            is_relevant=result.get("is_relevant", False),
                            relevance_score=result.get("relevance_score", 0.0),
                            matched_interest=result.get("matched_interest", "none"),
                            match_confidence=result.get("match_confidence", "low"),
                            reasoning=result.get("reasoning", ""),
                            actual_field=result.get("actual_field", "unknown"),
                            mismatched_fields=result.get("mismatched_fields", []),
                        )
                        analyses.append(analysis)
                except Exception as e:
                    error_count += 1

        except Exception as e:
            # 如果LLM调用失败，返回所有论文为未知状态
            for paper in papers:
                analyses.append(
                    RelevanceAnalysis(
                        paper_id=paper.paper_id or "unknown",
                        is_relevant=True,  # 失败时保守处理，不过滤
                        relevance_score=0.5,
                        matched_interest="unknown",
                        match_confidence="low",
                        reasoning=f"LLM analysis failed: {e}",
                        actual_field="unknown",
                        mismatched_fields=[],
                    )
                )
            error_count = len(papers)

        return BatchRelevanceResult(
            analyses=analyses,
            processed_count=len(analyses),
            error_count=error_count,
        )

    def analyze_papers(
        self,
        papers: list[PaperCandidate],
        interests: list[str],
        batch_size: int = 12,
        threshold: float = 0.6,
    ) -> list[RelevanceAnalysis]:
        """
        分批分析大量论文。

        Args:
            papers: 所有候选论文
            interests: 用户兴趣列表
            batch_size: 每批处理的论文数（默认12）
            threshold: 相关性阈值

        Returns:
            所有论文的分析结果
        """
        all_analyses = []

        for i in range(0, len(papers), batch_size):
            batch = papers[i : i + batch_size]
            result = self.analyze_batch(batch, interests, threshold)
            all_analyses.extend(result.analyses)

        return all_analyses
