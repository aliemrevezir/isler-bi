"""Ingest orkestrasyonu: Logo → raw. Incremental (watermark) + backfill.

Canlı ilerleme: her kaynak için toplam satır COUNT ile hesaplanır, veri parça parça
(chunked) okunur; her parçada `progress_fn` ile UI'ya kaynak/yüzde/satır bildirilir.

Çalıştırma:
- Celery task `ingest_logo` (app/tasks.py) bunu çağırır.
- CLI: `python -m app.ingest.run --incremental` ya da
        `python -m app.ingest.run --backfill --from 2023-01-01 [--to 2026-06-16] [--source stline]`
"""
import io
import sys
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import text

from ..config import settings
from ..db import SCHEMA_RAW, engine
from .logo import firm_code_for_year, logo_conn, read_sql
from .sources import ALL_SOURCE_NAMES, SOURCES

CHUNK = 20000


def _log(msg: str, log_fn=None):
    line = f"[ingest] {msg}"
    print(line, file=sys.stderr)
    if log_fn:
        log_fn(line)


def _table_exists(table: str) -> bool:
    with engine.connect() as conn:
        return bool(conn.execute(
            text("SELECT 1 FROM information_schema.tables "
                 "WHERE table_schema = :s AND table_name = :t"),
            {"s": SCHEMA_RAW, "t": table},
        ).first())


def _delete_from(table: str, where: str = "", params: dict | None = None):
    if not _table_exists(table):
        return
    with engine.begin() as conn:
        conn.execute(text(f'DELETE FROM {SCHEMA_RAW}."{table}" {where}'), params or {})


def _write_raw(table: str, df: pd.DataFrame, source_year: int | None):
    """raw şemasına yaz (_ingested_at, _source_year ekleyerek).

    Postgres COPY ile toplu yazım — milyonlarca satır için INSERT'ten çok daha hızlı.
    Tablo yoksa şeması to_sql ile (0 satır) oluşturulur, veri COPY ile akıtılır.
    """
    if df.empty:
        return 0
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]  # downstream SQL temiz olsun
    df["_ingested_at"] = datetime.utcnow()
    df["_source_year"] = source_year

    if not _table_exists(table):
        df.head(0).to_sql(table, engine, schema=SCHEMA_RAW, if_exists="append", index=False)

    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    cols = ", ".join(f'"{c}"' for c in df.columns)
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.copy_expert(
            f"COPY {SCHEMA_RAW}.\"{table}\" ({cols}) FROM STDIN WITH (FORMAT csv, NULL '')",
            buf,
        )
        raw.commit()
    finally:
        raw.close()
    return len(df)


def _count(conn, inner_sql: str) -> int:
    df = read_sql(conn, f"SELECT COUNT(*) AS c FROM (\n{inner_sql}\n) q")
    return int(df["c"].iloc[0])


def _ingest_fact(name, spec, start, end_excl, log_fn=None, report=None) -> tuple[int, str | None]:
    """Yıl yıl gez; toplam satırı COUNT'la, parça parça çek ve ilerleme bildir."""
    table = spec["table"]
    sql_builder = spec["sql"]
    wm_col = spec["watermark_col"]
    _delete_from(table, f'WHERE "{wm_col.lower()}" >= :start',
                 {"start": datetime.combine(start, datetime.min.time())})

    years = [y for y in range(start.year, end_excl.year + 1)
             if max(start, date(y, 1, 1)) < min(end_excl, date(y + 1, 1, 1))]

    # Önce toplam satırı tahmin et (yüzde için)
    total_target = 0
    year_sql = {}
    conn = logo_conn(spec["db"])
    try:
        for y in years:
            eff_start = max(start, date(y, 1, 1))
            eff_end = min(end_excl, date(y + 1, 1, 1))
            sql = sql_builder(firm_code_for_year(y), f"{eff_start:%Y-%m-%d}", f"{eff_end:%Y-%m-%d}")
            year_sql[y] = sql
            try:
                total_target += _count(conn, sql)
            except Exception:  # noqa: BLE001 — COUNT başarısızsa yüzdesiz devam
                total_target = 0
        if report:
            report(rows=0, total=total_target or None, detail="çekiliyor")

        total = 0
        max_date: date | None = None
        for y in years:
            _log(f"{name} {y}: çekiliyor", log_fn)
            if report:
                report(rows=total, total=total_target or None, detail=f"{y} yılı")
            for chunk in pd.read_sql(year_sql[y], conn, chunksize=CHUNK):
                if not chunk.empty and wm_col in chunk.columns:
                    col = pd.to_datetime(chunk[wm_col], errors="coerce")
                    if col.notna().any():
                        cur = col.max().date()
                        max_date = cur if max_date is None else max(max_date, cur)
                total += _write_raw(table, chunk, y)
                if report:
                    report(rows=total, total=total_target or None, detail=f"{y} yılı")
    finally:
        conn.close()

    return total, (max_date.isoformat() if max_date else start.isoformat())


