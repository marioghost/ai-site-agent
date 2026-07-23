"""User management API (admin only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.user import USER_ROLES, User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import MessageResponse
from app.schemas.user import ChangePasswordRequest, UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


def _to_read(user: User) -> UserRead:
    return UserRead.model_validate(user)


@router.get("", response_model=list[UserRead])
def list_users(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserRead]:
    return [_to_read(u) for u in UserRepository(db).list_all()]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserRead:
    if body.role not in USER_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    repo = UserRepository(db)
    if repo.get_by_username(body.username.strip()):
        raise HTTPException(status_code=400, detail="Username already exists")
    try:
        user = repo.create(
            username=body.username,
            password=body.password,
            display_name=body.display_name,
            role=body.role,
            email=body.email,
            is_active=body.is_active,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Username already exists") from exc
    return _to_read(user)


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserRead:
    user = UserRepository(db).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_read(user)


@router.put("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    body: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserRead:
    repo = UserRepository(db)
    user = repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if body.role is not None and body.role not in USER_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if body.is_active is False and user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    if body.username and body.username.strip() != user.username:
        existing = repo.get_by_username(body.username.strip())
        if existing and existing.id != user.id:
            raise HTTPException(status_code=400, detail="Username already exists")
    try:
        updated = repo.update(
            user,
            username=body.username,
            email=body.email,
            display_name=body.display_name,
            role=body.role,
            is_active=body.is_active,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Username already exists") from exc
    return _to_read(updated)


@router.post("/{user_id}/change-password", response_model=MessageResponse)
def change_password(
    user_id: int,
    body: ChangePasswordRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    repo = UserRepository(db)
    user = repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    repo.set_password(user, body.password)
    return MessageResponse(message="Password updated")


@router.post("/{user_id}/deactivate", response_model=UserRead)
def deactivate_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserRead:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    repo = UserRepository(db)
    user = repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_read(repo.update(user, is_active=False))


@router.post("/{user_id}/activate", response_model=UserRead)
def activate_user(
    user_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserRead:
    repo = UserRepository(db)
    user = repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_read(repo.update(user, is_active=True))


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    repo = UserRepository(db)
    user = repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    repo.delete(user)
    return MessageResponse(message="User deleted")
