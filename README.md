# MAS-PaperHelper

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg?style=flat-square" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License: MIT">
  <img src="https://img.shields.io/badge/FastAPI-Web%20UI-orange.svg?style=flat-square" alt="FastAPI Web UI">
</p>

<p align="center">
  <i>Multi-Agent System for Intelligent Paper Discovery & Summarization</i><br>
  <b>多源学术文献智能推荐与前沿捕捉系统</b>
</p>

---

## English

### Features

MAS-PaperHelper is a configurable multi-agent literature assistant that helps researchers efficiently track cutting-edge research:

| Module | Feature |
|--------|---------|
| 🔍 **Multi-Source Discovery** | Parallel search across arXiv, Semantic Scholar, Google Scholar |
| 🎯 **Intelligent Ranking** | Weighted scoring based on relevance and recency |
| 📄 **PDF Parsing** | Automatic download and parsing to structured Markdown |
| 🤖 **AI Summarization** | Auto-extract research problems and innovations |
| 📚 **Knowledge Base** | Keyword learning and expanded interest management |
| 🗃️ **History Archive** | Searchable paper history database |
| ⏰ **Scheduled Tasks** | Auto-run by hour/day/week |

### Quick Start

#### Requirements

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) package manager

#### Installation

```bash
# Clone repository
git clone <repository-url>
cd MAS-PaperHelper

# Create virtual environment
uv venv --python 3.12

# Install dependencies
uv sync --extra dev

# Optional components (install as needed)
uv sync --extra google      # Google Scholar support
uv sync --extra vector      # Vector database support
uv sync --extra database    # ClickHouse support
```

#### Configuration

```bash
cp config/config.yaml.example config/config.yaml
```

Edit `config/config.yaml`:

```yaml
# LLM configuration (choose one)
global:
  # Local deployment (recommended)
  llm_provider: openai
  base_model: Qwen/Qwen3-Next-80B-A3B-Instruct
  base_model_api_base: http://127.0.0.1:8000/v1

  # Or commercial API
  # llm_provider: openai
  # base_model: gpt-4o-mini
  # llm_api_key_env: OPENAI_API_KEY

# PDF parser selection
global:
  # 💡 Use pypdf without GPU
  parser_backend: pypdf

  # 💡 Use docling with NVIDIA GPU for better quality
  # parser_backend: docling
  # parser_device: cuda
  # parser_max_pages: 15
```

#### Launch

**CLI Mode**

```bash
# Run once
uv run python scripts/main.py run-once --user-id quant

# Scheduled loop
uv run python scripts/main.py schedule --interval-seconds 300
```

**Web UI**

```bash
uv run uvicorn web.app:app --reload --host 0.0.0.0 --port 8000
```

Visit http://127.0.0.1:8000

### Workflow

```
Discovery (Multi-source) → Ranking (Relevance) → Download (PDF)
                                                       ↓
Archive (Storage) ← Summary (AI) ← Parse (Text)
```

### Configuration Guide

#### Example: Quantitative Finance Tracking

```yaml
global:
  recency_window_days: 60           # Last 2 months
  discovery_limit_per_source: 20    # 20 papers per source
  use_llm_summary: true             # Enable AI summary
  summary_language: en              # English output

  # PDF parser selection
  parser_backend: pypdf             # CPU-friendly

  # Expanded interests control
  auto_query_from_interests: true
  auto_query_mode: interests
  keyword_kb_enabled: true
  keyword_whitelist:
    - quantitative trading
    - market microstructure
    - high frequency trading

users:
  - user_id: quant
    interests:
      - quantitative trading
      - market microstructure
      - high frequency trading
    enabled_sources:
      - arxiv
      - semantic_scholar
    update_frequency: daily
```

#### PDF Parser Comparison

| Backend | Hardware | Speed | Quality | Use Case |
|---------|----------|-------|---------|----------|
| **pypdf** | CPU only | ⚡ Fast | ⭐⭐⭐ | No GPU, quick processing |
| **docling** | CUDA GPU | 🚀 Medium | ⭐⭐⭐⭐⭐ | GPU available, high quality |

💡 **Selection Guide**
- No dedicated GPU → Use `pypdf`
- NVIDIA GPU with ≥ 8GB VRAM → Use `docling`

### UI Preview

#### Config Page
- One-click workflow execution
- Scheduler control
- Data source enable/disable
- Real-time expanded interests editing

#### Results Page
- Grouped by interest
- Collapsible detail panels
- Math formula rendering

#### History Page
- Full-text search
- Multi-user filtering
- Permanent archive

### FAQ

<details>
<summary><b>❌ No candidates pass threshold</b></summary>

