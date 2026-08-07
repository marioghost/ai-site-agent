"""Orchestrator for deterministic Knowledge Profile generation pipeline."""
from __future__ import annotations

import time
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.settings import Settings
from app.models.source import Source
from app.repositories.settings_repository import SettingsRepository
from app.schemas.knowledge_profile import KnowledgeProfile
from app.schemas.knowledge_profile_generation import (
    ConfidenceItem,
    GenerationPreview,
    WebsiteStructureSummary,
)
from app.services.knowledge_profile_generation.alias_utils import dedupe_topic_aliases
from app.services.knowledge_profile_generation.auto_repair import ProfileAutoRepair
from app.services.knowledge_profile_generation.content_hint_discovery import (
    ContentHintDiscovery,
)
from app.services.knowledge_profile_generation.confidence_engine import ConfidenceEngine
from app.services.knowledge_profile_generation.data_loader import IndexedPageLoader
from app.services.knowledge_profile_generation.entity_extractor import EntityExtractor
from app.services.knowledge_profile_generation.knowledge_graph import KnowledgeGraphBuilder
from app.services.knowledge_profile_generation.llm_refiner import LlmRefiner
from app.services.knowledge_profile_generation.metadata_extractor import (
    WebsiteMetadataExtractor,
)
from app.services.knowledge_profile_generation.models import PipelineContext
from app.services.knowledge_profile_generation.organization_detector import (
    OrganizationDetector,
)
from app.services.knowledge_profile_generation.profile_assembler import ProfileAssembler
from app.services.knowledge_profile_generation.statistics_builder import StatisticsBuilder
from app.services.knowledge_profile_generation.structure_analyzer import (
    WebsiteStructureAnalyzer,
)
from app.services.knowledge_profile_generation.topic_discovery import TopicDiscovery
from app.services.knowledge_profile_generation.validator import KnowledgeProfileValidator
from app.services.knowledge_profile_service import KnowledgeProfileService

StageCallback = Callable[[str, int], None]


