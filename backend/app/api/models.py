"""Models / local AI status API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_authenticated
from app.core.database import get_db
from app.repositories.settings_repository import SettingsRepository
from app.schemas.models import (
    ModelsResponse,
    OllamaDeleteResponse,
    OllamaModel,
    OllamaModelActionRequest,
    OllamaPullResponse,
    OllamaStatusResponse,
)
from app.services.ollama_model_admin_service import OllamaModelAdminError, OllamaModelAdminService
from app.services.ollama_service import OllamaService

router = APIRouter(tags=["models"])


def _serialize_models(raw: list[dict], admin: OllamaModelAdminService) -> list[OllamaModel]:
    models: list[OllamaModel] = []
    for m in raw:
        name = str(m.get("name") or m.get("model") or "")
        if not name:
            continue
        details = m.get("details") or {}
        models.append(
            OllamaModel(
                name=name,
                size=m.get("size"),
                modified_at=m.get("modified_at"),
                family=details.get("family"),
                parameter_size=details.get("parameter_size"),
                in_use_as=admin.model_in_use(name),  # type: ignore[arg-type]
            )
        )
    return models


@router.get("/api/models", response_model=ModelsResponse)
def list_models(
    _user=Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> ModelsResponse:
    settings = SettingsRepository(db).get_or_create()
    ollama = OllamaService()
    ok, _ = ollama.health()
    admin = OllamaModelAdminService(ollama, settings)
    raw = ollama.list_models() if ok else []
    return ModelsResponse(models=_serialize_models(raw, admin), ollama_reachable=ok)


@router.get("/api/ollama/status", response_model=OllamaStatusResponse)
def ollama_status(_user=Depends(require_authenticated)) -> OllamaStatusResponse:
    service = OllamaService()
    ok, detail = service.health()
    model_names = [m.get("name", "") for m in service.list_models()] if ok else []
    return OllamaStatusResponse(
        status="ok" if ok else "error",
        base_url=service.base_url,
        detail=detail,
        models=model_names,
    )


@router.post("/api/ollama/models/pull", response_model=OllamaPullResponse)
def pull_ollama_model(
    body: OllamaModelActionRequest,
    _user=Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> OllamaPullResponse:
    settings = SettingsRepository(db).get_or_create()
    admin = OllamaModelAdminService(OllamaService(timeout=600.0), settings)
    try:
        result = admin.pull(body.model.strip())
    except OllamaModelAdminError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OllamaPullResponse(
        model=result["model"],
        status=result["status"],
        duration_ms=int(result.get("duration_ms") or 0),
        message="Model installed successfully",
    )


@router.post("/api/ollama/models/delete", response_model=OllamaDeleteResponse)
def delete_ollama_model(
    body: OllamaModelActionRequest,
    _user=Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> OllamaDeleteResponse:
    settings = SettingsRepository(db).get_or_create()
    admin = OllamaModelAdminService(OllamaService(), settings)
    try:
        result = admin.delete(body.model.strip())
    except OllamaModelAdminError as exc:
        msg = str(exc)
        status = 409 if "active" in msg.lower() or "cannot delete" in msg.lower() else 400
        raise HTTPException(status_code=status, detail=msg) from exc
    return OllamaDeleteResponse(
        model=result["model"],
        status=result["status"],
        message="Model deleted",
    )
