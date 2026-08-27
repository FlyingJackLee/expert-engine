# Expert Engine

长期开发上下文、当前验证状态和待办维护在 [MEMORY.md](MEMORY.md)。
首批行业资料的采集规范和模板见 [docs/data-collection/README.md](docs/data-collection/README.md)。
当前架构、流程图和每次核心演进记录见 [docs/architecture.md](docs/architecture.md)。
开发阶段、交付标准与当前优先级见 [docs/development-plan.md](docs/development-plan.md)。

一期的住建数字化商机研判引擎骨架。系统以 LangGraph 编排推理流程，并要求关键结论附带可追溯证据；LLM 不应绕过知识、组织和能力引擎编造关键事实。

## 当前能力

- `housing_digitalization` 专家 Profile 与版本化规则
- 事件结构化、受控样例知识检索、需求/单位/处室/能力匹配
- 确定性机会评分和独立的证据覆盖 Reviewer
- `POST /api/v1/expert/analyze` 与 Run 查询接口
- 跟进反馈记录，以及从反馈提炼待审核 Knowledge Candidate 的 API

## 本地启动

```bash
cp .env.example .env
uv sync --all-groups
uv run uvicorn app.main:app --reload
```

接口文档：`http://127.0.0.1:8000/docs`。

## 评测

```bash
uv run python -m evaluation.run_benchmark
uv run pytest -q
```

测试套件与 Benchmark 会强制关闭 LLM，避免意外使用本地 `.env` 中的模型密钥；真实模型验证请按下方 Gateway 配置手动执行。若需在受控场景运行模型评测，显式传入 `EVALUATION_ALLOW_LLM=true`。

`evaluation/benchmark_housing_v1.json` 定义黄金样本的数据契约。当前仅含种子样本，业务标注完成后应扩充至规格要求的 50–100 条，并以此作为版本发布门槛。

评测输出包含逐案例的断言结果和实际摘要；任一案例失败时命令以非零状态退出，可直接用于 CI。

> 当前知识库是用于链路验证的内置种子数据。下一阶段将替换为 PostgreSQL/pgvector、OpenSearch、MinIO 和 PostgreSQL checkpointer。

## Phase 2：本地知识库

```bash
docker compose up -d postgres redis minio
uv run python -m scripts.migrate
uv run python -m scripts.seed_knowledge
KNOWLEDGE_BACKEND=postgres uv run uvicorn app.main:app --reload
```

分析结果使用 `RUN_BACKEND=postgres` 持久化；执行迁移后，`GET /api/v1/expert/runs/{run_id}` 可在服务重启后查询结果。测试环境使用内存后端，不依赖 Docker。

人工审核可通过 `POST /api/v1/expert/runs/{run_id}/reviews` 提交 `APPROVE`、`REJECT` 或 `REQUEST_RESEARCH` 决定，以及审核人角色代号和备注；审核记录保存到 PostgreSQL 审计表。

跟进结果可通过 `POST /api/v1/expert/runs/{run_id}/feedback` 记录。存在至少一条反馈后，调用 `POST /api/v1/expert/runs/{run_id}/knowledge-candidates` 可生成 `PENDING_APPROVAL` 候选；通过 `GET /api/v1/expert/knowledge-candidates/{candidate_id}` 查询。候选不会自动发布或参与检索。

专家可通过 `POST /api/v1/expert/knowledge-candidates/{candidate_id}/reviews` 审核候选。候选创建后会由 LangGraph `interrupt` 暂停，审核 API 以 `resume` 恢复对应流程；决定只允许写入一次，并作为审计记录保存。HITL workflow 使用 PostgreSQL checkpoint，`scripts.migrate` 会自动初始化其官方表结构；即使通过，也仍需后续发布流程才会进入正式知识库。

仅审核通过的候选可调用 `POST /api/v1/expert/knowledge-candidates/{candidate_id}/publish` 发布。发布会创建递增版本的 `INTERNAL` 知识文档及其候选来源记录，并在后续 Research 中作为补充历史经验检索；它不能替代政策、职责等原始证据。

