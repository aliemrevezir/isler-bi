"""Dashboards CRUD + kod/versiyon + meta(filter_schema) + run + export."""
import io

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_analyst
from ..ctx import DashboardContext
from ..db import get_db
from ..models import Dashboard, DashboardVersion, User
from ..runner import dashboard_meta, run_dashboard
from ..schemas import (
    CodeIn,
    DashboardCreate,
    DashboardOut,
    DashboardRunIn,
    VersionOut,
)

router = APIRouter()

STARTER = '''"""Dashboard: derived → {kpis, charts, table}. (read-only)

filter_schema() -> [{key,label,type,...}]   (UI filtreleri; opsiyonel)
run(ctx) -> {kpis:[...], charts:[...], table:{columns,rows}}
ctx.read_sql(sql, params), ctx.filters
"""


def filter_schema():
    return []


def run(ctx):
    df = ctx.read_sql("SELECT 1 AS deger")
    return {
        "kpis": [{"key": "toplam", "label": "Toplam", "value": int(df["deger"].sum()), "format": "int"}],
        "charts": [],
        "table": {
            "columns": [{"key": "deger", "label": "Değer", "format": "int"}],
            "rows": df.to_dict(orient="records"),
        },
    }
'''


def _validate(code: str):
    try:
        compile(code, "<dashboard>", "exec")
    except SyntaxError as e:
        raise HTTPException(status_code=400, detail=f"Sözdizimi hatası: {e}")


@router.get("", response_model=list[DashboardOut])
def list_dashboards(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Dashboard).order_by(Dashboard.title).all()


@router.post("", response_model=DashboardOut)
def create_dashboard(body: DashboardCreate, db: Session = Depends(get_db),
                     user: User = Depends(require_analyst)):
    if db.query(Dashboard).filter_by(key=body.key).first():
        raise HTTPException(status_code=409, detail="Bu key zaten var")
    code = body.code or STARTER
    _validate(code)
    dash = Dashboard(key=body.key, title=body.title, description=body.description,
                     code=code, created_by=user.username)
    db.add(dash)
    db.add(DashboardVersion(dashboard_key=body.key, code=code, created_by=user.username))
    db.commit()
    return dash


@router.get("/{key}", response_model=DashboardOut)
def get_dashboard(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dash = db.query(Dashboard).filter_by(key=key).first()
    if not dash:
        raise HTTPException(status_code=404, detail="Dashboard bulunamadı")
    return dash


@router.delete("/{key}")
def delete_dashboard(key: str, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    dash = db.query(Dashboard).filter_by(key=key).first()
    if not dash:
        raise HTTPException(status_code=404, detail="Dashboard bulunamadı")
    db.delete(dash)
    db.commit()
    return {"ok": True}


# --- kod + versiyon ---
@router.get("/{key}/code")
def get_code(key: str, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    dash = db.query(Dashboard).filter_by(key=key).first()
    if not dash:
        raise HTTPException(status_code=404, detail="Dashboard bulunamadı")
    return {"code": dash.code}


@router.put("/{key}/code")
def put_code(key: str, body: CodeIn, db: Session = Depends(get_db),
             user: User = Depends(require_analyst)):
    dash = db.query(Dashboard).filter_by(key=key).first()
    if not dash:
        raise HTTPException(status_code=404, detail="Dashboard bulunamadı")
    _validate(body.code)
    dash.code = body.code
    db.add(DashboardVersion(dashboard_key=key, code=body.code, created_by=user.username))
    db.commit()
    return {"ok": True}


@router.get("/{key}/versions", response_model=list[VersionOut])
def list_versions(key: str, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    return (db.query(DashboardVersion).filter_by(dashboard_key=key)
            .order_by(DashboardVersion.id.desc()).limit(50).all())


@router.get("/{key}/versions/{vid}")
def get_version(key: str, vid: int, db: Session = Depends(get_db),
                user: User = Depends(require_analyst)):
    v = db.query(DashboardVersion).filter_by(dashboard_key=key, id=vid).first()
    if not v:
        raise HTTPException(status_code=404, detail="Versiyon bulunamadı")
    return {"code": v.code, "created_at": v.created_at, "created_by": v.created_by}


# --- meta + çalıştırma + export ---
@router.get("/{key}/meta")
def meta(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dash = db.query(Dashboard).filter_by(key=key).first()
    if not dash:
        raise HTTPException(status_code=404, detail="Dashboard bulunamadı")
    try:
        return {"filter_schema": dashboard_meta(dash.code)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"filter_schema hatası: {e}")


def _run_code(code: str, filters: dict) -> dict:
    ctx = DashboardContext(filters=filters)
    try:
        return run_dashboard(code, ctx)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Çalıştırma hatası: {e}")


@router.post("/{key}/run")
def run_dashboard_ep(key: str, body: DashboardRunIn, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    dash = db.query(Dashboard).filter_by(key=key).first()
    if not dash:
        raise HTTPException(status_code=404, detail="Dashboard bulunamadı")
    return _run_code(dash.code, body.filters)


@router.post("/{key}/test")
def test_code(key: str, payload: dict, db: Session = Depends(get_db),
              user: User = Depends(require_analyst)):
    """Kaydetmeden kodu çalıştır (editörde önizleme)."""
    code = payload.get("code", "")
    filters = payload.get("filters", {})
    _validate(code)
    return {
        "filter_schema": dashboard_meta(code),
        "result": _run_code(code, filters),
    }


@router.post("/{key}/export")
def export(key: str, body: DashboardRunIn, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    dash = db.query(Dashboard).filter_by(key=key).first()
    if not dash:
        raise HTTPException(status_code=404, detail="Dashboard bulunamadı")
    result = _run_code(dash.code, body.filters)
    table = result.get("table", {})
    cols = [c["key"] for c in table.get("columns", [])]
    df = pd.DataFrame(table.get("rows", []))
    if cols:
        df = df.reindex(columns=cols)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        df.to_excel(xl, index=False, sheet_name="Veri")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{key}.xlsx"'},
    )
