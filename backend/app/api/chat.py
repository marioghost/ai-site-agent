"""Chat API (RAG) with tracing, concurrency control and optional debug payload."""

from __future__ import annotations

import json
import logging

from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.chat_dispatch_log import log_chat_dispatch, resolve_chat_path
from app.core.concurrency import ConcurrencyLimits, OverloadedError, concurrency
from app.core.database import get_db
from app.core.logging import get_logger
from app.repositories.settings_repository import SettingsRepository
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_response_builder import ChatResponseBuilder, DiagnosticsCollector
from app.services.chat_session_service import ChatSessionService
from app.services.executive import ExecutiveService
from app.services.feature_flags import knowledge_os_executive_enabled
from app.services.trace_service import new_request_id

router = APIRouter(tags=["chat"])
logger = get_logger(__name__)

# RFC-100 Step 064 — frozen operator kill-switch detail (HTTP 503 / SSE message).
EXECUTIVE_DISABLED_DETAIL = (
    "Chat Executive path is disabled by operator "
    "(KNOWLEDGE_OS_EXECUTIVE_ENABLED=false)."
)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _client_ip(request: Request) -> str | None:

    forwarded = request.headers.get("x-forwarded-for")

    if forwarded:

        return forwarded.split(",")[0].strip()

    if request.client:

        return request.client.host

    return None


def _dispatch_non_stream_answer(
    db: Session,
    settings,
    message: str,
    session_id: str | None,
    *,
    request_id: str,
    user_ip: str | None = None,
    user_agent: str | None = None,
    referrer: str | None = None,
    debug: bool = False,
    bypass_cache: bool = False,
):
    """Route non-streaming chat (RFC-100 Step 064).

    Sole API orchestration entry: ExecutiveService.
    Explicit Executive disable → HTTP 503 (no Rag / Reasoning / retrieval).
    """
    if not knowledge_os_executive_enabled():
        raise HTTPException(status_code=503, detail=EXECUTIVE_DISABLED_DETAIL)
    return ExecutiveService(db, settings).answer(
        message,
        session_id,
        request_id=request_id,
        user_ip=user_ip,
        user_agent=user_agent,
        referrer=referrer,
        debug=debug,
        bypass_cache=bypass_cache,
    )


def _dispatch_stream_events(
    db: Session,
    settings,
    message: str,
    session_id: str | None,
    *,
    request_id: str,
    collector: DiagnosticsCollector | None = None,
    user_ip: str | None = None,
    user_agent: str | None = None,
    referrer: str | None = None,
    debug: bool = False,
    bypass_cache: bool = False,
):
    """Route streaming chat (RFC-100 Step 064).

    Sole API orchestration entry: ExecutiveService.
    Explicit Executive disable → one SSE error (executive_disabled), then stop.
    """
    if not knowledge_os_executive_enabled():
        yield (
            "error",
            {
                "error_type": "executive_disabled",
                "message": EXECUTIVE_DISABLED_DETAIL,
                "partial_diagnostics": {},
            },
        )
        return
    yield from ExecutiveService(db, settings).answer_stream(
        message,
        session_id,
        request_id=request_id,
        collector=collector,
        user_ip=user_ip,
        user_agent=user_agent,
        referrer=referrer,
        debug=debug,
        bypass_cache=bypass_cache,
    )





