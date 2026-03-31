
# 1. 项目概览：MAS-PaperHelper

本系统是一个基于多智能体协作（Multi-Agent Collaboration）的本地化科研辅助平台，核心目标是消除手动检索、下载和初读论文的机械劳动，利用大模型实现精准的领域前沿追踪。

## 2. 技术栈选型
* **环境/依赖管理：** `uv` (用于极速依赖安装与虚拟环境管理)
* **Agent 编排：** LangGraph (支持循环状态机，适合复杂的论文筛选逻辑)
* **大模型调度：** LiteLLM 或 Ollama (支持本地/云端多模型无缝切换)
* **数据库：**
    * **元数据与日志：** ClickHouse (支持高性能分析，方便后续做阅读行为挖掘)
    * **向量检索：** Milvus 或 Chroma (支持本地持久化与多租户隔离)
* **解析工具：** `Docling` 或 `Marker` (将 PDF 高质量转为 Markdown)

---

## 3. 系统详细设计

### 3.1 灵活可配置项 (`config.yaml`)
系统采用一层全局配置 + 多用户 Profile 的模式。

```yaml
# 全局配置
global:
  llm_provider: "ollama" # 或 openai, claude
  base_model: "qwen2.5-72b-instruct"
  embedding_model: "text-embedding-3-small"
  max_concurrent_tasks: 5

# 用户/领域配置 (实现多用户隔离)
users:
  - user_id: "quant_researcher_01"
    interests: ["Market Microstructure", "High Frequency Trading"]
    search_query: "abs: 'order book' AND cat:cs.LG"
    update_frequency: "daily"
    ranking_weights:
      recency: 0.4
      relevance: 0.6
    llm_api_key: "sk-..." # 可选，支持私有配置
```

### 3.2 数据来源与下载方案
系统通过 Agent 调用专门的 Tool 进行数据获取：

| 来源 | 接入方式 | 说明 |
| :--- | :--- | :--- |
| **arXiv** | API (arxiv-api) | 支持按类别、日期过滤，性能最稳 |
| **Semantic Scholar** | REST API | 用于获取被引频次、S2ORC 摘要，提升筛选精度 |
| **BioRxiv/MedRxiv** | R RSS Feed | 针对生物/医药领域的实时追踪 |
| **Google Scholar** | Scholarly (Python lib) | 用于长尾搜索，但需注意 IP 频率限制 |

**下载逻辑：** 1.  由 `Discovery Agent` 获取 PDF URL。
2.  `Download Tool` 优先尝试官方 API，备选 `Sci-Hub` API（仅用于学术合规范围内）。
3.  文件本地存储路径：`./data/storage/{user_id}/{paper_id}.pdf`。

### 3.3 数据库字段设计 (ClickHouse)

**表名：`paper_metadata`**
* `id`: String (UUID)
* `user_id`: LowCardinality(String) -> **隔离关键字段**
* `title`: String
* `authors`: Array(String)
* `abstract`: String
* `publish_date`: DateTime
* `source`: String (arXiv, etc.)
* `download_path`: String
* `recommend_score`: Float32
* `is_read`: UInt8 (0/1)
* `user_tags`: Array(String) -> **偏好沉淀**

---

### 3.4 知识库构建与检索逻辑 (RAG)

**知识沉淀流程：**
1.  **解析：** 使用 `Marker` 将 PDF 转换为 Markdown，保留公式和表格。
2.  **分块 (Chunking)：** 按 Markdown 层级（如 `## Introduction`）进行语义分块。
3.  **向量化：** 针对每个 `user_id` 在向量库中建立独立的 **Collection** 或 **Partition**。
4.  **元数据注入：** 向量索引中必须包含 `publish_date` 和 `score`，实现“时间重排”或“质量重排”。

**检索逻辑：**
* **两阶段检索：** 先基于向量相似度召回 Top 50，再利用 Cross-Encoder 进行重排序（Rerank）。
* **多维过滤：** 检索时自动带入当前用户的 `user_id` 过滤条件。

---

## 4. 多智能体工作流 (LangGraph Design)

系统运行时的状态机逻辑如下：



1.  **Idle / Trigger:** 达到设定时间点，启动工作流。
2.  **Search Node:** `Discovery Agent` 根据用户的 `search_query` 抓取前 $N$ 篇新论文摘要。
3.  **Filtering Node:** `Ranking Agent` 调用 LLM 对摘要进行快速打分。
    * **打分逻辑：** 判断是否符合用户设定的 `interests`。
    * **阈值过滤：** 低于 $6.0$ 分的论文仅记录不下载。
4.  **Download & Parse Node:** 对高分论文执行异步下载并转换为 Markdown。
5.  **Summarize Node:** `Summary Agent` 读取全文 Markdown，生成结构化总结：
    * *Core Innovation, Methodology, Key Results, Potential Use Case.*
6.  **Knowledge Base Update:** 将解析内容和总结存入向量数据库与 ClickHouse。
7.  **Notification:** 向用户发送今日推送（本地 Web UI 或终端输出）。

---

## 5. 项目结构建议

```bash
.
├── config/
│   └── config.yaml          # 全局与用户配置
├── core/
│   ├── agents/              # LangGraph 节点定义
│   ├── tools/               # 搜索、下载、PDF解析工具
│   └── database/            # ClickHouse & Milvus 封装
├── data/
│   ├── storage/             # PDF 原文件 (按 user_id 分类)
│   └── vector_db/           # 本地向量数据库存储
├── scripts/
│   └── main.py              # 系统入口
├── pyproject.toml           # uv 配置文件
└── .env                     # 敏感 API Key
```

## 6. 后续开发建议

* **本地 GPU 加速：** 如果本地有 NVIDIA 显卡，建议在 PDF 解析阶段和 Embedding 阶段显式开启 CUDA 任务，这能让处理 100 篇论文的时间从小时级缩短到分钟级。
* **用户偏好闭环：** 在本地 UI 中增加“喜欢/不喜欢”按钮。每次点击后，调用一个 `Profile Update Agent` 重新总结用户的兴趣关键词，并写回 `config.yaml`。

您是否希望我为您编写一份基于 **LangGraph** 和 **Ollama** 的 `Discovery Agent` 核心代码原型？