- Lower `ranking_threshold` (e.g., 4.0)
- Lower `min_relevance_ratio` (e.g., 0.05)
- Increase `discovery_limit_per_source` (e.g., 50)
</details>

<details>
<summary><b>📝 Poor summary quality</b></summary>

- Confirm `use_llm_summary: true`
- Adjust `summary_max_chars` (default 1000)
- Switch parser backend (docling for GPU, pypdf for CPU)
- Check LLM service response
</details>

<details>
<summary><b>🔌 No results from a data source</b></summary>

- Check `enabled: true`
- Confirm user's `enabled_sources` includes it
- Run `uv run python scripts/main.py doctor` to diagnose
- Check network and API limits
</details>

### Development

```bash
# Run tests
uv run pytest -q

# Code linting
uv run ruff check .
```

---

## 中文 (Chinese)

### 功能特性

MAS-PaperHelper 是一个可配置的多智能体文献助手，帮助研究者高效追踪领域前沿：

| 模块 | 功能 |
|------|------|
| 🔍 **多源发现** | arXiv、Semantic Scholar、Google Scholar 等并行检索 |
| 🎯 **智能排序** | 基于相关性与时效性的加权评分 |
| 📄 **PDF 解析** | 自动下载并解析为结构化 Markdown |
| 🤖 **AI 摘要** | 自动提取研究问题与创新点 |
| 📚 **知识库** | 关键词学习与扩展兴趣管理 |
| 🗃️ **历史归档** | 可搜索的论文历史数据库 |
| ⏰ **定时任务** | 支持按小时/天/周自动执行 |

### 快速开始

#### 环境要求

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) 包管理器

#### 安装

```bash
# 克隆仓库
git clone <repository-url>
cd MAS-PaperHelper

# 创建虚拟环境
uv venv --python 3.12

# 安装依赖
uv sync --extra dev

# 可选组件（按需安装）
uv sync --extra google      # Google Scholar 支持
uv sync --extra vector      # 向量数据库支持
uv sync --extra database    # ClickHouse 支持
```

#### 配置

```bash
cp config/config.yaml.example config/config.yaml
```

编辑 `config/config.yaml`：

```yaml
# LLM 配置（二选一）
global:
  # 本地部署（推荐）
  llm_provider: openai
  base_model: Qwen/Qwen3-Next-80B-A3B-Instruct
  base_model_api_base: http://127.0.0.1:8000/v1

  # 或商业 API
  # llm_provider: openai
  # base_model: gpt-4o-mini
  # llm_api_key_env: OPENAI_API_KEY

# PDF 解析器选择
global:
  # 💡 无 GPU 推荐使用 pypdf
  parser_backend: pypdf

  # 💡 有 NVIDIA GPU 推荐使用 docling 获得更好效果
  # parser_backend: docling
  # parser_device: cuda
  # parser_max_pages: 15
```

#### 启动

**命令行模式**

```bash
# 单次执行
uv run python scripts/main.py run-once --user-id quant

# 定时循环
uv run python scripts/main.py schedule --interval-seconds 300
```

**Web 界面**

```bash
uv run uvicorn web.app:app --reload --host 0.0.0.0 --port 8000
```

访问 http://127.0.0.1:8000

### 工作流程

```
Discovery (多源检索) → Ranking (相关性排序) → Download (PDF下载)
                                                        ↓
Archive (归档存储) ← Summary (AI摘要) ← Parse (文本解析)
```

### 配置详解

#### 推荐配置：量化金融追踪

```yaml
global:
  recency_window_days: 60           # 近2个月文献
  discovery_limit_per_source: 20    # 每源检索20篇
  use_llm_summary: true             # 启用AI摘要
  summary_language: zh              # 中文输出

  # PDF解析器选择
  parser_backend: pypdf             # CPU友好

  # 扩展兴趣控制
  auto_query_from_interests: true
  auto_query_mode: interests
  keyword_kb_enabled: true
  keyword_whitelist:
    - quantitative trading
    - market microstructure
    - high frequency trading

users:
  - user_id: quant
    interests:
      - quantitative trading
      - market microstructure
      - high frequency trading
    enabled_sources:
      - arxiv
      - semantic_scholar
    update_frequency: daily
```

#### PDF 解析器对比

| 后端 | 硬件要求 | 速度 | 质量 | 推荐场景 |
|------|----------|------|------|----------|
| **pypdf** | CPU 即可 | ⚡ 快 | ⭐⭐⭐ | 无GPU、快速处理 |
| **docling** | CUDA GPU | 🚀 中等 | ⭐⭐⭐⭐⭐ | 有GPU、高质量需求 |