def _ingest_master(name, spec, ref_year, log_fn=None, report=None) -> tuple[int, str | None]:
    """Referans tablosunu tam yenile. Yıl-bazlı master'lar tüm yıllar için çekilir."""
    table = spec["table"]
    _delete_from(table)
    total = 0
    if spec.get("year_table", True):
        years = list(range(settings.HISTORY_START_YEAR, ref_year + 1))
        for i, y in enumerate(years):
            conn = logo_conn(spec["db"])
            try:
                df = read_sql(conn, spec["sql"](firm_code_for_year(y)))
            finally:
                conn.close()
            total += _write_raw(table, df, y)
            _log(f"{name} (master) {y}: {len(df)} satır", log_fn)
            if report:
                pct = int((i + 1) / len(years) * 100)
                report(rows=total, total=None, detail=f"{y} yılı", percent=pct)
    else:
        conn = logo_conn(spec["db"])
        try:
            df = read_sql(conn, spec["sql"]())
        finally:
            conn.close()
        total = _write_raw(table, df, None)
        _log(f"{name} (master) {total} satır", log_fn)
        if report:
            report(rows=total, total=total, detail="tamamlandı")
    return total, datetime.utcnow().date().isoformat()


def ingest_source(name, mode="incremental", from_date=None, to_date=None,
                  watermark=None, log_fn=None, report=None) -> tuple[int, str | None]:
    """Tek kaynağı çek. (rows, new_watermark) döner."""
    spec = SOURCES[name]
    today = date.today()

    if spec["kind"] == "master":
        return _ingest_master(name, spec, today.year, log_fn, report)

    history_start = date(settings.HISTORY_START_YEAR, 1, 1)
    if mode == "backfill":
        start = datetime.strptime(from_date, "%Y-%m-%d").date() if from_date else history_start
        end_excl = (datetime.strptime(to_date, "%Y-%m-%d").date() if to_date else today) + timedelta(days=1)
        _delete_from(spec["table"])
    else:
        start = datetime.strptime(watermark[:10], "%Y-%m-%d").date() if watermark else history_start
        end_excl = today + timedelta(days=1)

    return _ingest_fact(name, spec, start, end_excl, log_fn, report)


def run_ingest(sources=None, mode="incremental", from_date=None, to_date=None,
               watermarks=None, log_fn=None, progress_fn=None) -> dict:
    """Birden çok kaynağı çek. Canlı ilerlemeyi progress_fn(state) ile bildirir."""
    names = [n for n in (sources or ALL_SOURCE_NAMES) if n in SOURCES]
    watermarks = watermarks or {}

    state = {
        "sources": [{"source": n, "status": "pending", "rows": 0, "total": None,
                     "percent": 0, "detail": ""} for n in names],
        "current": None,
        "overall_percent": 0,
    }

    def _recompute_overall():
        if not state["sources"]:
            return 0
        frac = sum((1.0 if s["status"] == "done" else s["percent"] / 100.0)
                   for s in state["sources"])
        return int(frac / len(state["sources"]) * 100)

    def emit():
        state["overall_percent"] = _recompute_overall()
        if progress_fn:
            progress_fn(state)

    result = {}
    for idx, name in enumerate(names):
        entry = state["sources"][idx]
        entry["status"] = "running"
        state["current"] = name
        emit()

        def report(rows, total, detail, percent=None, _e=entry):
            _e["rows"] = rows
            _e["total"] = total
            _e["detail"] = detail
            if percent is not None:
                _e["percent"] = int(percent)
            elif total:
                _e["percent"] = int(min(rows / total, 1.0) * 100)
            emit()

        try:
            rows, wm = ingest_source(name, mode=mode, from_date=from_date, to_date=to_date,
                                     watermark=watermarks.get(name), log_fn=log_fn, report=report)
            entry.update(status="done", rows=rows, percent=100,
                         detail=f"{rows:,} satır".replace(",", "."))
            result[name] = {"rows": rows, "watermark": wm}
            _log(f"{name}: {rows} satır, watermark={wm}", log_fn)
        except Exception as e:  # noqa: BLE001
            entry.update(status="error", detail=str(e)[:200])
            emit()
            raise
        emit()

    state["current"] = None
    emit()
    return result


def _cli():
    import argparse

    p = argparse.ArgumentParser(description="Logo → raw ingest")
    p.add_argument("--incremental", action="store_true")
    p.add_argument("--backfill", action="store_true")
    p.add_argument("--from", dest="from_date")
    p.add_argument("--to", dest="to_date")
    p.add_argument("--source", action="append", dest="sources")
    args = p.parse_args()
    mode = "backfill" if args.backfill else "incremental"
    run_ingest(sources=args.sources, mode=mode, from_date=args.from_date, to_date=args.to_date)


if __name__ == "__main__":
    _cli()
