"""Jobs CRUD + kod/versiyon + çalıştırma + run geçmişi. (analyst/admin)"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_analyst
from ..db import get_db
from ..models import Job, JobRun, JobVersion, User
from ..schemas import (
    CodeIn,
    JobCreate,
    JobOut,
    JobUpdate,
    VersionOut,
)

router = APIRouter()

STARTER = '''"""Job: raw → derived. run(ctx) yaz.

ctx.read_sql(sql, params)  -> DataFrame (raw/derived okuma)
ctx.write_table(name, df, mode="replace"|"append", key=[...])  -> derived.<job_key>__<name>
ctx.params, ctx.logger, ctx.run_id
ctx.progress(percent=50, message="...")  -> canlı ilerleme çubuğu + mesaj
ctx.step(message="...", total=3)         -> adım sayacı (otomatik yüzde)
"""


def run(ctx):
    ctx.progress(percent=10, message="Veri okunuyor")
    df = ctx.read_sql("SELECT 1 AS x")
    ctx.progress(percent=60, message="Tablo yazılıyor")
    ctx.write_table("ornek", df, mode="replace")
    ctx.progress(percent=100, message="Bitti")
'''


def _validate(code: str):
    try:
        compile(code, "<job>", "exec")
    except SyntaxError as e:
        raise HTTPException(status_code=400, detail=f"Sözdizimi hatası: {e}")


@router.get("", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    return db.query(Job).order_by(Job.title).all()


@router.post("", response_model=JobOut)
def create_job(body: JobCreate, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    if db.query(Job).filter_by(key=body.key).first():
        raise HTTPException(status_code=409, detail="Bu key zaten var")
    code = body.code or STARTER
    _validate(code)
    job = Job(key=body.key, title=body.title, description=body.description, code=code,
              schedule=body.schedule, depends_on=body.depends_on, created_by=user.username)
    db.add(job)
    db.add(JobVersion(job_key=body.key, code=code, created_by=user.username))
    db.commit()
    return job


@router.get("/{key}", response_model=JobOut)
def get_job(key: str, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    job = db.query(Job).filter_by(key=key).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    return job


@router.patch("/{key}", response_model=JobOut)
def update_job(key: str, body: JobUpdate, db: Session = Depends(get_db),
               user: User = Depends(require_analyst)):
    job = db.query(Job).filter_by(key=key).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(job, field, val)
    db.commit()
    return job


@router.delete("/{key}")
def delete_job(key: str, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    job = db.query(Job).filter_by(key=key).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    db.delete(job)
    db.commit()
    return {"ok": True}


# --- kod + versiyon ---
@router.get("/{key}/code")
def get_code(key: str, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    job = db.query(Job).filter_by(key=key).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    return {"code": job.code}


@router.put("/{key}/code")
def put_code(key: str, body: CodeIn, db: Session = Depends(get_db),
             user: User = Depends(require_analyst)):
    job = db.query(Job).filter_by(key=key).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    _validate(body.code)
    job.code = body.code
    db.add(JobVersion(job_key=key, code=body.code, created_by=user.username))
    db.commit()
    return {"ok": True}


@router.get("/{key}/versions", response_model=list[VersionOut])
def list_versions(key: str, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    return db.query(JobVersion).filter_by(job_key=key).order_by(JobVersion.id.desc()).limit(50).all()


@router.get("/{key}/versions/{vid}")
def get_version(key: str, vid: int, db: Session = Depends(get_db),
                user: User = Depends(require_analyst)):
    v = db.query(JobVersion).filter_by(job_key=key, id=vid).first()
    if not v:
        raise HTTPException(status_code=404, detail="Versiyon bulunamadı")
    return {"code": v.code, "created_at": v.created_at, "created_by": v.created_by}


# --- çalıştırma + geçmiş ---
@router.post("/{key}/run")
def run_now(key: str, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    job = db.query(Job).filter_by(key=key).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    jr = JobRun(job_key=key, status="pending", triggered_by=user.username)
    db.add(jr)
    db.commit()
    from ..tasks import run_job as run_job_task
    run_job_task.delay(key, run_id=jr.id, triggered_by=user.username)
    return {"run_id": jr.id, "status": "queued"}


@router.get("/{key}/runs")
def list_runs(key: str, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    rows = db.query(JobRun).filter_by(job_key=key).order_by(JobRun.id.desc()).limit(30).all()
    out = []
    for r in rows:
        pct = None
        if r.progress:
            try:
                pct = json.loads(r.progress).get("percent")
            except (ValueError, TypeError):
                pct = None
        out.append({
            "id": r.id, "job_key": r.job_key, "status": r.status,
            "started_at": r.started_at, "finished_at": r.finished_at,
            "rows_out": r.rows_out, "error": r.error, "triggered_by": r.triggered_by,
            "percent": pct,
        })
    return out


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    jr = db.get(JobRun, run_id)
    if not jr:
        raise HTTPException(status_code=404, detail="Çalıştırma bulunamadı")
    progress = None
    if jr.progress:
        try:
            progress = json.loads(jr.progress)
        except (ValueError, TypeError):
            progress = None
    return {
        "id": jr.id, "job_key": jr.job_key, "status": jr.status,
        "started_at": jr.started_at, "finished_at": jr.finished_at,
        "rows_out": jr.rows_out, "log": jr.log, "error": jr.error,
        "triggered_by": jr.triggered_by, "progress": progress,
    }