💡 **选择建议**
- 无独立显卡 → 使用 `pypdf`
- 有 NVIDIA GPU 且显存 ≥ 8GB → 使用 `docling`

### 界面预览

#### 配置页面
- 一键运行工作流
- 定时调度器控制
- 数据源启停管理
- 扩展兴趣实时编辑

#### 结果页面
- 按兴趣分组展示
- 可折叠详情面板
- 数学公式渲染支持

#### 历史页面
- 全文检索
- 多用户筛选
- 永久归档

### 常见问题

<details>
<summary><b>❌ 无候选论文通过阈值</b></summary>

- 降低 `ranking_threshold`（如 4.0）
- 降低 `min_relevance_ratio`（如 0.05）
- 增加 `discovery_limit_per_source`（如 50）
</details>

<details>
<summary><b>📝 摘要质量不佳</b></summary>

- 确认 `use_llm_summary: true`
- 调整 `summary_max_chars`（默认 1000）
- 切换解析器后端（GPU用docling，CPU用pypdf）
- 检查 LLM 服务是否正常响应
</details>

<details>
<summary><b>🔌 某数据源无结果</b></summary>

- 检查 `enabled: true`
- 确认用户 `enabled_sources` 包含该源
- 运行 `uv run python scripts/main.py doctor` 诊断
- 检查网络连接与API限制
</details>

### 开发

```bash
# 运行测试
uv run pytest -q

# 代码检查
uv run ruff check .
```

---

## Search Algorithm & Ranking Parameters / 搜索算法与排序参数详解

### Overview / 概述

MAS-PaperHelper implements a **two-stage search architecture** with optional LLM enhancement:

```
Stage 1: Discovery (Candidate Retrieval)
    ├── Simple Mode: Keyword-based search from multiple sources
    └── LLM-Enhanced Mode: LLM expands queries + semantic filtering

Stage 2: Ranking & Filtering
    ├── Relevance Scoring (TF-IDF + keyword matching)
    ├── Recency Scoring (time-decay weighting)
    └── LLM Relevance Verification (optional, batch processing)
```

### Detailed Score Calculation / 详细分数计算

#### 1. Relevance Score (相关性分数)

**Purpose**: Measures how well the paper matches user interests using keyword and phrase matching.

**Calculation Steps**:

```python
# Step 1: Extract text and tokens
text = (title + " " + abstract).lower()
interest_tokens = [token.lower().strip() for token in user.interests]
primary_interests = interest_tokens[:2]  # First 2 interests get priority

# Step 2: Calculate phrase hits
phrase_hits = count of interest_tokens that appear as substring in text

# Step 3: Calculate keyword hits (word-level matching)
keyword_set = extract_words(interest_tokens) - stopwords
text_words = set(re.findall(r"[a-zA-Z]{3,}", text))
keyword_hits = |keyword_set ∩ text_words|

# Step 4: Primary keyword hits (first 2 interests weighted higher)
primary_keyword_set = extract_words(primary_interests) - stopwords
primary_keyword_hits = |primary_keyword_set ∩ text_words|

# Step 5: Compute relevance ratio
if interest_tokens:
    phrase_ratio = phrase_hits / len(interest_tokens)
    keyword_ratio = min(1.0, keyword_hits / 3.0)
    relevance = max(phrase_ratio, keyword_ratio)

    # Boost by primary interests (15% weight)
    if primary_keyword_set:
        primary_ratio = primary_keyword_hits / len(primary_keyword_set)
        relevance = min(1.0, relevance * 0.85 + primary_ratio * 0.15)
else:
    relevance = 0.5

# Step 6: Apply penalties
if no phrase hits and no keyword hits:
    recency *= 0.2  # Heavy penalty - almost no match
if no keyword hits:
    relevance *= 0.9  # Slight penalty
    recency *= 0.95
```

**Key Points**:
- **Phrase matching**: Full interest string appearing in text (e.g., "factor investing")
- **Keyword matching**: Individual words (3+ chars) from interests appearing in text
- **Primary interests**: First 2 interests get 15% extra weight
- **Penalty**: Papers with zero keyword overlap get score reduced by 10%

---

#### 2. Recency Score (时效性分数)

**Purpose**: Measures how recent the paper is, with linear decay over time.

**Formula**:
```python
age_days = max(0, today - published_at)
recency = max(0.0, 1.0 - min(age_days / recency_window_days, 1.0))
```

**Examples** (with `recency_window_days = 60`):

