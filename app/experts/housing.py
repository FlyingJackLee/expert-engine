"""Housing-digitalization expert implementation, isolated from graph orchestration."""
from app.experts.prompts.housing import (EVENT_ANALYZER_V1,
                                         EVIDENCE_CRITIC_V1,
                                         KNOWLEDGE_EXTRACTION_V1,
                                         NEED_REASONING_V1,
                                         OPPORTUNITY_SYNTHESIS_V1,
                                         RESEARCH_PLANNER_V1)
from app.experts.runtime import ExpertRuntime


runtime = ExpertRuntime(
    event_analyzer_prompt=EVENT_ANALYZER_V1,
    research_planner_prompt=RESEARCH_PLANNER_V1,
    opportunity_synthesis_prompt=OPPORTUNITY_SYNTHESIS_V1,
    evidence_critic_prompt=EVIDENCE_CRITIC_V1,
    need_reasoning_prompt=NEED_REASONING_V1,
    knowledge_extraction_prompt=KNOWLEDGE_EXTRACTION_V1,
    topic_keywords={
        "城市生命线": ("生命线", "燃气", "供水", "排水", "桥梁", "监测预警"),
        "CIM": ("CIM", "城市信息模型"),
        "城市更新": ("城市更新", "老旧小区", "更新改造"),
    },
    default_topic="住建数字化",
)
