"""Wrapper around the local Ollama HTTP API with a reused HTTP client."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from time import perf_counter

import httpx

from app.core.config import get_config
from app.core.concurrency import concurrency
from app.core.logging import get_logger

logger = get_logger(__name__)

_client_lock = threading.Lock()
_shared_client: httpx.Client | None = None


@dataclass
class OllamaChatResult:
    content: str
    prompt_eval_count: int = 0
    eval_count: int = 0
    total_duration_ns: int = 0
    eval_duration_ns: int = 0
    prompt_eval_duration_ns: int = 0
    load_duration_ns: int = 0
    model: str = ""
    connection_ms: int | None = None


@dataclass
class OllamaStreamChunk:
    text: str = ""
    done: bool = False
    stats: OllamaChatResult | None = None


def _get_client(timeout: float) -> httpx.Client:
    global _shared_client
    with _client_lock:
        if _shared_client is None:
            _shared_client = httpx.Client(
                timeout=timeout,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return _shared_client


def _build_options(
    *,
    temperature: float,
    max_tokens: int,
    num_ctx: int,
    top_p: float | None = None,
    repeat_penalty: float | None = None,
) -> dict:
    options: dict = {
        "temperature": temperature,
        "num_predict": max_tokens,
        "num_ctx": num_ctx,
    }
    if top_p is not None:
        options["top_p"] = top_p
    if repeat_penalty is not None:
        options["repeat_penalty"] = repeat_penalty
    return options


def _parse_chat_stats(data: dict, *, model: str, content: str = "") -> OllamaChatResult:
    message = data.get("message") or {}
    text = content or (message.get("content") or "").strip()
    return OllamaChatResult(
        content=text,
        prompt_eval_count=int(data.get("prompt_eval_count") or 0),
        eval_count=int(data.get("eval_count") or 0),
        total_duration_ns=int(data.get("total_duration") or 0),
        eval_duration_ns=int(data.get("eval_duration") or 0),
        prompt_eval_duration_ns=int(data.get("prompt_eval_duration") or 0),
        load_duration_ns=int(data.get("load_duration") or 0),
        model=str(data.get("model") or model),
    )


class OllamaError(RuntimeError):
    """Raised when an Ollama call fails."""


class OllamaService:
    def __init__(self, base_url: str | None = None, timeout: float = 120.0) -> None:
        self.base_url = (base_url or get_config().ollama_base_url).rstrip("/")
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        return _get_client(self.timeout)

    def version(self) -> str | None:
        try:
            resp = self._client().get(f"{self.base_url}/api/version", timeout=4.0)
            resp.raise_for_status()
            return str(resp.json().get("version") or "")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ollama version check failed: %s", exc)
            return None

    def health(self) -> tuple[bool, str]:
        try:
            resp = self._client().get(f"{self.base_url}/api/tags", timeout=4.0)
            resp.raise_for_status()
            return True, "Ollama reachable"
        except Exception as exc:  # noqa: BLE001
            return False, f"Ollama unreachable: {exc}"

    def list_models(self) -> list[dict]:
        try:
            resp = self._client().get(f"{self.base_url}/api/tags", timeout=15.0)
            resp.raise_for_status()
            return resp.json().get("models", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to list Ollama models: %s", exc)
            return []

    def embed(self, model: str, text: str, *, background: bool = False) -> list[float]:
        payload = {"model": model, "input": text}
        slot = (
            concurrency.background_embed_slot()
            if background
            else concurrency.embed_slot()
        )
        try:
            with slot:
                resp = self._client().post(
                    f"{self.base_url}/api/embed", json=payload, timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise OllamaError(f"Embedding request failed: {exc}") from exc
        embeddings = data.get("embeddings")
        if embeddings:
            return embeddings[0]
        if "embedding" in data:
            return data["embedding"]
        raise OllamaError("Ollama returned no embedding")

    def embed_batch(
        self, model: str, texts: list[str], *, background: bool = False
    ) -> list[list[float]]:
        if not texts:
            return []
        payload = {"model": model, "input": texts}
        slot = (
            concurrency.background_embed_slot()
            if background
            else concurrency.embed_slot()
        )
        try:
            with slot:
                resp = self._client().post(
                    f"{self.base_url}/api/embed", json=payload, timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise OllamaError(f"Batch embedding request failed: {exc}") from exc
        embeddings = data.get("embeddings")
        if embeddings is None:
            raise OllamaError("Ollama returned no embeddings")
        return embeddings

    def chat(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        num_ctx: int = 4096,
        top_p: float | None = None,
        repeat_penalty: float | None = None,
        timeout: float | None = None,
        keep_alive: str | None = None,
        background: bool = False,
    ) -> OllamaChatResult:
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": _build_options(
                temperature=temperature,
                max_tokens=max_tokens,
                num_ctx=num_ctx,
                top_p=top_p,
                repeat_penalty=repeat_penalty,
            ),
        }
        if keep_alive:
            payload["keep_alive"] = keep_alive
        req_timeout = timeout if timeout is not None else self.timeout
        llm_slot = (
            concurrency.background_llm_slot()
            if background
            else concurrency.llm_slot()
        )
        t_conn = perf_counter()
        try:
            with llm_slot:
                resp = self._client().post(
                    f"{self.base_url}/api/chat", json=payload, timeout=req_timeout
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as exc:
            raise OllamaError(f"Chat request timed out after {req_timeout}s") from exc
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "timed out" in msg or "timeout" in msg:
                raise OllamaError(f"Chat request timed out: {exc}") from exc
            raise OllamaError(f"Chat request failed: {exc}") from exc
        connection_ms = int((perf_counter() - t_conn) * 1000)
        message = data.get("message") or {}
        content = message.get("content")
        if content is None:
            raise OllamaError("Ollama returned no chat content")
        result = _parse_chat_stats(data, model=model, content=content.strip())
        result.connection_ms = connection_ms
        return result

    def chat_stream(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        num_ctx: int = 4096,
        top_p: float | None = None,
        repeat_penalty: float | None = None,
        timeout: float | None = None,
        keep_alive: str | None = None,
    ):
        """Yield token chunks immediately; final chunk includes Ollama timing stats."""
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
            "options": _build_options(
                temperature=temperature,
                max_tokens=max_tokens,
                num_ctx=num_ctx,
                top_p=top_p,
                repeat_penalty=repeat_penalty,
            ),
        }
        if keep_alive:
            payload["keep_alive"] = keep_alive
        req_timeout = timeout if timeout is not None else self.timeout
        t_conn = perf_counter()
        connection_ms: int | None = None
        try:
            with concurrency.llm_slot():
                with self._client().stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=req_timeout,
                ) as resp:
                    resp.raise_for_status()
                    connection_ms = int((perf_counter() - t_conn) * 1000)
                    accumulated: list[str] = []
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        msg = data.get("message") or {}
                        chunk = msg.get("content")
                        if chunk:
                            accumulated.append(chunk)
                            yield OllamaStreamChunk(text=chunk)
                        if data.get("done"):
                            stats = _parse_chat_stats(
                                data,
                                model=model,
                                content="".join(accumulated),
                            )
                            stats.connection_ms = connection_ms
                            yield OllamaStreamChunk(done=True, stats=stats)
                            break
        except httpx.TimeoutException as exc:
            raise OllamaError(f"Chat stream timed out after {req_timeout}s") from exc
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "timed out" in msg or "timeout" in msg:
                raise OllamaError(f"Chat stream timed out: {exc}") from exc
            raise OllamaError(f"Chat stream failed: {exc}") from exc

    def pull_model(self, model: str) -> dict:
        """Download a model from the Ollama registry (may take several minutes)."""
        payload = {"model": model, "stream": True}
        t0 = perf_counter()
        last: dict = {}
        try:
            with self._client().stream(
                "POST",
                f"{self.base_url}/api/pull",
                json=payload,
                timeout=httpx.Timeout(600.0, connect=30.0),
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    last = data
                    status = str(data.get("status") or "")
                    if status == "success":
                        break
                    if status == "error":
                        raise OllamaError(str(data.get("error") or "Model pull failed"))
        except OllamaError:
            raise
        except httpx.TimeoutException as exc:
            raise OllamaError("Model pull timed out after 600s") from exc
        except Exception as exc:  # noqa: BLE001
            raise OllamaError(f"Model pull failed: {exc}") from exc
        if str(last.get("status") or "") != "success":
            raise OllamaError(str(last.get("error") or "Model pull did not complete"))
        duration_ms = int((perf_counter() - t0) * 1000)
        return {
            "model": model,
            "status": "success",
            "duration_ms": duration_ms,
            "detail": last,
        }

    def delete_model(self, model: str) -> None:
        try:
            resp = self._client().request(
                "DELETE",
                f"{self.base_url}/api/delete",
                json={"model": model},
                timeout=60.0,
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise OllamaError(f"Model delete failed: {exc}") from exc
