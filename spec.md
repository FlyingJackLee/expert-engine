# Expert Engine 一期技术规格说明书

**技术路线：LangGraph 原生编排版**
**版本：V1.0**
**定位：AI 商务机会研判系统核心专家引擎**

---

# 1. 建设目标

Expert Engine 是整个商务机会研判系统的核心能力层。

一期不以“业务系统完整度”为主要目标，而以构建一个：

> **可独立调用、可解释、可验证、可持续学习的行业专家智能推理引擎**

为核心目标。

Expert Engine 接收到一条事件后，需要基于：

* 行业知识
* 政策知识
* 组织及部门职责
* 公开项目与采购信息
* 企业内部客户知识
* 公司产品与解决方案
* 公司历史案例
* 已验证专家经验
* 历史商务案例

完成专业研判。

最终回答：

```text
发生了什么？
↓
可能产生什么需求？
↓
哪些单位可能负责？
↓
哪些部门负责？
↓
谁可能牵头、谁可能协同？
↓
我方具备哪些对应能力？
↓
有没有历史案例可以佐证？
↓
这个机会价值多高？
↓
当前判断有多可信？
↓
为什么这么判断？
↓
下一步应该怎么行动？
```

---

# 2. 核心技术路线

一期直接采用：

```text
Python
+
FastAPI
+
LangGraph
+
PostgreSQL
+
pgvector
+
OpenSearch
+
Redis
+
MinIO
+
统一 LLM Gateway
```

其中：

**FastAPI**

负责 Expert Engine 对外 API。

**LangGraph**

负责 Expert 内部：

* 状态管理
* AI 推理编排
* 条件路由
* 并行研究
* Reviewer 回路
* 补充检索
* Interrupt
* Human-in-the-loop
* Checkpoint
* 长任务恢复

LangGraph 当前官方定位就是面向“长运行、有状态、需要确定性流程和 Agent 推理结合”的 Agent 编排框架，并原生提供 durable execution、streaming、human-in-the-loop、persistence 等能力。

---

# 3. 系统边界

整体系统：

```text
┌──────────────────────────────────────┐
│          外围业务/交互系统            │
│                                      │
│ Dify / Web / CRM / 企业微信 / API    │
└──────────────────┬───────────────────┘
                   │
                   │ REST / SSE
                   ▼
┌──────────────────────────────────────┐
│              Expert API              │
│               FastAPI                │
└──────────────────┬───────────────────┘
                   ▼
┌──────────────────────────────────────┐
│           Expert Runtime             │
│             LangGraph                │
│                                      │
│ State / Nodes / Edges / Interrupt    │
│ Retry / Checkpoint / Streaming       │
└──────────────────┬───────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
 Knowledge    Organization   Capability
 Engine       Engine         Engine
        │          │          │
        └──────────┼──────────┘
                   ▼
             Evidence Engine
                   ▼
              Reviewer
                   ▼
             Expert Result
```

---

# 4. LangGraph 在系统中的定位

LangGraph负责：

```text
WHO RUNS NEXT
WHEN TO RUN
WHAT STATE TO PASS
WHEN TO RETRY
WHEN TO STOP
WHEN TO ASK HUMAN
```

LangGraph不负责定义：

```text
行业知识
组织职责
公司能力
商机评分规则
Evidence规则
专家经验
```

因此必须坚持：

> **LangGraph 是编排基础设施，不是行业核心资产本身。**

---

# 5. 总体 LangGraph

一期主 Graph：

```text
START
  │
  ▼
initialize
  │
  ▼
route_expert
  │
  ▼
analyze_event
  │
  ▼
plan_research
  │
  ├─────────────────────────────────┐
  │                                 │
  ▼                                 ▼
retrieve_policy              retrieve_industry
  │                                 │
  ├───────────────┐                 │
  │               │                 │
  ▼               ▼                 ▼
retrieve_org   retrieve_cases   retrieve_internal
  │               │                 │
  └───────────────┴─────────────────┘
                  │
                  ▼
             merge_evidence
                  │
                  ▼
              infer_needs
                  │
                  ▼
           match_organizations
                  │
                  ▼
            match_departments
                  │
                  ▼
           match_capabilities
                  │
                  ▼
             retrieve_cases
                  │
                  ▼
          synthesize_opportunity
                  │
                  ▼
              score_result
                  │
                  ▼
                review
                  │
          ┌───────┼────────┐
          │       │        │
       APPROVE  RETRY   HUMAN_REVIEW
          │       │        │
          │       ▼        ▼
          │   research   interrupt
          │       │        │
          │       └───┐    │
          │           │    │
          └───────────┴────┘
                  │
                  ▼
           finalize_result
                  │
                  ▼
                 END
```

