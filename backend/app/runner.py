"""Editable Python yürütücü — güven temelli TAM PYTHON (sandbox yok).

Plan kararı: job/dashboard kodu worker içinde tam yetkiyle çalışır. Koruma katmanları:
RBAC (yalnız admin/analyst yazar), versiyonlama, audit (job_runs), Celery zaman limiti.
Bu nedenle burada builtins kısıtlaması YOKTUR.
"""
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from .ctx import DashboardContext, JobContext


def _exec_namespace(code: str) -> dict:
    ns: dict = {
        "pd": pd, "np": np,
        "date": date, "datetime": datetime, "timedelta": timedelta,
    }
    exec(compile(code, "<user-code>", "exec"), ns)
    return ns


def run_job(code: str, ctx: JobContext):
    """Job kodunu çalıştır: run(ctx) zorunlu."""
    ns = _exec_namespace(code)
    fn = ns.get("run")
    if not callable(fn):
        raise ValueError("Job kodu bir run(ctx) fonksiyonu tanımlamalı")
    return fn(ctx)


def dashboard_meta(code: str) -> list:
    """Dashboard filter_schema() → UI filtre tanımları (opsiyonel)."""
    ns = _exec_namespace(code)
    fn = ns.get("filter_schema")
    if not callable(fn):
        return []
    return fn() or []


def run_dashboard(code: str, ctx: DashboardContext) -> dict:
    """Dashboard kodunu çalıştır: run(ctx) → {kpis, charts, table}."""
    ns = _exec_namespace(code)
    fn = ns.get("run")
    if not callable(fn):
        raise ValueError("Dashboard kodu bir run(ctx) fonksiyonu tanımlamalı")
    out = fn(ctx) or {}
    return {
        "kpis": out.get("kpis", []),
        "charts": out.get("charts", []),
        "table": out.get("table", {"columns": [], "rows": []}),
    }
