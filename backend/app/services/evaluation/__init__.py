"""RFC-100 Step 049 — offline Memory Assist / Canonical Shadow evaluation.

Operations / Evaluation ownership. Consumes frozen diagnostics from Steps 047–048.
Must never be imported by chat, Rag, Reasoning runtime, Retrieval, EA, Language, or Memory.
"""
from __future__ import annotations

from app.services.evaluation.memory_assist_eval_aggregator import aggregate_memory_assist_eval
from app.services.evaluation.memory_assist_eval_recommendation import (
    EvalRecommendation,
    recommend_memory_assist_staging,
)
from app.services.evaluation.memory_assist_eval_report import (
    render_markdown_report,
    report_to_json_dict,
    write_json_report,
    write_markdown_report,
)
from app.services.evaluation.memory_assist_eval_types import (
    CorpusEvalSnapshot,
    EvalFlagSnapshot,
    EvalRunMetadata,
    EvalTurnRecord,
    MemoryAssistEvalReportV1,
    MemoryAssistEvalThresholdsV1,
)

__all__ = [
    "CorpusEvalSnapshot",
    "EvalFlagSnapshot",
    "EvalRecommendation",
    "EvalRunMetadata",
    "EvalTurnRecord",
    "MemoryAssistEvalReportV1",
    "MemoryAssistEvalThresholdsV1",
    "aggregate_memory_assist_eval",
    "recommend_memory_assist_staging",
    "render_markdown_report",
    "report_to_json_dict",
    "write_json_report",
    "write_markdown_report",
]