---

# 6. Graph State 设计

Expert Engine 所有节点共享一个统一：

```python
ExpertState
```

建议结构：

```python
class ExpertState(TypedDict):

    # Runtime
    run_id: str
    thread_id: str
    status: str

    # Context
    user_context: dict
    expert_id: str
    expert_profile: dict

    # Input
    raw_event: dict

    # Event understanding
    event_analysis: dict
    topics: list
    entities: list
    tasks: list
    signals: dict

    # Research
    research_plan: dict
    queries: list

    # Knowledge
    policy_evidence: list
    industry_evidence: list
    organization_evidence: list
    case_evidence: list
    internal_evidence: list

    evidence: list

    # Reasoning
    needs: list
    organizations: list
    departments: list

    capabilities: list
    solutions: list
    cases: list

    # Opportunity
    opportunity: dict

    # Deterministic score
    score: dict
    confidence: float

    # Review
    review_result: dict
    review_issues: list

    # Loop control
    retry_count: int
    retry_reason: str | None

    # HITL
    human_review_required: bool
    human_feedback: dict | None

    # Final
    final_result: dict
```

---

# 7. State 设计原则

State 不应保存大量原始 PDF 全文。

只保存：

```text
Document ID
Chunk ID
Evidence摘要
Structured Result
Score
```

原始内容通过 Knowledge Engine 获取。

避免 Graph State 无限膨胀。

---

# 8. Checkpoint

一期生产环境使用：

```text
PostgreSQL Checkpointer
```

不能使用：

```text
InMemorySaver
```

作为生产方案。

LangGraph 的 checkpointer 可以持久化一个 thread 的 Graph State，用于：

* 中断恢复
* 故障恢复
* Human-in-the-loop
* 历史状态查看

而 Store 更适合跨 thread 的长期数据。

---

# 9. Thread 设计

每次独立 Expert Analysis：

```text
1 Analysis Run
=
1 LangGraph Thread
```

thread_id：

```text
run UUID
```

例如：

```text
307a35bf-...
```

保存：

```text
run_id
thread_id
user_id
expert_id
event_id
```

---

# 10. Node 设计原则

一个 Node 只做一类职责。

禁止：

```text
一个 Prompt
同时完成
事件分析 + 找单位 + 找部门 + 匹配方案 + 商机判断
```

推荐：

```text
Node
=
One Reasoning Responsibility
```

---

# 11. Initialize Node

职责：

* 创建 Run
* 校验 Input
* 加载用户权限
* 初始化 State
* 初始化 Retry Count

输入：

```json
{
  "event": {},
  "expert_id": "AUTO"
}
```

---

# 12. Expert Router Node

节点：

```text
route_expert
```

负责决定：

> 应该调用哪个行业 Expert。

方法：

```text
规则分类
+
Embedding相似度
+
LLM分类
```

输出：

```json
{
  "primary_expert": "housing_digitalization",
  "secondary_experts": [],
  "confidence": 0.93
}
```

---

# 13. Expert Profile

每一个 Expert 都必须拥有自己的 Profile。

例如：

```json
{
  "id": "housing_digitalization",

  "name": "住建数字化专家",

  "version": "1.0",

  "domains": [
    "城市更新",
    "城市生命线",
    "CIM",
    "BIM",
    "数字住建"
  ],

  "knowledge_scope": [
    "policy",
    "organization",
    "industry",
    "company",
    "case"
  ],

  "rule_set": "housing_rules_v1",

  "scoring_model": "housing_score_v1",

  "prompt_set": "housing_prompt_v1"
}
```

---

# 14. Event Analyzer Node

节点：

```text
analyze_event
```

负责提取：

```text
事件类型
地区
行业
主题
主体
建设任务
关键时间
政策信号
项目启动信号
预算信号
采购信号
```

---

# 15. Event Analysis Schema

```json
{
  "event_type": "POLICY",

  "region": {
    "province": "...",
    "city": "...",
    "district": "..."
  },

  "industry": [
    "住房城乡建设"
  ],

  "topics": [
    "城市生命线"
  ],

  "entities": [],

  "tasks": [],

  "signals": {
    "policy_strength": 0.93,
    "project_signal": 0.71,
    "budget_signal": 0.30,
    "procurement_signal": 0.10
  }
}
```

---

# 16. Research Planner Node

节点：

```text
plan_research
```

不是直接搜索。

先判断：

