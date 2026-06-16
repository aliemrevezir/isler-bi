"""Ingest: kaynak listesi/durum, manuel tetikleme, çalıştırma geçmişi."""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_analyst
from ..db import get_db
from ..ingest.sources import SOURCES
from ..models import IngestRun, IngestState, User
from ..schemas import IngestRunIn, IngestStateOut

router = APIRouter()


@router.get("/sources")
def list_sources(db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    states = {s.source: s for s in db.query(IngestState).all()}
    out = []
    for name, spec in SOURCES.items():
        st = states.get(name)
        out.append({
            "source": name,
            "kind": spec["kind"],
            "db": spec["db"],
            "table": f"raw.{spec['table']}",
            "last_watermark": st.last_watermark if st else None,
            "last_run_at": st.last_run_at if st else None,
            "last_status": st.last_status if st else None,
            "rows_last": st.rows_last if st else None,
        })
    return out


@router.get("/state", response_model=list[IngestStateOut])
def state(db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    return db.query(IngestState).all()


@router.post("/run")
def run(body: IngestRunIn, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    # backfill yalnız admin
    if body.mode == "backfill" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Backfill yalnız admin tarafından tetiklenebilir")
    if body.sources:
        unknown = [s for s in body.sources if s not in SOURCES]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Bilinmeyen kaynak: {unknown}")
    from ..tasks import ingest_logo
    task = ingest_logo.delay(
        sources=body.sources, mode=body.mode,
        from_date=body.from_date, to_date=body.to_date, triggered_by=user.username,
    )
    return {"task_id": task.id, "status": "queued", "mode": body.mode}


@router.get("/runs")
def runs(db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    rows = db.query(IngestRun).order_by(IngestRun.id.desc()).limit(20).all()
    out = []
    for r in rows:
        pct = None
        if r.progress:
            try:
                pct = json.loads(r.progress).get("overall_percent")
            except (ValueError, TypeError):
                pct = None
        out.append({
            "id": r.id, "sources": r.sources, "mode": r.mode, "status": r.status,
            "started_at": r.started_at, "finished_at": r.finished_at,
            "rows_out": r.rows_out, "error": r.error, "triggered_by": r.triggered_by,
            "overall_percent": pct,
        })
    return out


@router.get("/runs/{run_id}")
def run_detail(run_id: int, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    r = db.get(IngestRun, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Çalıştırma bulunamadı")
    progress = None
    if r.progress:
        try:
            progress = json.loads(r.progress)
        except (ValueError, TypeError):
            progress = None
    return {
        "id": r.id, "sources": r.sources, "mode": r.mode, "status": r.status,
        "started_at": r.started_at, "finished_at": r.finished_at,
        "rows_out": r.rows_out, "log": r.log, "error": r.error,
        "progress": progress,
    }
