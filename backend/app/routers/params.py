"""Planlama parametreleri: cari × düzey hedef/nüfus (Excel `values` karşılığı).

Dashboard'lar 'Gönderilecek Adet' için nüfus/hedef'i bu tablodan okur. Düzenlenebilir
(analyst/admin). GET listeler, PUT upsert (cari+duzey doğal anahtarı).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_analyst
from ..db import get_db
from ..models import CariHedef, User
from ..schemas import CariHedefIn, CariHedefOut

router = APIRouter()


@router.get("/cari-hedef", response_model=list[CariHedefOut])
def list_cari_hedef(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(CariHedef).order_by(CariHedef.cari, CariHedef.duzey).all()


@router.put("/cari-hedef", response_model=CariHedefOut)
def upsert_cari_hedef(body: CariHedefIn, db: Session = Depends(get_db),
                      user: User = Depends(require_analyst)):
    row = (db.query(CariHedef)
             .filter_by(cari=body.cari, duzey=body.duzey).first())
    if row is None:
        row = CariHedef(cari=body.cari, duzey=body.duzey)
        db.add(row)
    row.nufus = body.nufus
    row.perakende_hedef = body.perakende_hedef
    row.kurumsal_hedef = body.kurumsal_hedef
    row.updated_by = user.username
    db.commit()
    db.refresh(row)
    return row