> 为了完成本次分析，需要调查哪些问题。

例如：

```json
{
  "questions": [
    {
      "type": "POLICY",
      "query": "该政策具体提出哪些建设任务"
    },
    {
      "type": "ORGANIZATION",
      "query": "城市生命线在当地由哪些单位负责"
    },
    {
      "type": "CASE",
      "query": "过去类似项目由哪个单位和部门牵头"
    }
  ]
}
```

---

# 17. Research Fan-Out

Research Planner 后进入并行 Research。

利用 LangGraph 并行节点执行：

```text
policy_research
industry_research
organization_research
case_research
internal_research
```

这些 Research 可以并行。

---

# 18. Policy Research Node

负责查询：

* 国家政策
* 地方政策
* 实施方案
* 上位政策
* 配套政策

输出：

```text
PolicyEvidence[]
```

---

# 19. Organization Research Node

负责：

```text
Organization Engine
```

检索：

* 机构
* 部门
* 法定职责
* 官网职责介绍
* 政策责任分工
* 历史牵头信息

---

# 20. Industry Research Node

负责行业知识：

```text
这个业务是什么
通常如何建设
涉及什么业务流程
涉及什么系统
```

避免模型完全依靠通用预训练知识。

---

# 21. Internal Research Node

仅在：

```text
include_internal = true
```

时执行。

检索：

* 内部客户
* 联系人
* 历史拜访
* 历史商机
* 已做项目
* 内部方案
* 内部商务经验

并严格携带：

```text
user_context
```

进行权限过滤。

---

# 22. Case Research Node

检索：

```text
Similar Cases
```

例如：

```text
相似事件
+
相似区域
+
相似需求
+
相似客户类型
```

返回真实历史案例。

---

# 23. Knowledge Engine

Research Node 不直接操作：

```text
pgvector
OpenSearch
SQL
```

统一调用：

```text
Knowledge Engine
```

---

# 24. Hybrid Retrieval

Knowledge Engine 实现：

```text
Query
 │
 ├── Vector Search
 │
 ├── BM25 Search
 │
 ├── Metadata Filter
 │
 ├── SQL Structured Search
 │
 └── Relationship Search
       ↓
     Fusion
       ↓
     Rerank
       ↓
     Evidence
```

---

# 25. Reranker

Retrieval结果在进入 LLM 前进行：

```text
Reranking
```

只将高相关证据进入上下文。

避免：

```text
Top50 chunks
全部直接送给大模型
```

---

# 26. Merge Evidence Node

节点：

```text
merge_evidence
```

合并：

```text
Policy
Industry
Organization
Case
Internal
```

并进行：

```text
去重
来源排序
可信度排序
冲突检测
```

---

# 27. Evidence 数据结构

```json
{
  "evidence_id": "ev_001",

  "type": "RESPONSIBILITY",

  "source_id": "...",

  "title": "...",

  "content": "...",

  "organization": "...",

  "source_url": "...",

  "relevance": 0.91,

  "reliability": 1.0,

  "effective_date": "..."
}
```

---

# 28. Evidence Reliability

建议默认规则：

```text
政府官网正式文件        1.00
政府部门职责页面        1.00
正式采购公告            0.98
内部已验证事实          0.95
真实历史项目            0.90
权威行业报告            0.85
新闻                    0.70
普通互联网网页          0.60
LLM自身推测             0.00
```

---

# 29. Need Agent

节点：

```text
infer_needs
```

负责从：

```text
Event
+
Evidence
```

推演：

```text
客户潜在需求
```

---

# 30. Need 推演链

必须按照：

```text
政策/事件目标
↓
建设任务
↓
业务需求
↓
能力需求
↓
技术需求
↓
可能建设内容
```

禁止：

```text
政策关键词
→
直接匹配我方产品
```

---

# 31. Need Schema

```json
{
  "id": "need_001",

  "name": "城市生命线风险监测平台",

  "category": "PLATFORM",

  "description": "...",

  "maturity": "EXPLICIT",

  "confidence": 0.89,

  "derived_from_tasks": [],

  "evidence_ids": []
}
```

---

# 32. Need Maturity

统一：

```text
CONCEPT
POTENTIAL
EXPLICIT
PROJECT
PROCUREMENT
```

这是防止过度研判的重要字段。

---

# 33. Organization Agent

节点：

```text
match_organizations
```

输入：

```text
Need[]
+
Organization Evidence
+
Expert Rules
+
Cases
```

输出候选单位。

---

# 34. Organization Engine

Organization Agent 不允许完全靠模型。

底层调用：

