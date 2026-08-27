# Expert Engine 开发记忆

> 这是项目的长期开发上下文。每次完成功能、调整架构或验证关键流程后，请同步更新本文件；内容应描述已验证的事实，不记录密钥、令牌或个人信息。

## 项目定位

面向住建数字化场景的、以证据为基础的商务机会研判引擎。一期采用 FastAPI + LangGraph；模型只能辅助事件理解与研究规划，单位、处室、能力、案例等关键结论必须能追溯到知识库证据。

## 当前状态（2026-08-26）

- 工作分支：`develop`；遵循从 `develop` 开发、通过 PR 合入 `main` 的约定。
- Git 状态：尚无首次提交；当前实现文件均未跟踪，首次提交前应人工复核纳入范围。
- 应用版本：`0.1.0`（见 `pyproject.toml`）。
- 已实现：住建数字化专家 Profile、LangGraph 推理编排、种子知识检索、需求/组织/处室/能力匹配、确定性机会评分、证据覆盖 Reviewer、分析与 Run 查询 API。
- Phase 2 基础：PostgreSQL 知识库访问、迁移与灌数脚本，以及知识文档写入接口；向量检索、OpenSearch BM25、MinIO 原文件存储和 checkpointer 尚未接入。
- 评测：`uv run pytest -q` 于 2026-08-26 通过，结果为 `6 passed`。存在 FastAPI TestClient 与 LangGraph 的依赖弃用警告，当前不阻塞功能。
- 观测性：标准库日志记录分析请求与结果摘要；设置 `LOG_LEVEL=DEBUG` 可看到 Graph 节点的安全调试信息（run ID、节点、耗时和输出字段），不会记录事件正文、用户上下文或密钥。
- Benchmark：运行器现在输出逐案例检查、实际主题/评分/审核/证据类型，并在存在失败案例时以非零退出，适合接入 CI。当前仍只有 1 条种子样本，不能作为生产发布门槛。
- 数据采集：`docs/data-collection/` 提供住建数字化首批数据的目录约定、质量/脱敏规范、验收清单和 JSONL 模板。首批以一个城市为行业单元，覆盖住建委、城管局、城投公司三方，合计采集 25–30 条核验事件。
- 数据集接入：`scripts.ingest_dataset` 可预检并导入符合目录规范的城市 JSONL；默认仅导入 `VERIFIED`，`--include-draft` 仅用于本地联调。
- 数据驱动匹配：组织、处室、能力和案例候选已从 `core.py` 的固定业务 ID 重构为读取检索证据元数据；缺少对应证据时返回 `UNKNOWN`，不再以种子结论替代。测试与 benchmark 强制使用 `seed` 后端，避免受开发者本地 PostgreSQL 数据影响。
- 定向检索：事件分析按证据类型分别检索政策/行业、组织职责、能力和案例；`EventInput.city`（或 `user_context.city`）会过滤本地政策与职责证据，能力/案例保持跨城市复用。
- 补检索闭环：Reviewer 的 `RESEARCH_MORE` 会生成补检索问题并受控回到研究节点；重试上限由 `MAX_RESEARCH_RETRIES` 配置（默认 1），达到上限后返回未解决缺口。
- 专家注册：Graph 已通过专家注册中心发现 Profile 与其声明的 Runtime，不再直接引用住建专家 ID、Prompt 或主题关键词；扩展新行业以新增 Profile + Runtime 为主。
- 运行持久化：分析结果由 `RunRepository` 保存，生产默认 PostgreSQL `expert_runs`，测试使用内存实现；审核未通过的运行保存为 `PENDING_REVIEW`，待接入人工审核动作。
- 检索上下文：研究节点将事件主题和标题并入查询；政策/行业按城市+主题、能力/案例按主题、组织职责按城市过滤，检索排序保持稳定。
- 通用候选排序：组织、处室、能力、案例均按证据相关度、来源可靠度与城市/主题元数据排序；通用权重集中在配置中，同分以稳定 ID 决定顺序。
- 种子 benchmark 校准：移除固定实体评分后，种子样本的规则分数为 78；其演示门槛由 80 校准为 75。真实业务 benchmark 的门槛须由人工标注确定。
- 证据绑定：`ground_evidence` 节点在结果中输出需求、组织、处室、能力到证据 ID 的独立映射，并标记 `GROUNDED` / `UNGROUNDED`；为审核与片段级引用扩展提供契约。
- 人工审核：`POST /api/v1/expert/runs/{run_id}/reviews` 可提交通过、驳回、要求补研究决定，审核人角色代号与备注审计到 `expert_run_reviews`；尚未连接 LangGraph Interrupt/恢复。
- 商务综合判断：`synthesize_opportunity` 支持专家 Runtime 声明的 Schema 约束 LLM，输入只含已接地结论与映射；未配置模型或本地校验失败时使用确定性兜底。
- 独立 Reviewer：`review` 支持专家 Runtime 声明的 Critic LLM 审查证据映射；Critic 仅能增加缺口，不能覆盖确定性规则，未配置或校验失败时使用规则审核。
- 引用映射：`grounding` 为每个结论输出证据 ID、来源文档、标题、URL 和 chunk 索引；PostgreSQL 检索保留 chunk 位置，便于人工审核定位。
- Evidence Rerank：检索结果在匹配前按词命中、初始相关度和来源可靠度融合重排，作为通用组件使用，不包含行业或城市事实。
- 需求推理：`infer_needs` 支持 Schema 约束 LLM，只接收事件分析和政策/行业证据；模型返回的证据 ID 经本地白名单过滤，规则兜底需求 ID 由主题和任务稳定派生。
- 跟进反馈：`POST /api/v1/expert/runs/{run_id}/feedback` 记录通用 outcome、notes、submitted_by 到 `expert_run_feedback`，为后续 Knowledge Candidate 提炼提供结构化来源。

