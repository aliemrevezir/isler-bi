"""Job ve Dashboard kodlarına verilen çalıştırma bağlamı (ctx).

- JobContext: raw/derived okur, derived.<job_key>__<name> yazar.
- DashboardContext: yalnız okur (read-only), filtreleri taşır.
"""
import re

import pandas as pd
from sqlalchemy import text

from .db import SCHEMA_DERIVED, engine


def _safe_ident(name: str) -> str:
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name or ""):
        raise ValueError(f"Geçersiz tablo/isim: {name!r}")
    return name


class _Logger:
    def __init__(self, sink=None):
        self.lines: list[str] = []
        self._sink = sink  # her satırda çağrılır → canlı log akışı

    def info(self, msg):
        self.lines.append(str(msg))
        if self._sink:
            self._sink()

    # logger("...") kısayolu
    def __call__(self, msg):
        self.info(msg)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


class JobContext:
    """Job kodunun kullandığı bağlam. job kendi derived isim-uzayına yazar."""

    def __init__(self, job_key: str, run_id: int | None = None, params: dict | None = None,
                 progress_fn=None):
        self.job_key = _safe_ident(job_key)
        self.run_id = run_id
        self.params = params or {}
        # progress_fn(state) DB'ye canlı yazar; logger her satırda da onu tetikler.
        self._progress_fn = progress_fn
        self.logger = _Logger(sink=self._flush)
        self.rows_out = 0
        # canlı ilerleme durumu
        self._percent = 0
        self._message = ""
        self._step = 0
        self._total: int | None = None

    def _state(self) -> dict:
        return {
            "percent": self._percent,
            "message": self._message,
            "step": self._step,
            "total": self._total,
        }

    def _flush(self):
        if self._progress_fn:
            self._progress_fn(self._state())

    def progress(self, percent: float | None = None, message: str | None = None,
                 step: int | None = None, total: int | None = None):
        """Canlı ilerleme bildir. Hepsi opsiyonel.

        ctx.progress(message="Veri okunuyor")             → mesaj + log
        ctx.progress(percent=40, message="Yarısı bitti")  → çubuk %40
        ctx.progress(step=3, total=10)                     → %30 (otomatik)
        """
        if total is not None:
            self._total = int(total)
        if step is not None:
            self._step = int(step)
        if percent is not None:
            self._percent = max(0, min(100, int(percent)))
        elif self._total:
            self._percent = min(100, int(self._step / max(1, self._total) * 100))
        if message is not None:
            self._message = str(message)
            self.logger.lines.append(str(message))  # mesaj log'a da düşer
        self._flush()

    def step(self, message: str | None = None, total: int | None = None):
        """Bir sonraki adıma geç (step += 1) ve yüzdeyi total'a göre güncelle."""
        if total is not None:
            self._total = int(total)
        self._step += 1
        self.progress(message=message)

    def read_sql(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})

    def write_table(self, name: str, df: pd.DataFrame,
                    mode: str = "replace", key: list[str] | None = None) -> int:
        """derived.<job_key>__<name> tablosuna yazar.

        mode="replace": tabloyu yeniden oluştur.
        mode="append":  ekle. key verilirse upsert (eşleşen anahtarları silip ekler).
        """
        short = _safe_ident(name)
        table = f"{self.job_key}__{short}"
        if mode == "replace":
            df.to_sql(table, engine, schema=SCHEMA_DERIVED, if_exists="replace",
                      index=False, chunksize=5000, method="multi")
        elif mode == "append":
            if key:
                self._delete_keys(table, df, key)
            df.to_sql(table, engine, schema=SCHEMA_DERIVED, if_exists="append",
                      index=False, chunksize=5000, method="multi")
        else:
            raise ValueError("mode 'replace' veya 'append' olmalı")
        self.rows_out += len(df)
        self.logger.info(f"yazıldı: {SCHEMA_DERIVED}.{table} ({len(df)} satır, mode={mode})")
        return len(df)

    def _delete_keys(self, table: str, df: pd.DataFrame, key: list[str]):
        # Tablo yoksa silme gerekmez (ilk yazım)
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM information_schema.tables "
                     "WHERE table_schema=:s AND table_name=:t"),
                {"s": SCHEMA_DERIVED, "t": table},
            ).first()
        if not exists:
            return
        keycols = [_safe_ident(k) for k in key]
        uniq = df[keycols].drop_duplicates()
        with engine.begin() as conn:
            for _, row in uniq.iterrows():
                cond = " AND ".join(f'"{k}" = :{k}' for k in keycols)
                conn.execute(
                    text(f'DELETE FROM {SCHEMA_DERIVED}."{table}" WHERE {cond}'),
                    {k: row[k] for k in keycols},
                )


class DashboardContext:
    """Dashboard kodunun bağlamı: read-only. filters UI'dan gelir."""

    def __init__(self, filters: dict | None = None):
        self.filters = filters or {}
        self.logger = _Logger()

    def read_sql(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})