```text
Organization Engine
```

数据：

```text
Organization
Department
Responsibility
Topic
PolicyRole
Region
HistoricalCase
```

---

# 35. Organization Candidate Generation

先从数据层形成：

```text
Candidate Organizations Top N
```

例如：

```text
住建委       0.91
城管局       0.82
大数据局     0.74
应急局       0.61
```

再由 Agent 做 Contextual Rerank。

---

# 36. Department Agent

节点：

```text
match_departments
```

专门处理：

> 应该去哪个处室？

不是 Organization Agent 顺便判断。

---

# 37. Candidate First

部门必须：

```text
数据库候选
→
职责检索
→
Agent判断
```

不能：

```text
LLM自己编一个部门
```

如果无可靠信息：

```json
{
  "department": null,
  "status": "UNKNOWN"
}
```

---

# 38. Department Role

需要判断角色：

```text
LEAD
COORDINATE
TECH_SUPPORT
DATA_PROVIDER
IMPLEMENTATION
SUPERVISION
```

例如：

```text
城建处
LEAD

科技信息处
TECH_SUPPORT
```

这比只给“相关部门”更有商务价值。

---

# 39. Capability Agent

节点：

```text
match_capabilities
```

输入：

```text
Need[]
```

底层调用公司 Capability Engine。

---

# 40. 企业能力模型

统一：

```text
Capability
  ↓
Solution
  ↓
Product
  ↓
Case
```

例如：

```text
数据治理
↓
城市生命线数据治理方案
↓
数据治理平台
↓
XX城市生命线项目
```

---

# 41. Capability Agent 输出

```json
{
  "need_id": "...",

  "capability_matches": [
    {
      "capability_id": "...",
      "score": 0.92,
      "reason": "...",
      "case_ids": []
    }
  ]
}
```

---

# 42. Opportunity Synthesis Agent

节点：

```text
synthesize_opportunity
```

这个 Agent 不再做 Research。

它只能根据已有：

```text
Event
Need
Organization
Department
Capability
Case
Evidence
```

生成综合商务判断。

---

# 43. Opportunity Schema

```json
{
  "summary": "...",

  "stage": "EARLY_OPPORTUNITY",

  "reasoning_summary": "...",

  "target_priority": [
    {
      "organization_id": "...",
      "department_id": "...",
      "reason": "..."
    }
  ],

  "risks": [],

  "recommended_actions": []
}
```

---

# 44. Scoring Node

节点：

```text
score_result
```

必须是：

```text
Deterministic Code Node
```

不是 LLM Node。

---

# 45. 商机评分

一期建议：

```text
Policy Signal             10%
Need Clarity              15%
Responsibility Match      20%
Department Match          10%
Company Capability        15%
Historical Case           10%
Customer Relationship     10%
Project/Procurement       10%
```

---

# 46. Opportunity Score

表示：

> 商业机会价值。

---

# 47. Confidence Score

单独计算：

```text
Evidence Sufficiency
Evidence Reliability
Organization Certainty
Department Certainty
Need Certainty
Evidence Conflict
Reviewer Confidence
```

所以：

```text
Opportunity Score != Confidence
```

---

# 48. Reviewer Agent

Reviewer 是独立 LangGraph Node：

```text
review
```

建议使用独立 Prompt。

条件允许时甚至使用与主推理不同模型。

---

# 49. Reviewer 检查

至少检查：

```text
Evidence Grounding
Organization Accuracy
Department Accuracy
Need Overreach
Procurement Overclaim
Capability Overclaim
Evidence Conflict
Unsupported Statement
```

---

# 50. Review Result

```json
{
  "decision": "RETRY",

  "confidence": 0.62,

  "issues": [
    {
      "type": "MISSING_DEPARTMENT_EVIDENCE",
      "message": "缺乏可靠处室职责依据"
    }
  ],

  "retry_targets": [
    "ORGANIZATION"
  ]
}
```

---

# 51. Conditional Routing

Reviewer 后使用 LangGraph：

```text
Conditional Edge
```

路由：

```text
APPROVE
→ finalize

MISSING_POLICY
→ policy_research

MISSING_ORG
→ organization_research

MISSING_CASE
→ case_research

LOW_CONFIDENCE
→ research_more

HUMAN_REQUIRED
→ human_review

FAILED
→ fallback
```

---

# 52. Retry Control

必须设置：

```text
max_retry_count = 2
```

禁止：

```text
Reviewer
→ Research
→ Reviewer
→ Research
→ 无限循环
```

LangGraph 自身也有递归/步骤控制机制，但业务层仍应明确限制 Retry。