## 关键入口

| 目的 | 位置 |
| --- | --- |
| 应用与路由 | `app/main.py`、`app/api/` |
| Graph 与状态 | `app/graph/main.py`、`app/graph/state.py` |
| 推理节点 | `app/nodes/core.py` |
| 领域 Schema | `app/schemas/domain.py` |
| 专家配置 | `app/experts/profiles/housing_digitalization.json` |
| 检索与种子数据 | `app/knowledge/` |
| LLM 网关 | `app/llm/gateway.py` |
| 评分规则 | `app/scoring/engine.py` |
| 评测与测试 | `evaluation/`、`tests/` |
| 完整需求规格 | `spec.md` |

## 本地运行与验证

```bash
cp .env.example .env
uv sync --all-groups
uv run uvicorn app.main:app --reload
uv run pytest -q
uv run python -m evaluation.run_benchmark
```

使用 PostgreSQL 知识后端时：

```bash
docker compose up -d postgres redis minio
uv run python -m scripts.migrate
uv run python -m scripts.seed_knowledge
KNOWLEDGE_BACKEND=postgres uv run uvicorn app.main:app --reload
```

## 重要约束

- 默认关闭 LLM；评测必须保持 LLM 关闭，除非明确设置 `EVALUATION_ALLOW_LLM=true`。
- 不得将 `.env`、API Key 或真实客户敏感数据提交到仓库。
- 修改评分、证据规则、专家 Profile 或输出 Schema 时，应同步补充/更新 benchmark 与测试，并在本文件记录兼容性影响。
- 当前内置知识仅为链路验证种子数据，不能将其视为生产事实库。
- 组件边界与架构图维护在 `docs/architecture.md`：节点不得硬编码城市、单位、处室、能力或案例业务结论；每次核心架构/流程变更须更新图和演进记录，并在交付说明中展示对应图。
- `docs/architecture.md` 的“目标技术架构与当前进度”表是功能完成度的单一查看入口；每次开发必须同步更新表格、目标流程图状态和实际运行链路。
- `docs/development-plan.md` 是开发计划与阶段验收标准的单一入口；阶段 1（核心分析可用）当前进行中。代码可读性基线：所有类必须具备职责 docstring，公共函数和非显然控制流必须有简短说明。

## 建议后续顺序

1. 复核未跟踪文件，完成首次提交到 `develop`。
2. 引入经业务标注的 50–100 条 benchmark 样本，设定发布门槛。
3. 接入生产知识链路：pgvector、OpenSearch、MinIO 与 PostgreSQL checkpointer。
4. 完善 Human-in-the-loop、长任务恢复、可观测性与权限/数据治理。

## 更新模板

每次重要变更追加：日期、改动范围、验证命令及结果、未解决风险、下一步。例如：

```text
### YYYY-MM-DD — 主题
- 改动：
- 验证：
- 风险/待办：
```
