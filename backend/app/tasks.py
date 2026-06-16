"""Celery task'ları: ingest_logo, run_job, tick_scheduler."""
import json
from datetime import datetime, timezone

from celery.exceptions import SoftTimeLimitExceeded
from croniter import croniter

from .celery_app import celery
from .ctx import JobContext
from .db import SessionLocal
from .ingest.run import run_ingest
from .ingest.sources import ALL_SOURCE_NAMES
from .models import IngestRun, IngestState, Job, JobRun
from .runner import run_job as exec_job_code


def _now():
    return datetime.now(timezone.utc)


# ---------------- Ingest ----------------
# Ingest toplu bir işlem; kullanıcı transform job'larının kısa limitinden ayrı,
# kendi geniş zaman limiti (2 saat). İlk backfill milyonlarca satır olabilir.
@celery.task(name="app.tasks.ingest_logo", soft_time_limit=7200, time_limit=7500)
def ingest_logo(sources=None, mode="incremental", from_date=None, to_date=None, triggered_by="system"):
    db = SessionLocal()
    names = sources or ALL_SOURCE_NAMES
    run = IngestRun(sources=",".join(names), mode=mode, status="running",
                    started_at=_now(), triggered_by=triggered_by)
    db.add(run)
    db.commit()

    logs: list[str] = []

    def log_fn(line):
        logs.append(line)
        run.log = "\n".join(logs)[-20000:]
        db.commit()

    def progress_fn(state):
        run.progress = json.dumps(state, default=str)
        db.commit()

    try:
        # incremental için kaynak watermark'larını oku
        watermarks = {}
        if mode == "incremental":
            for st in db.query(IngestState).all():
                watermarks[st.source] = st.last_watermark

        result = run_ingest(sources=names, mode=mode, from_date=from_date,
                            to_date=to_date, watermarks=watermarks,
                            log_fn=log_fn, progress_fn=progress_fn)

        total = 0
        for name, info in result.items():
            total += info["rows"]
            st = db.get(IngestState, name) or IngestState(source=name)
            st.last_watermark = info["watermark"]
            st.last_run_at = _now()
            st.last_status = "success"
            st.rows_last = info["rows"]
            st.error = None
            db.merge(st)

        run.status = "success"
        run.rows_out = total
        run.finished_at = _now()
        run.log = "\n".join(logs)[-20000:]
        db.commit()
        return {"status": "success", "rows": total}
    except Exception as e:  # noqa: BLE001
        db.rollback()
        run.status = "error"
        run.error = str(e)
        run.finished_at = _now()
        run.log = "\n".join(logs)[-20000:]
        db.commit()
        raise
    finally:
        db.close()


# ---------------- Jobs ----------------
@celery.task(name="app.tasks.run_job", bind=True)
def run_job(self, job_key, run_id=None, triggered_by="system", params=None):
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(key=job_key).first()
        if not job:
            raise ValueError(f"Job bulunamadı: {job_key}")

        if run_id:
            jr = db.get(JobRun, run_id)
        else:
            jr = JobRun(job_key=job_key, status="pending", triggered_by=triggered_by)
            db.add(jr)
            db.commit()

        jr.status = "running"
        jr.started_at = _now()
        jr.celery_id = self.request.id
        jr.progress = json.dumps({"percent": 0, "message": "Başladı", "step": 0, "total": None})
        db.commit()

        # Canlı log + ilerleme: ctx her log satırında / progress çağrısında bunu tetikler.
        def progress_fn(state):
            jr.log = ctx.logger.text[-20000:]
            jr.progress = json.dumps(state, default=str)
            db.commit()

        ctx = JobContext(job_key=job_key, run_id=jr.id, params=params or {},
                         progress_fn=progress_fn)
        try:
            exec_job_code(job.code, ctx)
        except SoftTimeLimitExceeded:
            raise RuntimeError("Job zaman limitini aştı (soft_time_limit)")

        jr.status = "success"
        jr.rows_out = ctx.rows_out
        jr.log = ctx.logger.text[-20000:]
        jr.progress = json.dumps({"percent": 100, "message": "Tamamlandı",
                                  "step": ctx._step, "total": ctx._total})
        jr.finished_at = _now()
        db.commit()
        return {"status": "success", "rows_out": ctx.rows_out}
    except Exception as e:  # noqa: BLE001
        db.rollback()
        jr = db.get(JobRun, run_id) if run_id else None
        if jr is None:
            jr = db.query(JobRun).filter_by(job_key=job_key).order_by(JobRun.id.desc()).first()
        if jr:
            jr.status = "error"
            jr.error = str(e)
            jr.finished_at = _now()
            db.commit()
        raise
    finally:
        db.close()


# ---------------- Zamanlayıcı (DB cron) ----------------
@celery.task(name="app.tasks.tick_scheduler")
def tick_scheduler():
    """Her dakika çalışır; cron zamanı gelen enabled job'ları kuyruğa alır."""
    db = SessionLocal()
    try:
        now = datetime.now()
        fired = []
        for job in db.query(Job).filter(Job.enabled.is_(True)).all():
            expr = (job.schedule or "").strip()
            if not expr:
                continue
            try:
                if croniter.match(expr, now.replace(second=0, microsecond=0)):
                    jr = JobRun(job_key=job.key, status="pending", triggered_by="beat")
                    db.add(jr)
                    db.commit()
                    run_job.delay(job.key, run_id=jr.id, triggered_by="beat")
                    fired.append(job.key)
            except (ValueError, KeyError):
                continue
        return {"fired": fired}
    finally:
        db.close()