| Age | Calculation | Recency Score |
|-----|-------------|---------------|
| 0 days (today) | 1.0 - 0/60 | **1.0** |
| 15 days | 1.0 - 15/60 | **0.75** |
| 30 days | 1.0 - 30/60 | **0.5** |
| 60 days | 1.0 - 60/60 | **0.0** |
| 90 days | 1.0 - min(90/60, 1.0) | **0.0** |

**Penalty**: If paper has no keyword overlap with interests, recency is reduced to 20% of its value.

---

#### 3. Final Score (0-10 scale)

**Formula**:
```python
final_score = 10 × (relevance_weight × relevance_score + recency_weight × recency_score)
```

**Default** (`relevance_weight = 0.5`, `recency_weight = 0.5`):
```
final_score = 10 × (0.5 × relevance + 0.5 × recency)
```

**Example Calculation**:

| Metric | Value | Weight | Contribution |
|--------|-------|--------|--------------|
| Relevance | 0.8 | 0.5 | 0.4 |
| Recency | 0.6 | 0.5 | 0.3 |
| **Final Score** | | | **7.0** |

---

#### 4. Cross-Encoder Rerank Score (可选)

**Purpose**: Neural reranking using transformer models for semantic similarity.

**When enabled** (`use_cross_encoder: true`):
```python
from sentence_transformers import CrossEncoder

model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
pairs = [(query, title + "\n" + abstract) for paper in papers]
scores = model.predict(pairs)  # Returns raw logits, typically -10 to 10

# Sort by score descending
papers.sort(by=cross_encoder_score, reverse=True)
```

**Characteristics**:
- Uses `ms-marco-MiniLM-L-6-v2` by default (can be changed)
- Scores are raw model outputs (not normalized)
- Applied after initial retrieval, before ranking agent
- **Performance**: GPU recommended, ~100-500ms per paper

---

#### 5. LLM Relevance Score (LLM增强模式)

**Purpose**: Semantic relevance judged by LLM reading the abstract.

**Calculation** (in `intelligent_search.py`):
```python
# LLM analyzes paper abstract and judges relevance
# Returns: relevance_score (0-1), match_confidence ("high"/"medium"/"low")

# Composite scoring (LLM mode)
composite_score = (
    0.6 × llm_relevance_score +      # LLM semantic understanding
    0.2 × recency_score +             # Time decay (1 year window)
    0.2 × original_score              # Source API score (0-1 normalized)
)
```

**LLM Relevance Scale** (as judged by LLM):

| Score Range | Meaning | Example |
|-------------|---------|---------|
| 0.0 - 0.3 | Not relevant | Geometry paper for finance query |
| 0.4 - 0.6 | Weakly relevant | Cross-disciplinary, not core topic |
| 0.7 - 0.8 | Relevant | Matches interest domain |
| 0.9 - 1.0 | Highly relevant | Core topic match |

**Filtering**:
- Papers with `llm_relevance_score < llm_relevance_threshold` (default 0.6) are filtered out
- In `strict_mode`, only "high" confidence matches are kept

---

### Parameter Reference / 参数详解

#### Core Ranking Parameters / 核心排序参数

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `ranking_threshold` | 6.0 | 0-10 | **Final cutoff score**. Papers below this value are discarded. Lower = more lenient, higher = stricter. |
| `min_relevance_ratio` | 0.2 | 0-1 | **Minimum relevance ratio** (relevance_score / max_score). Filters papers that are too weak relative to the best match. |
| `recency_window_days` | 60 | 1-365 | **Recency weight window**. Papers older than this get minimal recency score. |

**How Adaptive Thresholding Works**:
```python
# If overall scores are low, thresholds auto-adjust
adaptive_threshold = min(config_threshold, max(3.0, avg_score × 0.8))
adaptive_min_relevance = min(config_min_relevance, max(0.03, config_min_relevance × 0.5))

# Pass conditions
passes_score = (score >= adaptive_threshold) OR (score >= max_score × 0.7)
passes_relevance = (relevance >= adaptive_min_relevance) OR (score >= max_score × 0.85)

# Recency is more lenient for high-scoring papers
effective_recency_window = recency_window_days × (1.5 if score >= max_score × 0.8 else 1.0)
```

#### User Ranking Weights / 用户权重配置

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `ranking_weights.relevance` | 0.5 | 0-1 | Weight for relevance component. Higher = prefer topic match over freshness. |
| `ranking_weights.recency` | 0.5 | 0-1 | Weight for recency component. Higher = prefer newer papers. |

**Tip:** `relevance + recency` should equal 1.0 for balanced scoring.