@router.post("/api/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ChatResponse:

    settings = SettingsRepository(db).get_or_create()

    concurrency.configure(

        ConcurrencyLimits(

            max_concurrent_chat_requests=settings.max_concurrent_chat_requests,

            max_concurrent_llm_requests=settings.max_concurrent_llm_requests,

            max_concurrent_embedding_requests=settings.max_concurrent_embedding_requests,

            max_concurrent_background_embedding_requests=getattr(
                settings, "max_concurrent_background_embedding_requests", 1
            ),

        )

    )

    request_id = new_request_id()

    user_ip = _client_ip(request) if settings.enable_request_metadata_logging else None

    user_agent = (

        request.headers.get("user-agent") if settings.enable_request_metadata_logging else None

    )

    referrer = (

        request.headers.get("referer") if settings.enable_request_metadata_logging else None

    )

    debug = payload.debug and settings.enable_chat_debug_payload



    session_svc = ChatSessionService(db)

    try:

        session, _created = session_svc.resolve_session(

            payload.session_id,

            user_ip=user_ip,

            user_agent=user_agent,

            referrer=referrer,

        )

    except ValueError as exc:

        if str(exc) == "session_closed":

            raise HTTPException(status_code=409, detail="Session is closed") from exc

        raise



    if not payload.skip_user_message:
        session_svc.add_user_message(session, payload.message)

    chat_path = resolve_chat_path()
    log_chat_dispatch(
        logger,
        request_id=request_id,
        path=chat_path,
        mode="non_stream",
    )
    started = perf_counter()
    try:
        with concurrency.chat_slot():
            result = _dispatch_non_stream_answer(
                db,
                settings,
                payload.message,
                session.session_id,
                request_id=request_id,
                user_ip=user_ip,
                user_agent=user_agent,
                referrer=referrer,
                debug=debug,
                bypass_cache=payload.bypass_cache,
            )
    except OverloadedError as exc:
        log_chat_dispatch(
            logger,
            request_id=request_id,
            path=chat_path,
            mode="non_stream",
            error_type="overloaded",
            duration_ms=int((perf_counter() - started) * 1000),
            level=logging.WARNING,
        )
        raise HTTPException(status_code=429, detail=exc.message) from exc



    concurrency.metrics.record_latency(result.total_ms)
    concurrency.metrics.record_cache(result.cache_hit)

    builder = ChatResponseBuilder(settings)
    response = builder.from_rag_result(
        result,
        request_id=request_id,
        session_id=session.session_id,
        user_ip=user_ip,
        user_agent=user_agent,
        referrer=referrer,
        debug=debug,
    )
    collector = DiagnosticsCollector(request_id=request_id, session_id=session.session_id)
    collector.set_prompt_diagnostics(result.prompt_diagnostics)
    diagnostics_json = collector.to_persistence_json(response)

    session_svc.add_assistant_message(
        session,
        content=response.answer,
        request_id=request_id,
        sources_json=ChatResponseBuilder.sources_to_json(result.sources),
        used_context=response.used_context,
        cache_hit=response.cache_hit,
        cache_type=response.cache_type,
        timing_json=ChatSessionService.timing_to_json(response.timing.model_dump()),
        trace_id=request_id if response.trace else None,
        diagnostics_json=diagnostics_json,
    )

    log_chat_dispatch(
        logger,
        request_id=request_id,
        path=chat_path,
        mode="non_stream",
        duration_ms=int((perf_counter() - started) * 1000),
    )

    return response





@router.post("/api/chat/stream")
def chat_stream(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Stream answer tokens via SSE; full metadata on final event (parity with /api/chat)."""
    settings = SettingsRepository(db).get_or_create()
    if not getattr(settings, "enable_chat_streaming", True):
        return {"message": "Streaming disabled in settings.", "stream_available": False}

    concurrency.configure(
        ConcurrencyLimits(
            max_concurrent_chat_requests=settings.max_concurrent_chat_requests,
            max_concurrent_llm_requests=settings.max_concurrent_llm_requests,
            max_concurrent_embedding_requests=settings.max_concurrent_embedding_requests,
            max_concurrent_background_embedding_requests=getattr(
                settings, "max_concurrent_background_embedding_requests", 1
            ),
        )
    )

    session_svc = ChatSessionService(db)
    user_ip = _client_ip(request) if settings.enable_request_metadata_logging else None
    user_agent = (
        request.headers.get("user-agent") if settings.enable_request_metadata_logging else None
    )
    referrer = request.headers.get("referer") if settings.enable_request_metadata_logging else None
    debug = payload.debug and settings.enable_chat_debug_payload
    stream_request_id = new_request_id()

    try:
        session, _created = session_svc.resolve_session(
            payload.session_id,
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
        )
    except ValueError as exc:
        if str(exc) == "session_closed":
            raise HTTPException(status_code=409, detail="Session is closed") from exc
        raise

    session_svc.add_user_message(session, payload.message)
    builder = ChatResponseBuilder(settings)
    collector = DiagnosticsCollector(
        request_id=stream_request_id,
        session_id=session.session_id,
    )

    def event_generator():
        final_response: ChatResponse | None = None
        chat_path = resolve_chat_path()
        event_count = 0
        started = perf_counter()
        log_chat_dispatch(
            logger,
            request_id=stream_request_id,
            path=chat_path,
            mode="stream",
            stream_lifecycle="start",
        )
        try:
            try:
                with concurrency.chat_slot():
                    for event_name, event_data in _dispatch_stream_events(
                        db,
                        settings,
                        payload.message,
                        session.session_id,
                        request_id=stream_request_id,
                        collector=collector,
                        user_ip=user_ip,
                        user_agent=user_agent,
                        referrer=referrer,
                        debug=debug,
                        bypass_cache=payload.bypass_cache,
                    ):
                        if (
                            event_name == "error"
                            and event_data.get("error_type") == "executive_disabled"
                        ):
                            event_count += 1
                            yield _sse(event_name, event_data)
                            log_chat_dispatch(
                                logger,
                                request_id=stream_request_id,
                                path=chat_path,
                                mode="stream",
                                stream_lifecycle="error",
                                error_type="executive_disabled",
                                events_count=event_count,
                                duration_ms=int((perf_counter() - started) * 1000),
                                level=logging.WARNING,
                            )
                            yield "data: [DONE]\n\n"
                            return
                        if event_name == "final":
                            raw = event_data.get("response", event_data)
                            final_response = builder.from_stream_payload(
                                raw,
                                request_id=stream_request_id,
                                session_id=session.session_id,
                                user_ip=user_ip,
                                user_agent=user_agent,
                                referrer=referrer,
                                debug=debug,
                            )
                        event_count += 1
                        yield _sse(event_name, event_data)

                if final_response is not None:
                    collector.set_prompt_diagnostics(final_response.prompt_diagnostics)
                    diagnostics_json = collector.to_persistence_json(final_response)
                    session_svc.add_assistant_message(
                        session,
                        content=final_response.answer,
                        request_id=stream_request_id,
                        sources_json=json.dumps(
                            [s.model_dump() for s in final_response.sources],
                            ensure_ascii=False,
                        ),
                        used_context=final_response.used_context,
                        cache_hit=final_response.cache_hit,
                        cache_type=final_response.cache_type,
                        timing_json=ChatSessionService.timing_to_json(
                            final_response.timing.model_dump()
                        ),
                        trace_id=stream_request_id if final_response.trace else None,
                        diagnostics_json=diagnostics_json,
                    )
                    concurrency.metrics.record_latency(final_response.timing.total_ms)
                    concurrency.metrics.record_cache(final_response.cache_hit)

                yield "data: [DONE]\n\n"
                log_chat_dispatch(
                    logger,
                    request_id=stream_request_id,
                    path=chat_path,
                    mode="stream",
                    stream_lifecycle="end",
                    events_count=event_count,
                    duration_ms=int((perf_counter() - started) * 1000),
                )
            except OverloadedError as exc:
                log_chat_dispatch(
                    logger,
                    request_id=stream_request_id,
                    path=chat_path,
                    mode="stream",
                    stream_lifecycle="error",
                    error_type="overloaded",
                    events_count=event_count,
                    duration_ms=int((perf_counter() - started) * 1000),
                    level=logging.WARNING,
                )
                yield _sse(
                    "error",
                    {
                        "error_type": "overloaded",
                        "message": exc.message,
                        "partial_diagnostics": {},
                    },
                )
            except Exception as exc:  # noqa: BLE001
                log_chat_dispatch(
                    logger,
                    request_id=stream_request_id,
                    path=chat_path,
                    mode="stream",
                    stream_lifecycle="error",
                    error_type="server_error",
                    events_count=event_count,
                    duration_ms=int((perf_counter() - started) * 1000),
                    level=logging.WARNING,
                )
                yield _sse(
                    "error",
                    {
                        "error_type": "server_error",
                        "message": str(exc),
                        "partial_diagnostics": {},
                    },
                )
        except GeneratorExit:
            log_chat_dispatch(
                logger,
                request_id=stream_request_id,
                path=chat_path,
                mode="stream",
                stream_lifecycle="cancelled",
                events_count=event_count,
                duration_ms=int((perf_counter() - started) * 1000),
            )
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")

