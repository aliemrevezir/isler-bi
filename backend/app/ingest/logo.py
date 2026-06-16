"""Logo/META (MSSQL) bağlantısı — pytds (pure-Python, ODBC'siz, Mac uyumlu)."""
import warnings

import pandas as pd
import pytds

from ..config import settings


def logo_conn(database: str):
    return pytds.connect(
        server=settings.LOGO_SERVER,
        port=settings.LOGO_PORT,
        database=database,
        user=settings.LOGO_USER,
        password=settings.LOGO_PASSWORD,
        login_timeout=15,
    )


def read_sql(conn, sql: str) -> pd.DataFrame:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.read_sql(sql, conn)


def firm_code_for_year(y: int) -> str:
    """Logo yıl bazlı firma öneki: 2025 -> LG_035."""
    return f"LG_{y - 1990:03d}"
