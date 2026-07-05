"""Kullanıcı yönetimi — yalnız admin. Liste/oluştur/güncelle/parola/sil.

Kilitlenmeyi önleyen korumalar: kendi hesabını silme/pasifleştirme yok, son aktif
yöneticiyi silme/pasifleştirme/rol düşürme yok.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import hash_password, require_admin
from ..db import get_db
from ..models import ROLES, User
from ..schemas import PasswordIn, UserAdminOut, UserCreate, UserUpdate

router = APIRouter()

MIN_PASSWORD_LEN = 6


def _get(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return user


def _active_admins(db: Session, exclude_id: int | None = None) -> int:
    q = db.query(User).filter(User.role == "admin", User.is_active.is_(True))
    if exclude_id is not None:
        q = q.filter(User.id != exclude_id)
    return q.count()


@router.get("", response_model=list[UserAdminOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(User).order_by(User.id).all()


@router.post("", response_model=UserAdminOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=422, detail="Kullanıcı adı boş olamaz")
    if body.role not in ROLES:
        raise HTTPException(status_code=422, detail="Geçersiz rol")
    if len(body.password) < MIN_PASSWORD_LEN:
        raise HTTPException(status_code=422, detail=f"Parola en az {MIN_PASSWORD_LEN} karakter olmalı")
    if db.query(User).filter_by(username=username).first():
        raise HTTPException(status_code=409, detail="Bu kullanıcı adı zaten kullanımda")
    user = User(
        username=username,
        full_name=(body.full_name or None),
        role=body.role,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    me: User = Depends(require_admin),
):
    user = _get(db, user_id)

    if body.role is not None and body.role != user.role:
        if body.role not in ROLES:
            raise HTTPException(status_code=422, detail="Geçersiz rol")
        if user.role == "admin" and _active_admins(db, exclude_id=user.id) == 0:
            raise HTTPException(status_code=400, detail="Son aktif yöneticinin rolü değiştirilemez")
        user.role = body.role

    if body.is_active is not None and body.is_active != user.is_active:
        if not body.is_active:
            if user.id == me.id:
                raise HTTPException(status_code=400, detail="Kendi hesabınızı pasifleştiremezsiniz")
            if user.role == "admin" and _active_admins(db, exclude_id=user.id) == 0:
                raise HTTPException(status_code=400, detail="Son aktif yönetici pasifleştirilemez")
        user.is_active = body.is_active

    if body.full_name is not None:
        user.full_name = body.full_name or None

    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/password", status_code=204)
def set_password(
    user_id: int,
    body: PasswordIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if len(body.password) < MIN_PASSWORD_LEN:
        raise HTTPException(status_code=422, detail=f"Parola en az {MIN_PASSWORD_LEN} karakter olmalı")
    user = _get(db, user_id)
    user.password_hash = hash_password(body.password)
    db.commit()


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), me: User = Depends(require_admin)):
    user = _get(db, user_id)
    if user.id == me.id:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı silemezsiniz")
    if user.role == "admin" and _active_admins(db, exclude_id=user.id) == 0:
        raise HTTPException(status_code=400, detail="Son aktif yönetici silinemez")
    db.delete(user)
    db.commit()
