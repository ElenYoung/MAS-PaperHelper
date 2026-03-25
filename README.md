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

<p align="center">
  Made with ❤️ for researchers
</p>
