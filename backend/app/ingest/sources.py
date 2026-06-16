"""Ingest kaynak tanımları: her kaynak için sütun whitelist'i ve SQL üretimi.

İki kaynak tipi:
- fact   : yıl-bazlı işlem tabloları (STLINE/INVOICE). Tarih (DATE_) ile incremental.
- master : küçük referans tabloları (ITEMS/CLCARD/all_products). Her çalışmada tam yenile.

Raw tablolar `raw` şemasında; her satıra `_ingested_at` ve `_source_year` eklenir.
"""
from ..config import settings

PERIOD = settings.LOGO_PERIOD

# Kapsam: mart'a alınacak şube (bayi) kodları. fact tabloları bu bayilere filtrelenir.
DEALER_CODES = [
    "V_82", "V_137", "V_142", "V_122", "V_29", "V_37", "V_119", "V_125",
    "V_81", "V_027", "V_134", "V_36", "V_120", "V_206", "V_05_1", "V_32",
    "V_01", "V_02", "V_121", "V_03", "V_124", "V_07", "V_147", "V_123",
    "V_38", "V_141", "V_10", "V_21_1", "V_14", "V_110", "V_04", "V_113",
    "V_116", "V_109", "V_136", "V_128", "V_22", "V_145", "V_23", "V_34",
    "V_33", "V_105", "V_19", "V_139", "V_20", "V_40", "V_16", "V_148",
    "V_131", "V_75", "V_114", "V_28", "V_115", "V_35", "V_72", "V_24",
    "V_18", "V_41", "V_26", "V_44", "V_140", "V_30", "V_46", "V_25",
    "V_102", "V_103", "V_104",
]


def _dealer_in_clause() -> str:
    return "(" + ", ".join(f"N'{c}'" for c in DEALER_CODES) + ")"


def _dealer_subquery(firm: str) -> str:
    return f"SELECT LOGICALREF FROM {firm}_CLCARD WHERE CODE IN {_dealer_in_clause()}"


# --- fact kaynakları ---

def _invoice_sql(firm: str, start: str, end: str) -> str:
    return f"""
    SELECT LOGICALREF, CLIENTREF, TRCODE, DATE_, GRPCODE
    FROM {firm}_{PERIOD}_INVOICE
    WHERE DATE_ >= '{start}' AND DATE_ < '{end}'
      AND CLIENTREF IN ({_dealer_subquery(firm)})
    """.strip()


def _stline_sql(firm: str, start: str, end: str) -> str:
    return f"""
    SELECT LOGICALREF, INVOICEREF, STOCKREF, CLIENTREF, TRCODE,
           AMOUNT, LINENET, VATAMNT, ADDTAXAMOUNT, CANCELLED, SOURCEINDEX, DATE_
    FROM {firm}_{PERIOD}_STLINE
    WHERE DATE_ >= '{start}' AND DATE_ < '{end}'
      AND CANCELLED = 0 AND SOURCEINDEX <> 9
      AND CLIENTREF IN ({_dealer_subquery(firm)})
    """.strip()


# --- master kaynakları ---

def _items_sql(firm: str) -> str:
    return f"SELECT LOGICALREF, CODE, NAME, PRODUCERCODE FROM {firm}_ITEMS"


def _clcard_sql(firm: str) -> str:
    return (
        f"SELECT LOGICALREF, CODE, DEFINITION_, CITY, SPECODE "
        f"FROM {firm}_CLCARD WHERE CODE IN {_dealer_in_clause()}"
    )


def _all_products_sql() -> str:
    return """
    SELECT BookCode AS book_code, barcode, BookName AS book_name,
           Kategori AS category, [Yayınevi] AS publisher, Grup AS grup,
           [Ürün Tip] AS urun_tip, Cins AS cins, [Tür] AS tur,
           [Düzey] AS duzey, [Sınıf] AS sinif, [Branş] AS brans,
           [Yıl] AS yil, Seri AS seri
    FROM all_products
    """.strip()


# Kaynak kayıt defteri. raw.<table> tablolarını üretir.
SOURCES = {
    "invoice": {
        "kind": "fact", "db": "LOGO", "table": "invoice",
        "watermark_col": "DATE_", "sql": _invoice_sql,
    },
    "stline": {
        "kind": "fact", "db": "LOGO", "table": "stline",
        "watermark_col": "DATE_", "sql": _stline_sql,
    },
    "items": {
        "kind": "master", "db": "LOGO", "table": "items", "sql": _items_sql,
    },
    "clcard": {
        "kind": "master", "db": "LOGO", "table": "clcard", "sql": _clcard_sql,
    },
    "all_products": {
        "kind": "master", "db": "META", "table": "all_products",
        "year_table": False, "sql": _all_products_sql,
    },
}

ALL_SOURCE_NAMES = list(SOURCES.keys())
