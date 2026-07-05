"""Şema + tablo oluşturma ve ilk veri (idempotent). API açılışında çalışır."""
import os
import sys

from sqlalchemy import text

from .auth import hash_password
from .db import SCHEMA_APP, SCHEMA_DERIVED, SCHEMA_RAW, Base, engine, SessionLocal
from .data.cari_hedef import CARI_HEDEF
from .examples import SEED_DASHBOARDS, SEED_JOBS
from .models import CariHedef, Dashboard, Job, Permission, User


def ensure_schemas() -> None:
    with engine.begin() as conn:
        for schema in (SCHEMA_APP, SCHEMA_RAW, SCHEMA_DERIVED):
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))


def migrate() -> None:
    """Hafif idempotent şema güncellemeleri (mevcut tablolara sütun ekleme)."""
    with engine.begin() as conn:
        conn.execute(text(
            f'ALTER TABLE {SCHEMA_APP}.ingest_runs ADD COLUMN IF NOT EXISTS progress TEXT'
        ))
        conn.execute(text(
            f'ALTER TABLE {SCHEMA_APP}.job_runs ADD COLUMN IF NOT EXISTS progress TEXT'
        ))


def reconcile_orphans() -> None:
    """Açılışta yarıda kalmış (running/pending) çalıştırmaları 'error' işaretle."""
    with engine.begin() as conn:
        for tbl in ("ingest_runs", "job_runs"):
            conn.execute(text(
                f"UPDATE {SCHEMA_APP}.{tbl} SET status='error', "
                f"error=COALESCE(error,'') || 'Servis yeniden başlatıldı; çalıştırma kesildi.', "
                f"finished_at=now() WHERE status IN ('running','pending')"
            ))


def seed_users(db) -> None:
    """İlk açılış bootstrap'i: YALNIZ hiç kullanıcı yoksa tek bir admin oluştur.

    Kullanıcı yönetimi artık UI'dan (admin) yapılıyor. Silinen kullanıcıların
    yeniden başlatmada geri gelmemesi için burada sabit demo hesap BASILMAZ.
    İlk admin bilgisi env'den okunur (APP_ADMIN_USER / APP_ADMIN_PASSWORD).
    """
    if db.query(User).first():
        return
    username = os.environ.get("APP_ADMIN_USER", "admin")
    password = os.environ.get("APP_ADMIN_PASSWORD", "admin123")
    db.add(User(
        username=username, full_name="Yönetici", role="admin",
        password_hash=hash_password(password), is_active=True,
    ))
    db.commit()
    print(f"[seed] ilk yönetici oluşturuldu: {username}", file=sys.stderr)


def seed_permissions(db) -> None:
    # Varsayılan kaynak-bazlı izinler ('*' tüm kaynaklar için).
    defaults = [
        ("job", "admin", True, True, True),
        ("job", "analyst", True, True, True),
        ("job", "viewer", False, False, False),
        ("dashboard", "admin", True, True, True),
        ("dashboard", "analyst", True, True, True),
        ("dashboard", "viewer", True, False, False),
        ("ingest", "admin", True, True, True),
        ("ingest", "analyst", True, False, True),
        ("ingest", "viewer", False, False, False),
    ]
    for rtype, role, v, e, r in defaults:
        exists = db.query(Permission).filter_by(
            resource_type=rtype, resource_key="*", role=role
        ).first()
        if not exists:
            db.add(Permission(
                resource_type=rtype, resource_key="*", role=role,
                can_view=v, can_edit=e, can_run=r,
            ))
    db.commit()


def seed_cari_hedef(db) -> None:
    """Excel `values` sayfasından çıkarılan cari×düzey hedef/nüfus (idempotent, eksikleri ekler)."""
    existing = {(r.cari, r.duzey) for r in db.query(CariHedef.cari, CariHedef.duzey).all()}
    added = 0
    for cari, duzey, nufus, perakende, kurumsal in CARI_HEDEF:
        if (cari, duzey) in existing:
            continue
        db.add(CariHedef(cari=cari, duzey=duzey, nufus=nufus,
                         perakende_hedef=perakende, kurumsal_hedef=kurumsal,
                         updated_by="seed"))
        added += 1
    if added:
        db.commit()


def seed_examples(db) -> None:
    for spec in SEED_JOBS:
        if not db.query(Job).filter_by(key=spec["key"]).first():
            db.add(Job(created_by="seed", **spec))
    for spec in SEED_DASHBOARDS:
        if not db.query(Dashboard).filter_by(key=spec["key"]).first():
            db.add(Dashboard(created_by="seed", **spec))
    db.commit()


def main() -> None:
    print("[seed] şemalar oluşturuluyor...", file=sys.stderr)
    ensure_schemas()
    print("[seed] tablolar oluşturuluyor...", file=sys.stderr)
    Base.metadata.create_all(bind=engine)
    migrate()
    reconcile_orphans()
    db = SessionLocal()
    try:
        seed_users(db)
        seed_permissions(db)
        seed_cari_hedef(db)
        seed_examples(db)
    finally:
        db.close()
    print("[seed] tamam.", file=sys.stderr)


if __name__ == "__main__":
    main()