---

# 53. Research Again

Research Again 不是重复搜索原 Query。

Reviewer要输出：

```text
missing_question
```

例如：

> “缺乏城建处负责城市生命线建设的直接职责依据。”

Research Planner生成新的定向查询。

---

# 54. Human-in-the-loop

当以下情况出现：

```text
Opportunity Score 高
但 Confidence 低

多个部门严重冲突

内部知识和公开知识冲突

Reviewer连续不通过

需要人工确认后写入专家知识
```

触发：

```text
interrupt()
```

LangGraph 的 Interrupt 会保存当前 Graph State，等待外部输入后再从同一个 thread 恢复，非常适合这一场景。

---

# 55. Human Review Node

例如：

```python
decision = interrupt({
    "type": "EXPERT_REVIEW",
    "question": "请选择实际牵头部门",
    "candidates": [...]
})
```

外部可以是：

```text
Dify
Web后台
管理端
```

---

# 56. Resume

外部提交人工决定：

```text
Command(resume=...)
```

恢复同一个：

```text
thread_id
```

继续执行。

---

# 57. Finalize Node

节点：

```text
finalize_result
```

负责：

* 汇总最终结果
* 绑定所有 Evidence
* 生成输出 Schema
* 写 Expert Run
* 写审计
* 更新状态为 Completed

---

# 58. 最终 API 输出

```json
{
  "run_id": "...",

  "expert": {
    "id": "housing_digitalization",
    "version": "1.0"
  },

  "event": {},

  "opportunity": {
    "score": 87,
    "level": "A",
    "confidence": 0.84,
    "stage": "EARLY_OPPORTUNITY"
  },

  "needs": [],

  "organizations": [],

  "departments": [],

  "capabilities": [],

  "solutions": [],

  "cases": [],

  "evidence": [],

  "risks": [],

  "recommended_actions": [],

  "review": {}
}
```

---

# 59. Expert Subgraph 设计

随着专家越来越复杂，不建议所有 Node 都堆在一个巨大 Graph。

采用：

```text
Main Graph
│
├── Research Subgraph
│
├── Need Analysis Subgraph
│
├── Organization Subgraph
│
├── Capability Subgraph
│
└── Review Subgraph
```

---

# 60. Research Subgraph

```text
START
 ↓
plan
 ↓
fan-out
 ├ policy
 ├ industry
 ├ organization
 ├ internal
 └ cases
 ↓
merge
 ↓
END
```

---

# 61. Organization Subgraph

```text
START
 ↓
extract_topics
 ↓
candidate_org
 ↓
responsibility_match
 ↓
candidate_department
 ↓
department_research
 ↓
rerank
 ↓
END
```

---

# 62. Review Subgraph

```text
START
 ↓
grounding_check
 ↓
role_check
 ↓
overclaim_check
 ↓
conflict_check
 ↓
decision
 ↓
END
```

---

# 63. LangGraph Store

必须明确：

```text
Checkpoint
≠
Expert Knowledge
```

Checkpoint 负责当前运行状态。

Expert Knowledge 是长期跨运行的行业知识。

LangGraph 官方也区分：

* Checkpointer：thread级状态；
* Store：跨 thread 的长期数据。

一期可以暂时不直接用 LangGraph Store 保存正式专家知识，而继续使用自己的 PostgreSQL Expert Knowledge Repository。

这样知识治理更可控。

---

# 64. Knowledge Learning Graph

知识学习建议单独设计一个 Graph：

```text
Feedback
 ↓
analyze_feedback
 ↓
compare_prediction
 ↓
extract_candidate
 ↓
check_existing_knowledge
 ↓
assess_reusability
 ↓
human_review
 ↓
       ┌───────────┐
       │ interrupt │
       └─────┬─────┘
             ↓
      approve / reject
             ↓
     publish_knowledge
             ↓
            END
```

---

# 65. Feedback

商务人员反馈：

```json
{
  "run_id": "...",

  "actual_organization": "...",

  "actual_department": "...",

  "actual_need": "...",

  "has_opportunity": true,

  "comment": "..."
}
```

---

# 66. Knowledge Candidate Agent

AI根据：

```text
原预测
+
实际结果
```

提炼：

```text
哪些东西具有可复用价值？
```

不是简单原文入库。

---

# 67. 候选知识判断

判断：

```text
这是一次偶然情况？
还是一个行业规律？
```

维度：

```text
重复性
证据可信度
地域范围
适用行业
是否可以泛化
是否已有类似知识
是否与已有知识冲突
```

---

