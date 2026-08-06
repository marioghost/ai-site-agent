"""RAG planning v2 — pre-retrieval orchestration and coverage validation.

Import leaf modules directly (e.g. ``rag_planning.contracts``) rather than
relying on this package init. Eager re-exports here previously created an
import cycle through evidence_planning → retrieval_engine → SI constants.
"""