class KnowledgeProfilePipeline:
    STAGES = [
        ("metadata_extraction", 8),
        ("website_analysis", 18),
        ("statistics", 25),
        ("entity_extraction", 35),
        ("organization_detection", 45),
        ("topic_discovery", 55),
        ("content_hint_discovery", 65),
        ("knowledge_graph", 70),
        ("profile_assembly", 75),
        ("llm_refinement", 85),
        ("validation", 92),
        ("auto_repair", 96),
        ("preview", 99),
        ("complete", 100),
    ]

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings: Settings = SettingsRepository(db).get_or_create()
        self.confidence = ConfidenceEngine()

    def run(
        self,
        *,
        use_llm: bool = True,
        merge_identity: bool = False,
        on_stage: StageCallback | None = None,
    ) -> tuple[GenerationPreview, dict]:
        t0 = time.monotonic()
        ctx = PipelineContext(site_url=self.settings.site_url or "")

        def stage(name: str, pct: int) -> None:
            if on_stage:
                on_stage(name, pct)

        loader = IndexedPageLoader(self.db, self.settings)
        ctx.pages = loader.load()
        errors = loader.prereq_errors(ctx.pages)
        if errors:
            raise ValueError("; ".join(errors))

        # Stage 1: Metadata
        stage("metadata_extraction", 8)
        t_s = time.monotonic()
        ctx.metadata = WebsiteMetadataExtractor().extract(ctx.pages, ctx.site_url)
        ctx.report.stage_timings["metadata_extraction"] = round(time.monotonic() - t_s, 2)

        # Stage 2: Structure
        stage("website_analysis", 18)
        t_s = time.monotonic()
        ctx.hierarchy = WebsiteStructureAnalyzer().analyze(ctx.pages, ctx.metadata)
        ctx.report.stage_timings["website_analysis"] = round(time.monotonic() - t_s, 2)

        # Statistics
        stage("statistics", 25)
        file_count = self.db.scalar(
            select(func.count())
            .select_from(Source)
            .where(
                Source.status == "indexed",
                Source.source_type.notin_(sorted(IndexedPageLoader.PAGE_TYPES)),
            )
        ) or 0
        chunk_count = self.db.scalar(select(func.count()).select_from(Chunk)) or 0
        ctx.statistics = StatisticsBuilder().build(
            ctx.pages,
            ctx.metadata,
            file_count=int(file_count),
            chunk_count=int(chunk_count),
        )
        ctx.report.pages_analyzed = ctx.statistics.indexed_page_count

        # Stage 4: Entities (before org for frequency, but org detection uses metadata)
        stage("entity_extraction", 35)
        ctx.entities = EntityExtractor().extract(ctx.pages, ctx.metadata)

        # Stage 3: Organization
        stage("organization_detection", 45)
        ctx.organization = OrganizationDetector().detect(
            ctx.metadata, ctx.pages, ctx.hierarchy
        )
        ctx.entities = EntityExtractor().extract(
            ctx.pages, ctx.metadata, organization_name=ctx.organization.name
        )
        ctx.report.entities_extracted = len(ctx.entities)

        # Stage 5: Topics
        stage("topic_discovery", 55)
        ctx.topics = TopicDiscovery().discover(
            ctx.pages,
            ctx.hierarchy,
            ctx.entities,
            organization_name=ctx.organization.name,
        )
        ctx.report.topics_discovered = len(ctx.topics)

        # Stage 6: Content hints
        stage("content_hint_discovery", 65)
        hint_discovery = ContentHintDiscovery()
        ctx.hint_candidates = hint_discovery.discover(ctx.pages, ctx.hierarchy, ctx.topics)
        ctx.topics = hint_discovery.validate_topic_hints(ctx.topics)
        registered = hint_discovery.registered_ids()
        ctx.extras["registered_hint_ids"] = registered
        ctx.extras["hint_rules"] = hint_discovery.to_rules()
        ctx.report.hints_generated = len(ctx.hint_candidates)

        # Knowledge graph
        stage("knowledge_graph", 70)
        ctx.knowledge_graph = KnowledgeGraphBuilder().build(
            ctx.pages, ctx.hierarchy, ctx.entities
        )

        # Assemble profile
        stage("profile_assembly", 75)
        assembled = ProfileAssembler().assemble(ctx)
        ctx.profile = assembled.profile

        # LLM refinement
        if use_llm:
            stage("llm_refinement", 85)
            refiner = LlmRefiner()
            refined, llm_stats = refiner.refine(ctx, self.settings)
            if refined is not None:
                ctx.profile = refined
            ctx.report.llm_used = llm_stats.get("llm_used", False)
            ctx.report.llm_tokens = llm_stats.get("llm_tokens", 0)
            if llm_stats.get("llm_error"):
                ctx.report.warnings.append(
                    f"LLM refinement skipped: {llm_stats['llm_error']}"
                )

        if merge_identity:
            current = KnowledgeProfileService.from_settings(self.settings)
            if current.organization_name:
                ctx.profile.organization_name = current.organization_name
                ctx.profile.site_display_name = (
                    current.site_display_name or current.organization_name
                )
            if current.organization_aliases:
                ctx.profile.organization_aliases = list(
                    dict.fromkeys(
                        current.organization_aliases + ctx.profile.organization_aliases
                    )
                )

        ctx.profile, _ = dedupe_topic_aliases(ctx.profile)

        # Validation
        stage("validation", 92)
        validator = KnowledgeProfileValidator()
        issues = validator.validate(
            ctx.profile,
            registered_hint_ids=registered,
            allowed_topic_ids={t.id for t in ctx.topics},
        )
        ctx.validation_issues = issues

        # Auto repair
        stage("auto_repair", 96)
        repairer = ProfileAutoRepair()
        ctx.profile, ctx.validation_issues, fixes = repairer.repair(
            ctx.profile,
            ctx.validation_issues,
            organization=ctx.organization,
            topics=ctx.topics,
            hint_candidates=ctx.hint_candidates,
        )
        ctx.report.validator_fixes = fixes

        # Re-validate after repair
        remaining = validator.validate(
            ctx.profile,
            registered_hint_ids=set(r.content_type_hint for r in ctx.profile.content_hint_rules),
            allowed_topic_ids={t.id for t in ctx.topics},
        )
        ctx.validation_issues = remaining
        for issue in remaining:
            if issue.severity == "warning":
                ctx.report.warnings.append(issue.message)

        from app.services.knowledge_profile_sanitize import sanitize_profile_for_persist

        assert ctx.profile is not None
        ctx.profile = sanitize_profile_for_persist(ctx.profile)

        stage("preview", 99)
        preview = self._build_preview(ctx, ctx.profile)
        ctx.report.generation_seconds = round(time.monotonic() - t0, 2)
        ctx.report.confidence_distribution = self.confidence.distribution(
            [t.confidence for t in ctx.topics]
            + ([ctx.organization.confidence] if ctx.organization else [])
        )

        analytics = ctx.report.model_dump()
        analytics["errors"] = [
            i.message for i in ctx.validation_issues if i.severity == "error"
        ]
        analytics["validation_issues"] = [i.model_dump() for i in ctx.validation_issues]
        analytics["preset_seed"] = ctx.hierarchy.preset_seed

        stage("complete", 100)
        return preview, analytics

    def _build_preview(
        self, ctx: PipelineContext, profile: KnowledgeProfile
    ) -> GenerationPreview:
        assert ctx.organization is not None
        assert ctx.hierarchy is not None
        assert ctx.statistics is not None

        org_evidence = "; ".join(
            f"✓ {e.source}" + (f" ({e.detail})" if e.detail else "")
            for e in ctx.organization.evidence[:8]
        )

        structure = WebsiteStructureSummary(
            indexed_page_count=ctx.statistics.indexed_page_count,
            indexed_file_count=ctx.statistics.indexed_file_count,
            total_chunks=ctx.statistics.total_chunks,
            site_url=ctx.statistics.site_url,
            top_url_segments=ctx.statistics.top_url_segments,
            sample_titles=[p.title for p in ctx.pages[:40] if p.title],
            sample_headings=list(ctx.statistics.heading_counts.keys())[:40],
            document_type_counts=ctx.statistics.document_type_counts,
            content_hint_counts={
                h.hint_id: h.page_count for h in ctx.hint_candidates
            },
            homepage_excerpt=profile.site_subject,
        )

        return GenerationPreview(
            organization=ConfidenceItem(
                value=ctx.organization.name,
                confidence=ctx.organization.confidence,
                detail=org_evidence,
            ),
            website_type=ConfidenceItem(
                value=ctx.hierarchy.preset_seed,
                confidence=ctx.hierarchy.preset_confidence,
                detail=ctx.hierarchy.preset_secondary or "",
            ),
            website_type_secondary=(
                ConfidenceItem(
                    value=ctx.hierarchy.preset_secondary,
                    confidence=0.4,
                )
                if ctx.hierarchy.preset_secondary
                else None
            ),
            topics=[
                ConfidenceItem(
                    value=t.title,
                    confidence=t.confidence,
                    detail="; ".join(
                        f"✓ {e.source}" for e in t.evidence[:5]
                    )
                    or f"key={t.id}",
                    page_count=t.page_count,
                )
                for t in ctx.topics
            ],
            aliases=[
                ConfidenceItem(value=a, confidence=0.7, detail="alias")
                for a in ctx.organization.aliases
            ],
            document_types=[
                ConfidenceItem(
                    value=dt,
                    confidence=0.8,
                    page_count=count,
                )
                for dt, count in ctx.statistics.document_type_counts.items()
            ],
            overview_patterns=[
                ConfidenceItem(value=p, confidence=0.85) for p in profile.overview_query_patterns[:10]
            ],
            profile=profile,
            website_structure=structure,
            preset_seed=ctx.hierarchy.preset_seed,
            low_confidence_keys=self._low_confidence_keys(ctx),
            entities=[
                ConfidenceItem(
                    value=f"{e.name} ({e.entity_type})",
                    confidence=e.confidence,
                    detail=f"{e.frequency} hits",
                    page_count=len(e.pages),
                )
                for e in ctx.entities[:25]
            ],
            content_hints=[
                ConfidenceItem(
                    value=h.hint_id,
                    confidence=h.confidence,
                    detail=", ".join(h.patterns[:3]),
                    page_count=h.page_count,
                )
                for h in ctx.hint_candidates
            ],
            warnings=ctx.report.warnings,
            validation_issues=[i.model_dump() for i in ctx.validation_issues],
            analytics=ctx.report.model_dump(),
        )

    def _low_confidence_keys(self, ctx: PipelineContext) -> list[str]:
        keys: list[str] = []
        if ctx.organization and ctx.organization.confidence < 0.55:
            keys.append("organization")
        if ctx.hierarchy and ctx.hierarchy.preset_confidence < 0.55:
            keys.append("website_type")
        if len(ctx.topics) < 2:
            keys.append("topics")
        for t in ctx.topics:
            if t.confidence < 0.55:
                keys.append(f"topic:{t.id}")
        return keys