# 68. Knowledge Candidate Schema

```json
{
  "knowledge_type": "DEPARTMENT_ROLE",

  "content": "...",

  "scope": {
    "industry": "housing",
    "region": "..."
  },

  "confidence": 0.80,

  "source_cases": [],

  "conflicting_knowledge": []
}
```

---

# 69. Knowledge Approval

必须：

```text
Human-in-the-loop
```

批准后才能进入：

```text
Expert Knowledge
```

---

# 70. Expert Knowledge 生命周期

```text
Candidate
 ↓
APPROVED
 ↓
ACTIVE
 ↓
NEEDS_REVERIFY
 ↓
UPDATED / EXPIRED
```

---

# 71. LangGraph Streaming

Expert分析时间可能达到：

```text
10～60秒
```

API需要支持 Streaming。

前端可实时显示：

```text
正在分析事件...
正在查询政策...
正在分析主管单位...
正在分析处室职责...
正在匹配我方能力...
正在进行专家复核...
```

但不展示模型私有推理过程。

只展示：

```text
Node Status
```

---

# 72. Streaming API

建议：

```http
POST /api/v1/expert/analyze/stream
```

通过：

```text
SSE
```

输出阶段事件。

---

# 73. API

核心：

```http
POST /api/v1/expert/analyze
```

异步：

```http
POST /api/v1/expert/runs
```

查询：

```http
GET /api/v1/expert/runs/{run_id}
```

恢复：

```http
POST /api/v1/expert/runs/{run_id}/resume
```

反馈：

```http
POST /api/v1/expert/runs/{run_id}/feedback
```

---

# 74. Resume API

请求：

```json
{
  "decision": {
    "department_id": "...",
    "comment": "..."
  }
}
```

内部转换：

```python
Command(resume=decision)
```

---

# 75. Node Retry

技术错误：

```text
LLM Timeout
HTTP 503
Search Timeout
```

使用 Node RetryPolicy。

业务 Reviewer Retry 与技术 Retry 分开。

LangGraph本身提供 Node 级 RetryPolicy 等相关机制。

---

# 76. 业务 Retry

例如：

```text
Evidence不足
```

不是 RetryPolicy。

而是：

```text
Conditional Edge
→ Research Again
```

两种绝对不能混。

---

# 77. Prompt Management

每个 Agent Node 使用独立 Prompt：

```text
event_analyzer_prompt
research_planner_prompt
need_agent_prompt
organization_agent_prompt
department_agent_prompt
capability_agent_prompt
opportunity_prompt
reviewer_prompt
knowledge_candidate_prompt
```

---

# 78. Prompt Version

每次 Run 记录：

```text
Prompt Version
Expert Version
Graph Version
Rule Version
Scoring Version
Model Version
```

---

# 79. Structured Output

全部核心节点：

```text
LLM
↓
Pydantic Schema
```

不能用自然语言解析。

例如：

```python
class NeedAnalysis(BaseModel):
    needs: list[Need]
```

---

# 80. LLM Gateway

统一：

```python
class LLMGateway:

    async def structured_generate(
        model_profile,
        prompt,
        schema
    )

    async def generate(...)

    async def embed(...)

    async def rerank(...)
```

---

# 81. Model Routing

可以按 Node 配模型：

```text
Router
→ 快速低成本模型

Event Analyzer
→ 中等模型

Research Planner
→ 中等模型

Need Agent
→ 强推理模型

Organization Agent
→ 强推理模型

Reviewer
→ 强推理模型

Knowledge Candidate
→ 中等模型
```

---

# 82. Knowledge Engine 数据存储

```text
PostgreSQL
├ Organization
├ Department
├ Responsibility
├ Capability
├ Solution
├ Case
├ Expert Knowledge
└ Metadata

pgvector
├ Policy Chunk
├ Industry Chunk
├ Case Chunk
└ Expert Knowledge

OpenSearch
├ Keyword Search
├ Policy Search
└ Organization Search

MinIO
└ Raw Documents
```

---

# 83. Redis

使用：

```text
Search Cache
Model Response Cache
Task Coordination
Rate Limit
Short-lived Runtime Data
```

不作为正式 Expert Memory。

---

# 84. 工程目录