如需停止某个版本参与后续推理，可调用 `POST /api/v1/expert/knowledge-publications/{publication_id}/retire`，并提交专家角色代号与原因。退役不会物理删除知识或审计记录，只会将该 `INTERNAL` 文档排除出检索。

经复核后，可调用 `POST /api/v1/expert/knowledge-publications/{publication_id}/restore` 恢复已退役版本。恢复会重新启用内部检索可见性，并以 `RESTORED` 事件记录在同一版本治理审计链中。

每次分析会将检索到的已发布 `INTERNAL` 知识单独返回为 `historical_knowledge`，并将其作为受约束 LLM 商务综合的补充上下文。历史经验不能替代当前事件的政策、职责或项目原始证据。

`uv run python -m evaluation.run_benchmark` 还会报告 `historical_knowledge_coverage`，用于验证已发布经验在后续推理中可检索、可追溯，并始终保持为 `INTERNAL` 补充上下文。

此时相同的分析 API 将从 PostgreSQL（宿主机端口 `5433`）中读取证据。文档可通过 `POST /api/v1/knowledge/documents` 写入；原始文件对象存储、嵌入生成与 OpenSearch BM25 将在后续检索增强迭代接入。

PostgreSQL 检索会融合全文排序、`pg_trgm` 相似度和词覆盖，并继续使用城市、主题、证据类型与知识生命周期过滤；运行 `scripts.migrate` 会创建所需索引。

向量检索通过 `EMBEDDING_ENABLED=true`、`EMBEDDING_MODEL=<model-name>` 显式启用。启用后知识文档导入和专家知识发布会生成 chunk embedding；未配置时不会调用 embedding 服务。当前向量列和查询不固定维度，切换模型后应安排旧资料向量重建。

采集目录中的城市 JSONL 数据可在不写数据库的情况下先做预检；正式导入默认只接受 `VERIFIED` 记录：

```bash
uv run python -m scripts.ingest_dataset docs/data-collection/chongqing --check
uv run python -m scripts.ingest_dataset docs/data-collection/chongqing
```

采集过程中的联调可显式加 `--include-draft`，该选项不应用于生产知识库。

## LLM Gateway（可选）

默认未启用模型调用，事件分析与研究规划使用确定性规则。先执行 `cp .env.example .env`，再在 `.env` 中配置 OpenAI-compatible Chat Completions 网关，即可启用 Schema 约束的模型输出：

```bash
LLM_ENABLED=true
LLM_BASE_URL=https://<your-gateway>/v1
LLM_API_KEY=<your-api-key>
LLM_EVENT_MODEL=<model-name>
LLM_RESEARCH_MODEL=<model-name>
```

所有职责默认共用 `LLM_BASE_URL`、`LLM_API_KEY` 及各自的全局模型变量；如某个环节使用不同服务，可按完整 Profile 名称覆盖：`LLM_EVENT_ANALYZER_BASE_URL`、`LLM_EVENT_ANALYZER_API_KEY`、`LLM_EVENT_ANALYZER_MODEL`。未设置的字段逐项回退到全局默认，不会影响其他环节。

模型只负责事件理解和研究问题规划；单位、处室、案例等关键事实仍只能通过知识库证据得出。未配置任何一个必填变量时，相应节点会自动使用规则兜底。

Gateway 会优先使用 JSON Schema；若当前网关不支持 `response_format`，会自动降级为 JSON Object，最后再以提示词要求纯 JSON，并在本地进行 Pydantic Schema 校验。

## 轻量调试日志

默认输出分析请求、完成结果（run ID、耗时、评分、审核结果、证据数量）和失败堆栈。开发中可设置 `LOG_LEVEL=DEBUG`，查看每个 Graph 节点的开始/完成、耗时和输出字段摘要；日志不会输出事件正文、`user_context`、证据正文或任何密钥。
