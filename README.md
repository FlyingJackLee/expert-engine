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

此时相同的分析 API 将从 PostgreSQL（宿主机端口 `5433`）中读取证据。文档可通过 `POST /api/v1/knowledge/documents` 写入；原始文件对象存储、嵌入生成与 OpenSearch BM25 将在后续检索增强迭代接入。

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

模型只负责事件理解和研究问题规划；单位、处室、案例等关键事实仍只能通过知识库证据得出。未配置任何一个必填变量时，相应节点会自动使用规则兜底。

Gateway 会优先使用 JSON Schema；若当前网关不支持 `response_format`，会自动降级为 JSON Object，最后再以提示词要求纯 JSON，并在本地进行 Pydantic Schema 校验。

## 轻量调试日志

默认输出分析请求、完成结果（run ID、耗时、评分、审核结果、证据数量）和失败堆栈。开发中可设置 `LOG_LEVEL=DEBUG`，查看每个 Graph 节点的开始/完成、耗时和输出字段摘要；日志不会输出事件正文、`user_context`、证据正文或任何密钥。