```text
expert-engine/

├── app/
│   ├── api/
│   │   ├── runs.py
│   │   ├── experts.py
│   │   ├── knowledge.py
│   │   └── feedback.py
│   │
│   ├── graph/
│   │   ├── main.py
│   │   ├── state.py
│   │   ├── routing.py
│   │   └── checkpoint.py
│   │
│   ├── subgraphs/
│   │   ├── research/
│   │   ├── organization/
│   │   ├── capability/
│   │   ├── review/
│   │   └── learning/
│   │
│   ├── nodes/
│   │   ├── initialize.py
│   │   ├── expert_router.py
│   │   ├── event_analyzer.py
│   │   ├── research_planner.py
│   │   ├── need_agent.py
│   │   ├── opportunity.py
│   │   └── finalize.py
│   │
│   ├── experts/
│   │   ├── profiles/
│   │   ├── rules/
│   │   └── prompts/
│   │
│   ├── knowledge/
│   │   ├── retrieval.py
│   │   ├── hybrid.py
│   │   ├── reranker.py
│   │   └── ingestion.py
│   │
│   ├── organization/
│   │   ├── matcher.py
│   │   └── responsibility.py
│   │
│   ├── capability/
│   │   └── matcher.py
│   │
│   ├── evidence/
│   │   └── engine.py
│   │
│   ├── scoring/
│   │   └── engine.py
│   │
│   ├── llm/
│   │   ├── gateway.py
│   │   └── providers/
│   │
│   ├── schemas/
│   ├── repositories/
│   └── models/
│
├── evaluation/
├── migrations/
├── tests/
└── deploy/
```

---

# 85. Graph 伪代码

核心实现结构：

```python
builder = StateGraph(ExpertState)

builder.add_node("initialize", initialize)
builder.add_node("route_expert", route_expert)
builder.add_node("analyze_event", analyze_event)

builder.add_node("research", research_subgraph)

builder.add_node("infer_needs", infer_needs)

builder.add_node(
    "organization",
    organization_subgraph
)

builder.add_node(
    "capability",
    capability_subgraph
)

builder.add_node(
    "synthesize",
    synthesize_opportunity
)

builder.add_node(
    "score",
    score_result
)

builder.add_node(
    "review",
    review_subgraph
)

builder.add_node(
    "human_review",
    human_review
)

builder.add_node(
    "finalize",
    finalize
)
```

主要路线：

```python
START -> initialize

initialize -> route_expert

route_expert -> analyze_event

analyze_event -> research

research -> infer_needs

infer_needs -> organization

organization -> capability

capability -> synthesize

synthesize -> score

score -> review
```

Reviewer：

```text
APPROVE
→ finalize

RESEARCH_MORE
→ research

HUMAN_REVIEW
→ human_review

FAIL
→ finalize
```

---

# 86. 可观测性

每个 Node 必须记录：

```text
开始时间
完成时间
Model
Token
Cost
Input IDs
Output
Evidence IDs
Error
Retry
```

---

# 87. Trace

一个 Run 应该能够看到：

```text
09:32:01 initialize
09:32:01 route_expert
09:32:02 event_analysis
09:32:05 policy_research
09:32:05 organization_research
09:32:06 case_research
09:32:09 merge
09:32:11 need_analysis
09:32:14 organization
09:32:17 department
09:32:20 capability
09:32:23 synthesize
09:32:24 scoring
09:32:27 reviewer
09:32:28 complete
```

---

# 88. Evaluation

一期必须搭建：

```text
Expert Evaluation Pipeline
```

不能只测最终答案。

还需要测每一个 Node。

---

# 89. Node Evaluation

### Event Agent

测试：

```text
Industry Accuracy
Topic Accuracy
Task Extraction
```

### Need Agent

```text
Need Precision
Need Recall
Overreach
```

### Organization Agent

```text
Top1
Top3 Recall
```

### Department Agent

```text
Top1
Top3 Recall
```

### Reviewer

```text
Error Detection Rate
False Positive Rate
```

---

# 90. End-to-End Evaluation

核心：

```text
Opportunity Detection Accuracy

Need Precision

Organization Top3 Recall

Department Top3 Recall

Evidence Coverage

Evidence Correctness

Hallucination Rate
```

---

# 91. 一期目标

建议：

```text
Event Accuracy ≥ 90%

Need Precision ≥ 80%

Organization Top3 ≥ 85%

Department Top3 ≥ 75%

Capability Precision ≥ 80%

Evidence Coverage ≥ 90%

Unsupported Critical Claim ≤ 5%
```

---

# 92. 首个专家

一期不做多个浅专家。

建议：

```text
1 个主专家
```

做深。

例如：

```text
住建数字化专家
```

---

# 93. 第一批数据

建议：

```text
政策                    100+
组织机构                重点客户
部门职责                重点客户
历史项目                30+
解决方案                20+
公司案例                30+
真实商务案例            50+
Benchmark               50～100
```

