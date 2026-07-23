"""User repository."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import USER_ROLES, User
from app.utils.time_utils import utcnow


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def count(self) -> int:
        return int(self.db.scalar(select(func.count()).select_from(User)) or 0)

    def list_all(self) -> list[User]:
        return list(
            self.db.scalars(select(User).order_by(User.username.asc())).all()
        )

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self.db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

    def create(
        self,
        *,
        username: str,
        password: str,
        display_name: str,
        role: str,
        email: str | None = None,
        is_active: bool = True,
    ) -> User:
        if role not in USER_ROLES:
            raise ValueError(f"Invalid role: {role}")
        user = User(
            username=username.strip(),
            email=email.strip() if email else None,
            display_name=display_name.strip() or username,
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(
        self,
        user: User,
        *,
        email: str | None = None,
        display_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        username: str | None = None,
    ) -> User:
        if username is not None:
            user.username = username.strip()
        if email is not None:
            user.email = email.strip() or None
        if display_name is not None:
            user.display_name = display_name.strip()
        if role is not None:
            if role not in USER_ROLES:
                raise ValueError(f"Invalid role: {role}")
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_password(self, user: User, password: str) -> User:
        user.password_hash = hash_password(password)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def record_login(self, user: User) -> None:
        user.last_login_at = utcnow()
        self.db.add(user)
        self.db.commit()

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()

    def seed_default_admin(self, password: str = "фвьшт") -> User | None:
        """Create default admin if no users exist."""
        if self.count() > 0:
            return None
        return self.create(
            username="admin",
            password=password,
            display_name="Administrator",
            role="admin",
            email=None,
            is_active=True,
        )
