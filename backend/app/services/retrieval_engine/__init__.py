"""Modular retrieval engine — document-first RAG pipeline."""

from app.services.retrieval_engine.context_builder import RetrievalContextBuilder
from app.services.retrieval_engine.diagnostics import PipelineDiagnostics
from app.services.retrieval_engine.diagnostics_builder import DiagnosticsBuilder
from app.services.retrieval_engine.document_aggregator import DocumentAggregator
from app.services.retrieval_engine.document_reranker import DocumentReranker
from app.services.retrieval_engine.document_scorer import DocumentScorer
from app.services.retrieval_engine.pipeline import DocumentFirstRetrievalPipeline
from app.services.retrieval_engine.prompt_builder import CompactPromptBuilder
from app.services.retrieval_engine.retrieval_profiler import RetrievalProfiler
from app.services.retrieval_engine.semantic_expansion import SemanticExpansionService

__all__ = [
    "CompactPromptBuilder",
    "DiagnosticsBuilder",
    "DocumentAggregator",
    "DocumentFirstRetrievalPipeline",
    "DocumentReranker",
    "DocumentScorer",
    "PipelineDiagnostics",
    "RetrievalContextBuilder",
    "RetrievalProfiler",
    "SemanticExpansionService",
]
