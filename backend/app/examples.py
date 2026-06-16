"""Seed örnekleri: iki job (raw→derived) ve iki dashboard (derived→görsel).

Bu kodlar DB'ye editable olarak yüklenir; kullanıcı UI'dan düzenleyebilir.
"""

# --------------------------------------------------------------------------
# JOB 1 — Aylık satış özeti: raw.stline → derived.satis_ozet__aylik
# --------------------------------------------------------------------------
SATIS_OZET_CODE = '''"""Aylık mağaza x ürün satış özeti.

NetSale = linenet + vatamnt + addtaxamount; TRCODE 2/3 (iade) negatife alınır.
Çıktı: derived.satis_ozet__aylik
"""

SQL = """
SELECT
    cl.code  AS store_code,
    cl.definition_ AS store_name,
    it.code  AS book_code,
    it.name  AS book_name,
    EXTRACT(YEAR  FROM st.date_)::int AS yr,
    EXTRACT(MONTH FROM st.date_)::int AS mon,
    COUNT(*) AS line_count,
    SUM(CASE WHEN st.trcode IN (2,3) THEN -st.amount ELSE st.amount END) AS quantity,
    SUM(CASE WHEN st.trcode IN (2,3)
             THEN -(st.linenet + COALESCE(st.vatamnt,0) + COALESCE(st.addtaxamount,0))
             ELSE  (st.linenet + COALESCE(st.vatamnt,0) + COALESCE(st.addtaxamount,0)) END) AS revenue
FROM raw.stline st
JOIN raw.clcard cl ON st.clientref = cl.logicalref AND st._source_year = cl._source_year
JOIN raw.items  it ON st.stockref  = it.logicalref AND st._source_year = it._source_year
GROUP BY cl.code, cl.definition_, it.code, it.name,
         EXTRACT(YEAR FROM st.date_), EXTRACT(MONTH FROM st.date_)
"""


def run(ctx):
    df = ctx.read_sql(SQL)
    ctx.logger.info(f"satis_ozet: {len(df)} satır toplandı")
    ctx.write_table("aylik", df, mode="replace")
'''

# --------------------------------------------------------------------------
# JOB 2 — Ürün kategori/yayınevi analizi (META zenginleştirme):
#          raw.stline + raw.all_products → derived.urun_kategori__aylik
# --------------------------------------------------------------------------
URUN_KATEGORI_CODE = '''"""Aylık kategori x yayınevi satış analizi (ürün öznitelikleriyle zenginleştirilmiş).

items.producercode (barkod) = all_products.barcode üzerinden META kataloğuna bağlanır.
Çıktı: derived.urun_kategori__aylik
"""

SQL = """
SELECT
    COALESCE(ap.category, '(bilinmeyen)')  AS category,
    COALESCE(ap.publisher, '(bilinmeyen)') AS publisher,
    COALESCE(ap.grup, '(bilinmeyen)')      AS grup,
    EXTRACT(YEAR  FROM st.date_)::int AS yr,
    EXTRACT(MONTH FROM st.date_)::int AS mon,
    SUM(CASE WHEN st.trcode IN (2,3) THEN -st.amount ELSE st.amount END) AS quantity,
    SUM(CASE WHEN st.trcode IN (2,3)
             THEN -(st.linenet + COALESCE(st.vatamnt,0) + COALESCE(st.addtaxamount,0))
             ELSE  (st.linenet + COALESCE(st.vatamnt,0) + COALESCE(st.addtaxamount,0)) END) AS revenue
FROM raw.stline st
JOIN raw.items it ON st.stockref = it.logicalref AND st._source_year = it._source_year
LEFT JOIN raw.all_products ap ON it.producercode = ap.barcode
GROUP BY ap.category, ap.publisher, ap.grup,
         EXTRACT(YEAR FROM st.date_), EXTRACT(MONTH FROM st.date_)
"""


def run(ctx):
    df = ctx.read_sql(SQL)
    ctx.logger.info(f"urun_kategori: {len(df)} satır toplandı")
    ctx.write_table("aylik", df, mode="replace")
'''

