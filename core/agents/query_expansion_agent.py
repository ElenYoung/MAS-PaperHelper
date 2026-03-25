from __future__ import annotations

import json
from dataclasses import dataclass

from core.config import GlobalConfig, UserConfig
from core.llm import get_llm


@dataclass
class QueryStrategy:
    """结构化查询策略。"""

    interest: str
    core_keywords: list[str]
    domain_constraints: list[str]
    exclude_keywords: list[str]
    source_specific_queries: dict[str, str]


class QueryExpansionAgent:
    """使用LLM将用户兴趣扩展为结构化搜索策略的Agent。"""

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

    def expand(self, user: UserConfig, max_keywords: int = 5) -> list[QueryStrategy]:
        """
        为用户的每个兴趣生成结构化查询策略。

        Args:
            user: 用户配置
            max_keywords: 每个兴趣扩展的最大关键词数

        Returns:
            每个兴趣对应的查询策略列表
        """
        if not user.interests:
            return []

        interests_text = "\n".join(f"- {interest}" for interest in user.interests)

        prompt = f"""你是一位学术研究专家，精通各学科领域的术语体系和研究方法。

请为以下每个研究兴趣生成结构化的搜索策略，用于在学术数据库（arXiv、Semantic Scholar等）中检索相关论文。

## 用户研究兴趣
{interests_text}

## 任务要求
对于每个兴趣，请分析并生成：

1. **core_keywords**: 该领域的核心术语和同义词（{max_keywords}个以内）
   - 包含英文术语的标准表达
   - 包含密切相关的同义词或变体

2. **domain_constraints**: 该兴趣所属的领域/学科（用于限定搜索范围）
   - 例如："finance", "quantitative finance", "computer science", "machine learning"

3. **exclude_keywords**: 应排除的关键词（防止语义漂移）
   - 识别容易与该兴趣混淆的其他领域
   - 例如factor investing应排除"medical", "biological", "image processing"

4. **source_specific_queries**: 为不同数据源优化的查询字符串
   - arxiv: 适合arXiv搜索语法的查询
   - semantic_scholar: 适合Semantic Scholar的查询
   - google_scholar: 适合Google Scholar的查询

## 输出格式
输出JSON数组，每个兴趣一个对象：
[
  {{
    "interest": "原始兴趣名称",
    "core_keywords": ["term1", "term2", ...],
    "domain_constraints": ["field1", "field2", ...],
    "exclude_keywords": ["exclude1", "exclude2", ...],
    "source_specific_queries": {{
      "arxiv": "query string",
      "semantic_scholar": "query string",
      "google_scholar": "query string"
    }}
  }},
  ...
]

## 示例
对于interest "factor investing":
- core_keywords: ["factor investing", "factor models", "smart beta", "asset pricing factors", "FF model"]
- domain_constraints: ["finance", "asset management", "quantitative finance"]
- exclude_keywords: ["image", "medical", "biological", "ecological"]
- source_specific_queries.arxiv: "factor investing OR factor models OR smart beta OR asset pricing factors"
- source_specific_queries.semantic_scholar: "factor investing finance asset pricing quantitative"

请确保生成的搜索策略专业、准确，能有效过滤不相关领域的论文。只输出JSON，不要其他解释。"""

        try:
            response = self._llm.complete(prompt)
            content = response.content.strip()

            # 提取JSON内容（处理可能的markdown代码块）
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            strategies_data = json.loads(content)

            strategies = []
            for item in strategies_data:
                strategy = QueryStrategy(
                    interest=item["interest"],
                    core_keywords=item.get("core_keywords", []),
                    domain_constraints=item.get("domain_constraints", []),
                    exclude_keywords=item.get("exclude_keywords", []),
                    source_specific_queries=item.get("source_specific_queries", {}),
                )
                strategies.append(strategy)

            return strategies

        except Exception as e:
            # Fallback: 返回简单的关键词扩展
            return self._fallback_expand(user)

    def _fallback_expand(self, user: UserConfig) -> list[QueryStrategy]:
        """当LLM调用失败时的简单回退。"""
        strategies = []
        for interest in user.interests:
            # 简单的同义词映射
            synonyms = self._get_simple_synonyms(interest)
            strategies.append(
                QueryStrategy(
                    interest=interest,
                    core_keywords=[interest] + synonyms,
                    domain_constraints=[],
                    exclude_keywords=[],
                    source_specific_queries={
                        "arxiv": " OR ".join(f'"{k}"' for k in [interest] + synonyms),
                        "semantic_scholar": f"{interest} {' '.join(synonyms[:2])}",
                        "google_scholar": f"{interest} {' '.join(synonyms[:2])} research paper",
                    },
                )
            )
        return strategies

    def _get_simple_synonyms(self, interest: str) -> list[str]:
        """简单的同义词映射表。"""
        synonym_map = {
            "factor investing": ["smart beta", "factor models", "asset pricing factors"],
            "options pricing": ["option valuation", "derivatives pricing", "Black-Scholes"],
            "market microstructure": ["market structure", "trading mechanism", "price formation"],
            "high frequency trading": ["HFT", "algorithmic trading", "electronic trading"],
            "quantitative trading": ["quant trading", "systematic trading", "algo trading"],
            "reinforcement learning": ["RL", "policy learning", "actor-critic"],
            "machine learning": ["ML", "statistical learning", "deep learning"],
            "time series forecasting": ["time series prediction", "sequential forecasting", "temporal modeling"],
            "risk premia": ["risk premium", "excess returns", "factor risk"],
        }
        return synonym_map.get(interest.lower(), [])
