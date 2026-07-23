"""Background indexing worker.

Runs a full-site indexing job in a single background thread. Only one job may
run at a time. Supports a cooperative stop flag and persists progress to the
`index_jobs` table (including progress_json for nested status counters).

Discovery (URL finding) is separate from processing (fetch/embed/index).
The per-run page limit applies to selected processing candidates only.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field

import httpx

from app.core.config import get_config
from app.core.database import SessionLocal
from app.core.job_progress_tracker import JobProgressThrottle
from app.core.logging import get_logger
from app.models.index_job import IndexJob
from app.repositories.index_job_repository import IndexJobRepository
from app.repositories.job_event_repository import JobEventRepository
from app.repositories.settings_repository import SettingsRepository
from app.repositories.source_repository import SourceRepository
from app.services.crawler_service import CrawlFrontier
from app.services.indexing_planner_service import CandidateClass, IndexingPlannerService
from app.services.indexing_progress import IndexingProgress
from app.services.indexing_stages import STAGE_CHECKING_FILE, STAGE_COMPLETED, STAGE_DISCOVERING_URLS, STAGE_FAILED, STAGE_PLANNING_QUEUE, STAGE_PREPARING, STAGE_STOPPED
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.file_fetch_service import FileFetchService
from app.services.indexing_service import IndexingService
from app.services.sitemap_service import SitemapService
from app.utils.time_utils import isoformat_now, utcnow
from app.utils.url_utils import detect_file_type, get_domain, normalize_url

logger = get_logger(__name__)


@dataclass
class _Overrides:
    site_url: str | None = None
    sitemap_url: str | None = None
    crawl_depth: int | None = None
    allowed_domains: list[str] | None = None
    deny_url_patterns: list[str] | None = None
    max_pages_per_run: int | None = None
    max_files_per_run: int | None = None
    scan_mode: str | None = None
    enable_file_indexing: bool | None = None
    scan_all_pages: bool | None = None
    scan_all_files: bool | None = None
    force_reindex: bool = False
    pending_only: bool = False


@dataclass
class _JobLog:
    entries: list[dict] = field(default_factory=list)

    def add(self, level: str, message: str) -> None:
        self.entries.append(
            {"timestamp": isoformat_now(), "level": level, "message": message}
        )
        if len(self.entries) > 500:
            self.entries = self.entries[-500:]


class IndexingWorker:
    """Module-level singleton coordinating background indexing."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._current_job_id: int | None = None
        self._event_repo: JobEventRepository | None = None
        self._progress_throttle: JobProgressThrottle | None = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, overrides: _Overrides) -> int:
        with self._lock:
            if self.is_running():
                raise RuntimeError("An indexing job is already running")
            self._stop_event.clear()
            db = SessionLocal()
            try:
                job = IndexJobRepository(db).create()
                job.started_at = utcnow()
                job.updated_at = utcnow()
                db.add(job)
                db.commit()
                self._current_job_id = job.id
            finally:
                db.close()

            self._thread = threading.Thread(
                target=self._run, args=(self._current_job_id, overrides), daemon=True
            )
            self._thread.start()
            return self._current_job_id

    def stop(self) -> None:
        self._stop_event.set()

    @staticmethod
    def _reached(limit: int, count: int) -> bool:
        return limit > 0 and count >= limit

    def _run(self, job_id: int, overrides: _Overrides) -> None:
        db = SessionLocal()
        job_repo = IndexJobRepository(db)
        event_repo = JobEventRepository(db)
        cfg_progress = get_config()
        self._event_repo = event_repo
        self._progress_throttle = JobProgressThrottle(
            flush_every_items=cfg_progress.progress_flush_every_items,
            flush_interval_seconds=cfg_progress.progress_flush_interval_seconds,
        )
        job = job_repo.get(job_id)
        log = _JobLog()
        progress = IndexingProgress()
        progress.reset_for_job()
        try:
            settings = SettingsRepository(db).get_or_create()
            cfg = self._resolve_config(settings, overrides)
            planner = IndexingPlannerService(
                page_refresh_hours=cfg["page_refresh_hours"],
                file_refresh_hours=cfg["file_refresh_hours"],
                force_reindex=cfg["force_reindex"],
            )

            log.add(
                "info",
                f"Starting indexing. mode={cfg['scan_mode']} "
                f"pending_only={cfg.get('pending_only', False)} "
                f"index_pages={cfg['index_pages']} index_files={cfg['index_files']} "
                f"max_process_pages={'∞' if cfg['max_pages'] == 0 else cfg['max_pages']} "
                f"page_refresh={cfg['page_refresh_hours']}h",
            )
            progress.set_stage(
                STAGE_PREPARING,
                phase="discovery",
                action="Initializing indexing run",
                message="Starting indexing run",
            )
            self._persist_progress(job_repo, job, log, "running", progress, force=True)

            indexer = IndexingService(db, settings)
            source_repo = SourceRepository(db)

            if cfg["pending_only"]:
                progress.run_mode = "pending_only"
                self._run_pending_only(
                    job_repo, job, log, progress, cfg, planner, source_repo, indexer
                )
                return

            frontier = CrawlFrontier(
                cfg["allowed_domains"], cfg["deny_patterns"], cfg["crawl_depth"]
            )

            self._seed_frontier(frontier, cfg, settings, log)

            discovered_page_urls: set[str] = set()
            discovered_file_urls: set[str] = set()
            discovery_pending = 0
            DISCOVERY_COMMIT_EVERY = 50

            # --- Phase 1: discovery (no processing limit) ---
            progress.set_stage(
                STAGE_DISCOVERING_URLS,
                phase="discovery",
                action="Discovering site URLs",
                message="Discovering URLs",
            )
            while frontier.has_next():
                if self._stop_event.is_set():
                    log.add("info", "Stop requested during discovery")
                    self._finalize(job_repo, job, log, "stopped", progress)
                    return

                item = frontier.pop()
                if item is None:
                    break
                frontier.mark_visited(item.url)
                url = normalize_url(item.url)
                file_type = detect_file_type(url)
                is_file = file_type is not None and file_type != "html"

                progress.discovery.discovered_urls += 1
                if is_file:
                    if cfg["discover_files"]:
                        _source, created = source_repo.record_discovery(url, file_type, commit=False)
                        discovery_pending += 1
                        discovered_file_urls.add(url)
                        progress.discovery.discovered_files += 1
                        progress.files.discovered_files += 1
                        if created:
                            progress.discovery.newly_discovered_urls += 1
                        else:
                            progress.discovery.already_known_urls += 1
                    continue

                progress.discovery.discovered_pages += 1
                source, created = source_repo.record_discovery(url, "page", commit=False)
                discovery_pending += 1
                discovered_page_urls.add(url)
                if progress.discovery.discovered_pages % 10 == 1:
                    progress.set_current_url(
                        url,
                        url_type="page",
                        action="Discovering page links",
                        message=f"Discovering: {url}",
                    )
                if created:
                    progress.discovery.newly_discovered_urls += 1
                else:
                    progress.discovery.already_known_urls += 1

                cls = planner.classify(source)
                needs_links = item.depth < cfg["crawl_depth"]
                parsed = None
                if cfg["index_pages"]:
                    if planner.should_fetch_for_discovery(
                        cls, needs_link_expansion=needs_links
                    ):
                        parsed = indexer.parse_page_only(url)
                    elif cls is CandidateClass.FRESH:
                        progress.pages.skipped_fresh_pages += 1
                        log.add(
                            "info",
                            f"Fresh indexed page skipped until next refresh: {url}",
                        )
                else:
                    parsed = indexer.parse_page_only(url)
                    log.add("info", f"[page/discovery] {url}")

                if parsed is not None and needs_links:
                    for link in parsed.links:
                        frontier.add(link, depth=item.depth + 1)
                    if cfg["discover_files"]:
                        for furl, _ftype in parsed.file_links:
                            frontier.add(furl, depth=item.depth + 1)

                if discovery_pending >= DISCOVERY_COMMIT_EVERY:
                    source_repo.commit()
                    discovery_pending = 0
                if progress.discovery.discovered_pages % 100 == 0:
                    self._persist_progress(job_repo, job, log, "running", progress)

            log.add(
                "info",
                f"[discovery] discovered_urls={progress.discovery.discovered_urls} "
                f"pages={progress.discovery.discovered_pages} "
                f"files={progress.discovery.discovered_files} "
                f"known={progress.discovery.already_known_urls} "
                f"new={progress.discovery.newly_discovered_urls}",
            )

            if discovery_pending:
                source_repo.commit()
                discovery_pending = 0

            # --- Phase 2: prioritized page processing ---
            if cfg["index_pages"]:
                page_sources = source_repo.list_page_sources()
                self._process_page_queue(
                    job_repo,
                    job,
                    log,
                    progress,
                    cfg,
                    planner,
                    source_repo,
                    indexer,
                    page_sources,
                )

            # --- Phase 3: prioritized file processing ---
            if cfg["index_files"] and discovered_file_urls:
                progress.set_stage(
                    STAGE_CHECKING_FILE,
                    phase="processing_files",
                    action="Processing files",
                    message="Processing discovered files",
                )
                file_sources = source_repo.list_by_urls(sorted(discovered_file_urls))
                file_queue = [
                    c
                    for c in planner.select_candidates_for_run(
                        file_sources, max_pages_per_run=cfg["max_files"]
                    )
                    if c.source.source_type in cfg["allowed_file_types"]
                ]
                progress.files.queued_files_for_this_run = len(file_queue)
                self._persist_progress(job_repo, job, log, "running", progress, force=True)

                for candidate in file_queue:
                    if self._stop_event.is_set():
                        break
                    if self._reached(cfg["max_files"], progress.files.processed_files):
                        log.add(
                            "info",
                            f"Run file limit reached after {progress.files.processed_files} processed files",
                        )
                        break
                    was_never_indexed = (
                        candidate.source.status or "pending"
                    ).lower() in {"pending", "new"}
                    self._process_file_candidate(
                        candidate.source,
                        indexer,
                        cfg["force_reindex"],
                        progress,
                        log,
                        was_never_indexed=was_never_indexed,
                    )
                    self._persist_progress(job_repo, job, log, "running", progress)

            self._finalize(job_repo, job, log, "completed", progress)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Indexing job crashed")
            log.add("error", f"Job crashed: {exc}")
            try:
                self._finalize(job_repo, job, log, "failed", progress)
            except Exception:  # noqa: BLE001
                pass
        finally:
            db.close()
            with self._lock:
                self._thread = None

    def _run_pending_only(
        self,
        job_repo,
        job,
        log: _JobLog,
        progress: IndexingProgress,
        cfg: dict,
        planner: IndexingPlannerService,
        source_repo: SourceRepository,
        indexer: IndexingService,
    ) -> None:
        log.add(
            "info",
            "Pending-only run: indexing waiting pages (URL discovery skipped)",
        )
        progress.set_stage(
            STAGE_PLANNING_QUEUE,
            phase="planning",
            action="Loading waiting pages",
            message="Preparing pending pages queue",
        )
        self._persist_progress(job_repo, job, log, "running", progress)

        waiting_pages = source_repo.list_waiting_page_sources()
        log.add("info", f"Found {len(waiting_pages)} waiting page(s)")

        if not waiting_pages:
            log.add("info", "No waiting pages to index")
            self._finalize(job_repo, job, log, "completed", progress)
            return

        self._process_page_queue(
            job_repo,
            job,
            log,
            progress,
            cfg,
            planner,
            source_repo,
            indexer,
            waiting_pages,
        )
        self._finalize(job_repo, job, log, "completed", progress)

    def _process_page_queue(
        self,
        job_repo,
        job,
        log: _JobLog,
        progress: IndexingProgress,
        cfg: dict,
        planner: IndexingPlannerService,
        source_repo: SourceRepository,
        indexer: IndexingService,
        page_sources: list,
    ) -> None:
        progress.set_stage(
            STAGE_PLANNING_QUEUE,
            phase="planning",
            action="Planning queue for this run",
            message="Planning page queue",
        )
        preview = planner.build_queue_preview(
            page_sources, max_pages_per_run=cfg["max_pages"]
        )
        progress.apply_queue_preview(preview)
        log.add(
            "info",
            f"[queue] new={preview.new_pages_waiting} "
            f"failed={preview.failed_pages_waiting} "
            f"stale={preview.stale_pages_waiting} "
            f"fresh_skipped={preview.fresh_pages_skipped_until_refresh} "
            f"selected_for_run={preview.queued_pages_for_this_run}",
        )
        self._persist_progress(job_repo, job, log, "running", progress)

        progress.set_stage(
            "fetching_page",
            phase="processing_pages",
            action="Processing selected pages",
            message=f"Processing {preview.queued_pages_for_this_run} pages",
        )
        queue = planner.select_candidates_for_run(
            page_sources, max_pages_per_run=cfg["max_pages"]
        )

        remaining_logged = False
        for idx, candidate in enumerate(queue):
            if self._stop_event.is_set():
                log.add("info", "Stop requested during processing")
                self._finalize(job_repo, job, log, "stopped", progress)
                return
            if self._reached(cfg["max_pages"], progress.pages.processed_pages):
                if not remaining_logged:
                    remaining = len(queue) - idx
                    log.add(
                        "info",
                        f"Run limit reached after {progress.pages.processed_pages} "
                        f"processed pages. {remaining} queued page(s) remain for future runs.",
                    )
                    remaining_logged = True
                break

            source = candidate.source
            progress.set_current_url(
                source.url,
                url_type=self._source_url_type(source),
                action="Processing page",
                message=f"Processing page: {source.url}",
            )
            was_never_indexed = (source.status or "pending").lower() in {
                "pending",
                "new",
            }
            if candidate.candidate_class is CandidateClass.NEW:
                log.add("info", f"New page queued: {source.url}")
            elif candidate.candidate_class is CandidateClass.STALE:
                log.add("info", f"Stale page queued for refresh: {source.url}")
            elif candidate.candidate_class is CandidateClass.FAILED:
                log.add("info", f"Failed page queued for retry: {source.url}")

            outcome = indexer.index_source(
                source,
                force=cfg["force_reindex"],
                on_progress=self._index_progress_callback(progress),
            )
            self._apply_page_outcome(
                outcome, progress, was_never_indexed=was_never_indexed
            )
            log.add(
                "info" if outcome.status != "error" else "error",
                f"[page/{outcome.status}] {source.url} ({outcome.detail})",
            )
            if progress.pages.processed_pages % 10 == 0:
                log.add(
                    "info",
                    f"[processing] processed={progress.pages.processed_pages} "
                    f"indexed_new={progress.pages.indexed_new_pages} "
                    f"updated={progress.pages.updated_pages} "
                    f"unchanged={progress.pages.unchanged_pages} "
                    f"failed={progress.pages.failed_pages}",
                )
            self._persist_progress(job_repo, job, log, "running", progress)

    @staticmethod
    def _refresh_run_queue(
        progress: IndexingProgress,
        planner: IndexingPlannerService,
        source_repo: SourceRepository,
        discovered_page_urls: set[str],
        cfg: dict,
    ) -> None:
        if not discovered_page_urls:
            return
        page_sources = source_repo.list_by_urls(sorted(discovered_page_urls))
        preview = planner.build_queue_preview(
            page_sources, max_pages_per_run=cfg["max_pages"]
        )
        progress.apply_queue_preview(preview)

    @staticmethod
    def _resolve_config(settings, overrides: _Overrides) -> dict:
        scan_mode = overrides.scan_mode or settings.scan_mode or "pages_only"
        enable_file_indexing = (
            overrides.enable_file_indexing
            if overrides.enable_file_indexing is not None
            else settings.enable_file_indexing
        )
        scan_all_pages = (
            overrides.scan_all_pages
            if overrides.scan_all_pages is not None
            else settings.scan_all_pages
        )
        scan_all_files = (
            overrides.scan_all_files
            if overrides.scan_all_files is not None
            else settings.scan_all_files
        )
        max_pages = (
            overrides.max_pages_per_run
            if overrides.max_pages_per_run is not None
            else settings.max_pages_per_run
        )
        max_files = (
            overrides.max_files_per_run
            if overrides.max_files_per_run is not None
            else settings.max_files_per_run
        )
        index_pages = scan_mode in ("pages_only", "pages_and_files")
        index_files = enable_file_indexing and scan_mode in (
            "pages_and_files",
            "files_only",
        )
        if not enable_file_indexing:
            index_files = False
        discover_files = scan_mode in ("pages_and_files", "files_only")

        allowed_domains = overrides.allowed_domains
        if allowed_domains is None:
            allowed_domains = json.loads(settings.allowed_domains_json or "[]")
        site_url = overrides.site_url or settings.site_url
        sitemap_url = overrides.sitemap_url or settings.sitemap_url
        if not allowed_domains:
            seed = site_url or sitemap_url
            if seed:
                allowed_domains = [get_domain(seed)]

        deny_patterns = overrides.deny_url_patterns
        if deny_patterns is None:
            deny_patterns = json.loads(settings.deny_url_patterns_json or "[]")

        pending_only = overrides.pending_only
        if pending_only:
            scan_mode = "pages_only"
            index_pages = True
            index_files = False
            discover_files = False
            max_pages = 0
            max_files = 0

        return {
            "site_url": site_url,
            "sitemap_url": sitemap_url,
            "crawl_depth": overrides.crawl_depth
            if overrides.crawl_depth is not None
            else settings.crawl_depth,
            "scan_mode": scan_mode,
            "index_pages": index_pages,
            "index_files": index_files,
            "discover_files": discover_files,
            "max_pages": 0 if scan_all_pages else max_pages,
            "max_files": 0 if scan_all_files else max_files,
            "allowed_domains": allowed_domains,
            "deny_patterns": deny_patterns,
            "allowed_file_types": {
                t.lower()
                for t in json.loads(settings.allowed_file_types_json or "[]")
            },
            "page_refresh_hours": settings.indexed_page_refresh_interval_hours,
            "file_refresh_hours": settings.indexed_file_refresh_interval_hours,
            "force_reindex": overrides.force_reindex,
            "pending_only": pending_only,
        }

    @staticmethod
    def _source_url_type(source) -> str:
        st = (source.source_type or "page").lower()
        if st in ("pdf", "docx", "txt"):
            return "file"
        return "page"

    @staticmethod
    def _index_progress_callback(progress: IndexingProgress):
        def on_progress(stage: str, message: str) -> None:
            progress.set_stage(stage, action=message, message=message)

        return on_progress

    def _seed_frontier(self, frontier, cfg, settings, log: _JobLog) -> None:
        if cfg["sitemap_url"]:
            try:
                urls = SitemapService(
                    FileFetchService(settings.request_timeout_seconds)
                ).collect_urls(cfg["sitemap_url"])
                log.add("info", f"Sitemap yielded {len(urls)} URLs")
                for u in urls:
                    frontier.add(u, depth=0)
            except Exception as exc:  # noqa: BLE001
                log.add("error", f"Sitemap error: {exc}")

        if cfg["site_url"]:
            frontier.add(cfg["site_url"], depth=0)
            for wp_url in self._wordpress_urls(
                cfg["site_url"], settings.request_timeout_seconds
            ):
                frontier.add(wp_url, depth=0)

    @staticmethod
    def _apply_page_outcome(
        outcome, progress: IndexingProgress, *, was_never_indexed: bool
    ) -> None:
        progress.pages.processed_pages += 1
        if outcome.status == "indexed":
            if was_never_indexed:
                progress.pages.indexed_new_pages += 1
            else:
                progress.pages.updated_pages += 1
        elif outcome.status == "skipped":
            if outcome.detail == "unchanged":
                progress.pages.unchanged_pages += 1
            elif outcome.detail == "empty content":
                progress.pages.skipped_empty_pages += 1
            else:
                progress.pages.skipped_empty_pages += 1
        else:
            progress.pages.failed_pages += 1
            progress.errors_count += 1

    def _process_file_candidate(
        self,
        source,
        indexer,
        force: bool,
        progress: IndexingProgress,
        log: _JobLog,
        *,
        was_never_indexed: bool,
    ) -> None:
        progress.set_current_url(
            source.url,
            url_type=self._source_url_type(source),
            action="Processing file",
            message=f"Processing file: {source.url}",
        )
        outcome = indexer.index_source(
            source,
            force=force,
            on_progress=self._index_progress_callback(progress),
        )
        progress.files.processed_files += 1
        if outcome.status == "indexed":
            if was_never_indexed:
                progress.files.indexed_new_files += 1
            else:
                progress.files.updated_files += 1
        elif outcome.status == "skipped":
            if outcome.detail == "unchanged":
                progress.files.unchanged_files += 1
            else:
                progress.files.skipped_files += 1
        else:
            progress.errors_count += 1
            progress.files.failed_files += 1
        log.add(
            "info" if outcome.status != "error" else "error",
            f"[file/{outcome.status}] {source.url} ({outcome.detail})",
        )

    def _wordpress_urls(self, site_url: str, timeout: int) -> list[str]:
        base = site_url.rstrip("/")
        endpoints = [
            f"{base}/wp-json/wp/v2/pages?per_page=100",
            f"{base}/wp-json/wp/v2/posts?per_page=100",
        ]
        found: list[str] = []
        for endpoint in endpoints:
            try:
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    resp = client.get(endpoint)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for item in data:
                        link = item.get("link")
                        if link:
                            found.append(normalize_url(link))
            except Exception:  # noqa: BLE001
                continue
        if found:
            logger.info("WordPress REST discovery found %d URLs", len(found))
        return found

    def _persist_progress(
        self,
        job_repo,
        job: IndexJob,
        log: _JobLog,
        status: str,
        progress: IndexingProgress,
        *,
        force: bool = False,
    ) -> None:
        throttle = self._progress_throttle
        if throttle and not throttle.should_flush(force=force):
            return
        job.status = status
        job.updated_at = utcnow()
        progress.apply_to_job(job)
        if log.entries:
            job.log_json = json.dumps(log.entries[-80:], ensure_ascii=False)
            if self._event_repo and log.entries:
                last = log.entries[-1]
                self._event_repo.append(
                    job.id,
                    last.get("level", "info"),
                    last.get("message", ""),
                )
        job_repo.save(job)
        if throttle:
            throttle.mark_flushed()

    def _finalize(
        self,
        job_repo,
        job: IndexJob,
        log: _JobLog,
        status: str,
        progress: IndexingProgress,
    ) -> None:
        terminal_stage = (
            STAGE_COMPLETED
            if status == "completed"
            else STAGE_STOPPED
            if status == "stopped"
            else STAGE_FAILED
        )
        progress.set_stage(
            terminal_stage,
            phase="complete" if status == "completed" else status,
            action=f"Run {status}",
            message=f"Indexing run {status}",
        )
        progress.current_url = None
        progress.current_url_type = None
        progress.current_action = None
        log.add(
            "info",
            f"[complete] status={status} processed={progress.pages.processed_pages} "
            f"indexed_new={progress.pages.indexed_new_pages} "
            f"updated={progress.pages.updated_pages} "
            f"unchanged={progress.pages.unchanged_pages} "
            f"skipped_fresh={progress.pages.skipped_fresh_pages} "
            f"failed={progress.pages.failed_pages} "
            f"files_indexed={progress.files.indexed_new_files + progress.files.updated_files}",
        )
        job.status = status
        job.updated_at = utcnow()
        progress.apply_to_job(job)
        job.finished_at = utcnow()
        if log.entries:
            job.log_json = json.dumps(log.entries[-80:], ensure_ascii=False)
            if self._event_repo:
                last = log.entries[-1]
                self._event_repo.append(
                    job.id,
                    last.get("level", "info"),
                    last.get("message", ""),
                )
        job_repo.save(job)
        throttle = self._progress_throttle
        if throttle:
            throttle.mark_flushed()

        try:
            from app.services.queue_preview_cache import queue_preview_cache
            queue_preview_cache.invalidate()
        except Exception:  # noqa: BLE001
            pass

        if status in ("completed", "stopped") and (
            progress.pages.indexed_new_pages + progress.pages.updated_pages > 0
            or progress.files.indexed_new_files + progress.files.updated_files > 0
        ):
            try:
                KnowledgeVersionService(job_repo.db).bump()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to bump knowledge version: %s", exc)


indexing_worker = IndexingWorker()