# --------------------------------------------------------------------------
# DASHBOARD 1 — Satış paneli (derived.satis_ozet__aylik)
# --------------------------------------------------------------------------
SATIS_PANEL_CODE = '''"""Satış paneli: aylık ciro trendi + mağaza kırılımı."""


def filter_schema():
    return [
        {"key": "ay_bas", "label": "Başlangıç Ayı", "type": "month"},
        {"key": "ay_bit", "label": "Bitiş Ayı", "type": "month"},
    ]


def _ym(val, default):
    if not val:
        return default
    y, m = str(val).split("-")
    return int(y) * 100 + int(m)


def run(ctx):
    df = ctx.read_sql(
        \'SELECT yr, mon, store_code, store_name, quantity, revenue \'
        \'FROM derived."satis_ozet__aylik"\'
    )
    empty = {"kpis": [], "charts": [], "table": {"columns": [], "rows": []}}
    if df.empty:
        return empty

    df["ym"] = df["yr"] * 100 + df["mon"]
    bas = _ym(ctx.filters.get("ay_bas"), int(df["ym"].min()))
    bit = _ym(ctx.filters.get("ay_bit"), int(df["ym"].max()))
    df = df[(df["ym"] >= bas) & (df["ym"] <= bit)]
    if df.empty:
        return empty

    toplam_ciro = float(df["revenue"].sum())
    toplam_adet = float(df["quantity"].sum())
    magaza_sayisi = int(df["store_code"].nunique())

    # Aylık trend
    trend = df.groupby("ym", as_index=False)["revenue"].sum().sort_values("ym")
    x = [f"{v // 100}-{v % 100:02d}" for v in trend["ym"]]

    # Mağaza kırılımı (ilk 20)
    mag = (df.groupby(["store_code", "store_name"], as_index=False)
             .agg(revenue=("revenue", "sum"), quantity=("quantity", "sum"))
             .sort_values("revenue", ascending=False).head(20))

    return {
        "kpis": [
            {"key": "ciro", "label": "Toplam Ciro", "value": toplam_ciro, "format": "money"},
            {"key": "adet", "label": "Toplam Adet", "value": toplam_adet, "format": "int"},
            {"key": "magaza", "label": "Mağaza Sayısı", "value": magaza_sayisi, "format": "int"},
        ],
        "charts": [{
            "type": "line", "title": "Aylık Ciro Trendi", "x": x,
            "series": [{"name": "Ciro", "data": [round(v, 2) for v in trend["revenue"]]}],
        }],
        "table": {
            "columns": [
                {"key": "store_code", "label": "Mağaza Kodu", "format": "text"},
                {"key": "store_name", "label": "Mağaza", "format": "text"},
                {"key": "revenue", "label": "Ciro", "format": "money"},
                {"key": "quantity", "label": "Adet", "format": "int"},
            ],
            "rows": mag.to_dict(orient="records"),
        },
    }
'''

# --------------------------------------------------------------------------
# DASHBOARD 2 — Kategori paneli (derived.urun_kategori__aylik)
# --------------------------------------------------------------------------
KATEGORI_PANEL_CODE = '''"""Kategori paneli: yayınevi/kategori bazlı ciro dağılımı."""


def filter_schema():
    return [
        {"key": "ay_bas", "label": "Başlangıç Ayı", "type": "month"},
        {"key": "ay_bit", "label": "Bitiş Ayı", "type": "month"},
    ]


def _ym(val, default):
    if not val:
        return default
    y, m = str(val).split("-")
    return int(y) * 100 + int(m)


def run(ctx):
    df = ctx.read_sql(
        \'SELECT yr, mon, category, publisher, quantity, revenue \'
        \'FROM derived."urun_kategori__aylik"\'
    )
    empty = {"kpis": [], "charts": [], "table": {"columns": [], "rows": []}}
    if df.empty:
        return empty

    df["ym"] = df["yr"] * 100 + df["mon"]
    bas = _ym(ctx.filters.get("ay_bas"), int(df["ym"].min()))
    bit = _ym(ctx.filters.get("ay_bit"), int(df["ym"].max()))
    df = df[(df["ym"] >= bas) & (df["ym"] <= bit)]
    if df.empty:
        return empty

    kat = (df.groupby("category", as_index=False)["revenue"].sum()
             .sort_values("revenue", ascending=False).head(12))
    yay = (df.groupby("publisher", as_index=False)
             .agg(revenue=("revenue", "sum"), quantity=("quantity", "sum"))
             .sort_values("revenue", ascending=False).head(20))

    return {
        "kpis": [
            {"key": "ciro", "label": "Toplam Ciro", "value": float(df["revenue"].sum()), "format": "money"},
            {"key": "kat", "label": "Kategori Sayısı", "value": int(df["category"].nunique()), "format": "int"},
            {"key": "yay", "label": "Yayınevi Sayısı", "value": int(df["publisher"].nunique()), "format": "int"},
        ],
        "charts": [{
            "type": "bar", "title": "Kategoriye Göre Ciro", "x": list(kat["category"]),
            "series": [{"name": "Ciro", "data": [round(v, 2) for v in kat["revenue"]]}],
        }],
        "table": {
            "columns": [
                {"key": "publisher", "label": "Yayınevi", "format": "text"},
                {"key": "revenue", "label": "Ciro", "format": "money"},
                {"key": "quantity", "label": "Adet", "format": "int"},
            ],
            "rows": yay.to_dict(orient="records"),
        },
    }
'''


SEED_JOBS = [
    {
        "key": "satis_ozet",
        "title": "Aylık Satış Özeti",
        "description": "raw.stline → derived.satis_ozet__aylik (mağaza x ürün x ay)",
        "code": SATIS_OZET_CODE,
        "schedule": "30 6 * * *",  # her gün 06:30 (ingest sonrası)
        "depends_on": None,
    },
    {
        "key": "urun_kategori",
        "title": "Ürün Kategori Analizi",
        "description": "raw.stline + META → derived.urun_kategori__aylik (kategori x yayınevi x ay)",
        "code": URUN_KATEGORI_CODE,
        "schedule": "35 6 * * *",
        "depends_on": None,
    },
]

SEED_DASHBOARDS = [
    {
        "key": "satis_panel",
        "title": "Satış Paneli",
        "description": "Aylık ciro trendi ve mağaza kırılımı",
        "code": SATIS_PANEL_CODE,
    },
    {
        "key": "kategori_panel",
        "title": "Kategori Paneli",
        "description": "Yayınevi/kategori bazlı ciro dağılımı",
        "code": KATEGORI_PANEL_CODE,
    },
]
