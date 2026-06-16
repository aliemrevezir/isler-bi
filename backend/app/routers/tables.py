"""Şema introspection: job/dashboard yazarken raw/derived tablolarını keşfet."""
from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..auth import require_analyst
from ..db import SCHEMA_DERIVED, SCHEMA_RAW, engine
from ..models import User

router = APIRouter()


@router.get("")
def list_tables(user: User = Depends(require_analyst)):
    """raw ve derived şemalarındaki tablo + sütunları döndür."""
    sql = text("""
        SELECT table_schema, table_name, column_name, data_type, ordinal_position
        FROM information_schema.columns
        WHERE table_schema IN (:raw, :derived)
        ORDER BY table_schema, table_name, ordinal_position
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"raw": SCHEMA_RAW, "derived": SCHEMA_DERIVED}).all()

    tables: dict[str, dict] = {}
    for schema, table, col, dtype, _pos in rows:
        full = f"{schema}.{table}"
        tables.setdefault(full, {"schema": schema, "table": table, "columns": []})
        tables[full]["columns"].append({"name": col, "type": dtype})
    return list(tables.values())


@router.get("/preview")
def preview(table: str, limit: int = 20, user: User = Depends(require_analyst)):
    """Bir tablonun ilk satırlarını göster (schema.table biçiminde, raw/derived)."""
    if "." not in table:
        return {"error": "schema.table biçiminde verin"}
    schema, name = table.split(".", 1)
    if schema not in (SCHEMA_RAW, SCHEMA_DERIVED):
        return {"error": "yalnız raw/derived"}
    limit = max(1, min(limit, 200))
    with engine.connect() as conn:
        rows = conn.execute(text(f'SELECT * FROM "{schema}"."{name}" LIMIT {limit}')).mappings().all()
    return {"rows": [dict(r) for r in rows]}