#### LLM-Enhanced Search Parameters / LLM增强搜索参数

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `llm_search_enabled` | false | true/false | **Master switch** for LLM-enhanced search pipeline. |
| `llm_relevance_threshold` | 0.6 | 0-1 | **Semantic relevance cutoff**. Papers with LLM score below this are filtered out. |
| `llm_analysis_batch_size` | 12 | 1-50 | **Batch size** for LLM relevance analysis. Larger = fewer API calls, but slower per batch. |

---

### Score Comparison: Simple vs LLM Mode / 模式对比

#### Simple Mode Score Breakdown

```
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: Discovery                                          │
│  ├── Source API returns candidates with source_score        │
│  └── Cross-Encoder (optional): reranks by neural similarity │
├─────────────────────────────────────────────────────────────┤
│  Stage 2: RankingAgent                                       │
│  ├── relevance_score: keyword/phrase matching (0-1)         │
│  ├── recency_score: 1 - age/window (0-1)                    │
│  └── final_score: 10 × (w_rel×rel + w_rec×rec) (0-10)       │
├─────────────────────────────────────────────────────────────┤
│  Stage 3: Filtering                                          │
│  ├── score >= ranking_threshold?                            │
│  ├── relevance >= min_relevance_ratio × max?                │
│  └── age <= recency_window_days?                            │
└─────────────────────────────────────────────────────────────┘
```

#### LLM-Enhanced Mode Score Breakdown

```
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: Discovery (LLM Expanded)                           │
│  ├── LLM generates expanded queries per interest            │
│  ├── Multi-source search with expanded terms                │
│  └── More candidates fetched (limit increased to 30)        │
├─────────────────────────────────────────────────────────────┤
│  Stage 2: LLM Relevance Verification                         │
│  ├── LLM reads abstract, judges relevance (0-1)             │
│  └── Batch processing: 12 papers per API call               │
├─────────────────────────────────────────────────────────────┤
│  Stage 3: Composite Scoring                                  │
│  ├── llm_relevance: 0-1 (semantic match)                    │
│  ├── recency: 1 - age/365 (1-year window)                   │
│  ├── original_score: source API score (0-1)                 │
│  └── composite = 0.6×llm + 0.2×recency + 0.2×original       │
├─────────────────────────────────────────────────────────────┤
│  Stage 4: Filtering                                          │
│  └── llm_relevance >= llm_relevance_threshold?              │
└─────────────────────────────────────────────────────────────┘
```

---

### Tuning Guide / 调参指南

#### Scenario 1: Too Few Results / 结果太少

```yaml
# Relax constraints
ranking_threshold: 4.0           # Lower from 6.0
min_relevance_ratio: 0.05        # Lower from 0.2
discovery_limit_per_source: 50   # Increase from 10
```

#### Scenario 2: Poor Relevance / 相关性差

```yaml
# Enable LLM enhancement
llm_search_enabled: true
llm_relevance_threshold: 0.7     # Stricter filtering
llm_analysis_batch_size: 10      # Smaller batches for better precision

# Or adjust weights (simple mode)
ranking_weights:
  relevance: 0.8                 # Prefer topic match
  recency: 0.2
```

#### Scenario 3: Too Many Old Papers / 旧论文过多

```yaml
recency_window_days: 30          # Shorter window
ranking_weights:
  relevance: 0.3
  recency: 0.7                   # Prefer recent papers
```

#### Scenario 4: Balanced Daily Monitoring / 均衡日常监控

```yaml
# Recommended for daily research tracking
discovery_limit_per_source: 20
ranking_threshold: 5.5
min_relevance_ratio: 0.15
recency_window_days: 45
llm_search_enabled: true
llm_relevance_threshold: 0.6
llm_analysis_batch_size: 12
```

---

### Semantic Relevance Explained / 语义相关性说明

**The Problem:** Traditional keyword search can fail when:
- Same term has different meanings ("factor" in finance vs geometry)
- Related concepts use different vocabulary
- Cross-disciplinary papers use different terminology

**Example: Why "factor investing" returns geometry papers**

| Paper Title | Keyword Match | LLM Analysis |
|-------------|---------------|--------------|
| "Dynamic Light Spanners in **Doubling Metrics**" | ❌ "factor" not found | Actual field: computational geometry |
| "Multi-**Factor** Models in Emerging Markets" | ✅ "factor" found | Actual field: financial economics |

**Without LLM**: Both papers might match if "factor" appears in metadata
**With LLM**: LLM reads abstract and correctly identifies actual research domain

**LLM Judgment Criteria**:
1. **Core domain identification** - What field is this actually in?
2. **Semantic similarity** - Does the abstract discuss concepts related to the interest?
3. **Methodology check** - Are the techniques relevant to the interest domain?
4. **Confidence scoring** - How certain is the judgment?

---

<p align="center">
  Made with ❤️ for researchers
</p>


