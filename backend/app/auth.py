"""JWT + bcrypt + RBAC bağımlılıkları."""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Rol hiyerarşisi: admin her şey, analyst yazar/çalıştırır, viewer görür.
ROLE_RANK = {"viewer": 0, "analyst": 1, "admin": 2}


def hash_password(p: str) -> str:
    return pwd_context.hash(p)


def verify_password(p: str, h: str) -> bool:
    return pwd_context.verify(p, h)


def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.APP_JWT_TTL_MIN),
    }
    return jwt.encode(payload, settings.APP_JWT_SECRET, algorithm=settings.APP_JWT_ALG)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz veya süresi dolmuş oturum",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.APP_JWT_SECRET, algorithms=[settings.APP_JWT_ALG])
        user_id = int(payload.get("sub"))
    except (jwt.PyJWTError, TypeError, ValueError):
        raise cred_exc
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise cred_exc
    return user


def require_role(*allowed: str):
    """En az verilen rollerden birini şart koşan dependency üretir."""
    min_rank = min(ROLE_RANK[r] for r in allowed)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if ROLE_RANK.get(user.role, -1) < min_rank:
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
        return user

    return _dep


# Kısayollar
require_viewer = require_role("viewer")
require_analyst = require_role("analyst")  # analyst veya admin
require_admin = require_role("admin")