---

# 94. 一期开发阶段

## Phase 0

方法论：

```text
Expert Profile
Output Schema
Organization Model
Need Taxonomy
Evidence Model
Scoring
Benchmark
```

---

## Phase 1

LangGraph基础：

```text
State
Checkpoint
Run
FastAPI
LLM Gateway
Graph Runtime
Streaming
```

---

## Phase 2

Research：

```text
Knowledge Engine
Hybrid Search
Research Planner
Research Subgraph
Evidence
```

---

## Phase 3

核心专家：

```text
Need Agent
Organization Agent
Department Agent
Capability Agent
```

---

## Phase 4

闭环：

```text
Opportunity Agent
Scoring
Reviewer
Retry Routing
HITL
```

---

## Phase 5

学习：

```text
Feedback
Learning Graph
Knowledge Candidate
Human Approval
Expert Knowledge
```

---

## Phase 6

外围 Demo：

```text
Dify
→ Expert API
→ Result
→ Feedback
```

---

# 95. 一期不做

一期暂不建设：

```text
大规模 autonomous web agent
无限制自主 research
复杂多专家辩论
几十个 sub-agent
Fine-tuning
销售自动触达
完整CRM
复杂知识图谱
```

---

# 96. 一期最重要的设计约束

### 约束一

LLM不能绕过 Knowledge Engine 直接做关键事实判断。

### 约束二

LLM不能随意编单位、部门。

### 约束三

重要结论必须有 Evidence ID。

### 约束四

Reviewer不能与第一次分析共用同一份推理输出作为唯一依据。

### 约束五

Score必须由代码计算。

### 约束六

商务反馈不能自动进入正式专家知识库。

### 约束七

Graph Retry必须有限。

### 约束八

Checkpoint只是运行记忆，不等于专家知识。

---

# 97. 最终一期架构

```text
                   Dify / Web / CRM
                         │
                         ▼
                     FastAPI
                         │
                         ▼
                  LangGraph Runtime
                         │
               ┌─────────┴─────────┐
               │                   │
        Expert Main Graph     Learning Graph
               │                   │
      ┌────────┼────────┐          │
      ▼        ▼        ▼          ▼
 Research    Need     Organization Feedback
 Subgraph   Agent      Subgraph      │
      │        │        │        Candidate
      └────────┼────────┘            │
               ▼                  Interrupt
          Capability                 │
               ▼                  Approval
          Opportunity                │
               ▼                     ▼
            Scoring           Expert Knowledge
               ▼
            Reviewer
               │
       ┌───────┼────────┐
       ▼       ▼        ▼
    Approve  Retry     HITL
       │       │        │
       └───────┴────────┘
               ▼
          Final Result
```

---

# 98. 一期核心交付物

必须交付：

```text
Expert Engine API

LangGraph Main Graph

Research Subgraph

Organization Subgraph

Review Subgraph

Learning Graph

Expert State Schema

Checkpoint机制

Human Interrupt机制

Knowledge Engine

Organization Engine

Capability Engine

Evidence Engine

Scoring Engine

Expert Profile Framework

Prompt Version Framework

LLM Gateway

Benchmark

Evaluation Pipeline

首个行业 Expert

Dify 临时 Demo
```

---

# 99. 最终定位

一期结束以后，系统核心不应该是：

> “我们做了一个 LangGraph Agent。”

而应该是：

> **我们建立了一套以 LangGraph 为推理编排基础，以行业知识、组织职责、企业能力、历史案例和人工验证经验为核心数据资产的专业 Expert Engine。**

LangGraph解决：

> **专家怎样思考和流转。**

Knowledge Engine解决：

> **专家知道什么。**

Organization Engine解决：

> **专家知道谁负责。**

Capability Engine解决：

> **专家知道我们能做什么。**

Evidence Engine解决：

> **专家为什么这么判断。**

Reviewer解决：

> **专家如何避免错误。**

Learning Graph解决：

> **专家如何通过商务实践逐渐变得更准确。**

因此一期真正需要形成的核心飞轮是：

```text
事件
 ↓
Research
 ↓
Expert Reasoning
 ↓
Evidence Grounding
 ↓
商务判断
 ↓
Reviewer
 ↓
人工实践
 ↓
反馈
 ↓
Knowledge Candidate
 ↓
专家审核
 ↓
Expert Knowledge
 ↓
下一次 LangGraph Research / Reasoning
```

最终实现：

> **一个可以随着真实商务实践持续积累行业经验的 LangGraph 行业专家智能研判引擎。**

