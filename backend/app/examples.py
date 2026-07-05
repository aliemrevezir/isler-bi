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


# --------------------------------------------------------------------------
# JOB 3 — Bayii & Şube miktar takibi (Excel "Bayii Şube Miktar Takip" karşılığı):
#   raw.stline/clcard/items/all_products → derived.bayii_sube_takip__bayii (bayii satış)
#   raw.stok/items/all_products/capiwhouse → derived.bayii_sube_takip__sube (depo stok+satış)
# Detay = raporlama granülerliği (parçalanabilir); filtre kolonlarına indeks (hızlı).
# --------------------------------------------------------------------------
BAYII_SUBE_TAKIP_CODE = '''"""Bayii & Şube miktar takibi.

Çıktılar:
  derived.bayii_sube_takip__bayii  → bayii(B.*) × kitap × periyot satış adedi (kategori: PERAKENDE/KURUMSAL)
  derived.bayii_sube_takip__sube   → depo × kitap × periyot: STOK (cari mali yıl) + SATIS_ADET (periyot)

İşaret mantığı orijinal sube_bayii_takip.py'den: iade (TRCODE 2,3) negatif; stok/satış IOCODE+TRCODE
maskeleriyle. logicalref yıllar arası sabit olmadığından stok/satış BARCODE seviyesinde toplanır
(join yıl-içinde). Periyot: <2025-07 → '2025-01', değilse '2025-07'.
"""

# Hariç tutulan depolar (orijinal remove_depos).
EXCLUDE_DEPOS = (
    "'TOPTAN DEPO','OSTİM DEPO','ARIZALI','ADA','ILICAK','OutletANK','ÖRNEK','YAYINEVİ',"
    "'TÜYAP İST','ÖZYURT','BARAN','PazarlamaANK','YENİKENT','ERTEM-DEPO','DENEME DEPO',"
    "'MEŞRUTİYET','YENİMAHALLE','BAĞLICA','FATİH'"
)

BAYII_SQL = """
SELECT
    cl.code AS dealer_code,
    cl.definition_ AS dealer_name,
    it.producercode AS barcode,
    it.code AS book_code,
    it.name AS book_name,
    ap.publisher, ap.category, ap.duzey,
    CASE WHEN st.date_ < DATE '2025-07-01' THEN '2025-01' ELSE '2025-07' END AS periyot,
    SUM(CASE WHEN st.trcode IN (2,3) THEN -st.amount ELSE st.amount END) AS quantity
FROM raw.stline st
JOIN raw.clcard cl ON st.clientref = cl.logicalref AND st._source_year = cl._source_year
JOIN raw.items  it ON st.stockref  = it.logicalref AND st._source_year = it._source_year
JOIN (
    SELECT DISTINCT ON (barcode) barcode, publisher, category, duzey
    FROM raw.all_products WHERE barcode IS NOT NULL AND barcode <> '' ORDER BY barcode
) ap ON it.producercode = ap.barcode
WHERE cl.code LIKE 'B.%'
  AND it.code LIKE 'İY%'
  AND ap.category IN ('PERAKENDE YAYIN','KURUMSAL DENEME')
  AND st.date_ >= DATE '2025-01-01'
GROUP BY cl.code, cl.definition_, it.producercode, it.code, it.name,
         ap.publisher, ap.category, ap.duzey,
         CASE WHEN st.date_ < DATE '2025-07-01' THEN '2025-01' ELSE '2025-07' END
"""

SUBE_SQL = f"""
WITH mov AS (
    SELECT s.sourceindex, it.producercode AS barcode, s.iocode, s.trcode,
           s.yr, s.mon, s.amount, s._source_year
    FROM raw.stok s
    JOIN raw.items it ON s.stockref = it.logicalref AND s._source_year = it._source_year
),
stk AS (  -- STOK: cari mali yıl (en güncel _source_year), barcode bazında işaretli net
    SELECT sourceindex, barcode,
      SUM(CASE
        WHEN (iocode=1 AND trcode IN (2,3,4,13,14,50)) OR (iocode=2 AND trcode=25) THEN ABS(amount)
        WHEN (iocode=0 AND trcode=7) OR (iocode=3 AND trcode=25) OR (iocode=4 AND trcode IN (7,8,51)) THEN -ABS(amount)
        ELSE 0 END) AS stok
    FROM mov WHERE _source_year = (SELECT MAX(_source_year) FROM raw.stok)
    GROUP BY sourceindex, barcode
),
sat AS (  -- SATIS_ADET: 2025+ tüm yıllar, periyot bazında işaretli satış
    SELECT sourceindex, barcode,
      CASE WHEN (yr*100+mon) < 202507 THEN '2025-01' ELSE '2025-07' END AS periyot,
      SUM(CASE
        WHEN (iocode=0 AND trcode=7) OR (iocode=4 AND trcode IN (7,8)) THEN ABS(amount)
        WHEN (iocode=1 AND trcode IN (2,3,4)) THEN -ABS(amount)
        ELSE 0 END) AS satis_adet
    FROM mov WHERE (yr*100+mon) >= 202501
    GROUP BY sourceindex, barcode,
             CASE WHEN (yr*100+mon) < 202507 THEN '2025-01' ELSE '2025-07' END
),
ap AS (
    SELECT DISTINCT ON (barcode) barcode, book_name, publisher, category, duzey
    FROM raw.all_products WHERE barcode IS NOT NULL AND barcode <> '' ORDER BY barcode
),
depo AS (
    SELECT DISTINCT ON (sourceindex) sourceindex, depo
    FROM raw.capiwhouse ORDER BY sourceindex, _source_year DESC
)
SELECT
    COALESCE(stk.sourceindex, sat.sourceindex) AS sourceindex,
    d.depo,
    COALESCE(stk.barcode, sat.barcode) AS barcode,
    ap.book_name, ap.publisher, ap.category, ap.duzey,
    sat.periyot,
    COALESCE(stk.stok, 0) AS stok,
    COALESCE(sat.satis_adet, 0) AS satis_adet
FROM stk
FULL OUTER JOIN sat ON stk.sourceindex = sat.sourceindex AND stk.barcode = sat.barcode
JOIN ap ON ap.barcode = COALESCE(stk.barcode, sat.barcode)
LEFT JOIN depo d ON d.sourceindex = COALESCE(stk.sourceindex, sat.sourceindex)
WHERE ap.category IN ('PERAKENDE YAYIN','KURUMSAL DENEME')
  AND COALESCE(d.depo, '') NOT IN ({EXCLUDE_DEPOS})
"""


def run(ctx):
    ctx.progress(percent=10, message="Bayii satışları toplanıyor")
    bayii = ctx.read_sql(BAYII_SQL)
    ctx.logger.info(f"bayii: {len(bayii)} satır (bayii × kitap × periyot)")
    ctx.write_table("bayii", bayii, mode="replace",
                    indexes=[["category", "periyot", "dealer_code"], ["category", "publisher"]])

    ctx.progress(percent=60, message="Depo stok + satış toplanıyor")
    sube = ctx.read_sql(SUBE_SQL)
    ctx.logger.info(f"sube: {len(sube)} satır (depo × kitap × periyot)")
    ctx.write_table("sube", sube, mode="replace",
                    indexes=[["category", "periyot", "sourceindex"], ["category", "publisher"]])
    ctx.progress(percent=100, message="Bitti")
'''


# --------------------------------------------------------------------------
# DASHBOARD'lar 3-6 — Bayii & Şube panelleri (derived.bayii_sube_takip__*)
# Excel'in perakende_panel/kurumsal_panel sayfalarının bayii+şube kırılımları.
# --------------------------------------------------------------------------

# ---- DASHBOARD 3: Perakende — Bayii ----
PERAKENDE_BAYII_CODE = '''"""Perakende — Bayii: bayii × kitap satış + Düzey Nüfus/Hedef + Gönderilecek Adet.

Gönderilecek Adet = (adet>0 → 0; nüfus>10000 → 5; değilse 3).
"""

CATEGORY = "PERAKENDE YAYIN"
HEDEF_COL = "perakende_hedef"


def filter_schema():
    return [
        {"key": "periyot", "label": "Periyot", "type": "select", "options": [
            {"value": "", "label": "Tümü"},
            {"value": "2025-01", "label": "2025-01 (1. dönem)"},
            {"value": "2025-07", "label": "2025-07 (2. dönem)"}]},
        {"key": "cari", "label": "Cari (içerir)", "type": "text"},
        {"key": "yayinevi", "label": "Yayınevi (içerir)", "type": "text"},
        {"key": "urun", "label": "Ürün (içerir)", "type": "text"},
    ]


def _where(ctx, params):
    conds = ['b.category = :kat']
    params["kat"] = CATEGORY
    f = ctx.filters
    if f.get("periyot"):
        conds.append("b.periyot = :periyot"); params["periyot"] = f["periyot"]
    if f.get("cari"):
        conds.append("b.dealer_code ILIKE :cari"); params["cari"] = f"%{f['cari']}%"
    if f.get("yayinevi"):
        conds.append("b.publisher ILIKE :yay"); params["yay"] = f"%{f['yayinevi']}%"
    if f.get("urun"):
        conds.append("b.book_name ILIKE :urun"); params["urun"] = f"%{f['urun']}%"
    return " AND ".join(conds)


def run(ctx):
    empty = {"kpis": [], "charts": [], "table": {"columns": [], "rows": []}}
    params = {}
    where = _where(ctx, params)
    # Ortak CTE: agg (cari×kitap toplam) → valid (kitap toplam ≥500) → j (hedef + Gönderilecek Adet).
    base = (
        "WITH agg AS ("
        "  SELECT b.dealer_code, b.book_name, b.publisher, b.duzey, SUM(b.quantity) AS adet"
        '  FROM derived."bayii_sube_takip__bayii" b'
        f" WHERE {where}"
        "  GROUP BY b.dealer_code, b.book_name, b.publisher, b.duzey),"
        " valid AS (SELECT book_name FROM agg GROUP BY book_name HAVING SUM(adet) >= 500),"
        " j AS ("
        "  SELECT a.dealer_code, a.book_name, a.publisher, a.duzey, a.adet,"
        f"         h.nufus, h.{HEDEF_COL} AS hedef,"
        "         CASE WHEN a.adet > 0 THEN 0"
        "              WHEN COALESCE(h.nufus, 0) > 10000 THEN 5 ELSE 3 END AS gonderilecek"
        "  FROM agg a JOIN valid v ON v.book_name = a.book_name"
        "  LEFT JOIN app.cari_hedef h ON h.cari = a.dealer_code AND h.duzey = a.duzey)"
    )
    try:
        # KPI'lar tüm filtrelenmiş küme üzerinden (tablo LIMIT'inden bağımsız).
        kpi = ctx.read_sql(
            base + " SELECT COALESCE(SUM(adet),0) AS adet, COUNT(DISTINCT dealer_code) AS cari,"
                   " COALESCE(SUM(gonderilecek),0) AS gonder FROM j", params)
        df = ctx.read_sql(base + " SELECT * FROM j ORDER BY adet DESC LIMIT 1000", params)
    except Exception:  # noqa: BLE001 — tablo henüz yoksa (job çalışmadan) boş dön
        return empty
    if df.empty:
        return empty

    return {
        "kpis": [
            {"key": "adet", "label": "Toplam 25-26 Adet", "value": float(kpi["adet"][0]), "format": "int"},
            {"key": "cari", "label": "Cari Sayısı", "value": int(kpi["cari"][0]), "format": "int"},
            {"key": "gonder", "label": "Toplam Gönderilecek", "value": int(kpi["gonder"][0]), "format": "int"},
        ],
        "charts": [{
            "type": "bar", "title": "Yayınevine Göre Adet (ilk 15)",
            "x": list(df.groupby("publisher")["adet"].sum().sort_values(ascending=False).head(15).index),
            "series": [{"name": "Adet", "data": [round(float(v), 1) for v in
                        df.groupby("publisher")["adet"].sum().sort_values(ascending=False).head(15).values]}],
        }],
        "table": {
            "columns": [
                {"key": "dealer_code", "label": "Cari", "format": "text"},
                {"key": "book_name", "label": "Kitap", "format": "text"},
                {"key": "publisher", "label": "Yayınevi", "format": "text"},
                {"key": "duzey", "label": "Düzey", "format": "text"},
                {"key": "adet", "label": "25-26 Adet", "format": "int"},
                {"key": "nufus", "label": "Düzey Nüfus", "format": "int"},
                {"key": "hedef", "label": "Düzey Perakende Hedef", "format": "int"},
                {"key": "gonderilecek", "label": "Gönderilecek Adet", "format": "int"},
            ],
            "rows": df.fillna("").to_dict(orient="records"),
        },
    }
'''

# ---- DASHBOARD 4: Kurumsal — Bayii ----  (perakende ile aynı; kategori + hedef kolonu farklı)
KURUMSAL_BAYII_CODE = (PERAKENDE_BAYII_CODE
                       .replace('Perakende — Bayii', 'Kurumsal — Bayii')
                       .replace('CATEGORY = "PERAKENDE YAYIN"', 'CATEGORY = "KURUMSAL DENEME"')
                       .replace('HEDEF_COL = "perakende_hedef"', 'HEDEF_COL = "kurumsal_hedef"')
                       .replace('Düzey Perakende Hedef', 'Düzey Kurumsal Deneme Hedef'))

# ---- DASHBOARD 5: Perakende — Şube ----
PERAKENDE_SUBE_CODE = '''"""Perakende — Şube: depo × kitap STOK + satış + Gönderilecek Adet.

Gönderilecek Adet = (stok<=0 → 5; değilse 0). STOK çift sayımı engellenir (barcode başına MAX).
"""

CATEGORY = "PERAKENDE YAYIN"


def filter_schema():
    return [
        {"key": "periyot", "label": "Periyot", "type": "select", "options": [
            {"value": "", "label": "Tümü"},
            {"value": "2025-01", "label": "2025-01 (1. dönem)"},
            {"value": "2025-07", "label": "2025-07 (2. dönem)"}]},
        {"key": "depo", "label": "Depo (içerir)", "type": "text"},
        {"key": "yayinevi", "label": "Yayınevi (içerir)", "type": "text"},
        {"key": "urun", "label": "Ürün (içerir)", "type": "text"},
    ]


def run(ctx):
    empty = {"kpis": [], "charts": [], "table": {"columns": [], "rows": []}}
    params = {"kat": CATEGORY}
    conds = ["s.category = :kat"]
    f = ctx.filters
    if f.get("periyot"):
        conds.append("s.periyot = :periyot"); params["periyot"] = f["periyot"]
    if f.get("depo"):
        conds.append("s.depo ILIKE :depo"); params["depo"] = f"%{f['depo']}%"
    if f.get("yayinevi"):
        conds.append("s.publisher ILIKE :yay"); params["yay"] = f"%{f['yayinevi']}%"
    if f.get("urun"):
        conds.append("s.book_name ILIKE :urun"); params["urun"] = f"%{f['urun']}%"
    where = " AND ".join(conds)
    # f: barcode başına STOK (MAX, çift sayım yok) + periyot satışı; g: kitap×depo toplamı + Gönderilecek.
    base = (
        "WITH f AS ("
        "  SELECT s.depo, s.book_name, s.publisher, s.duzey, s.sourceindex, s.barcode,"
        "         MAX(s.stok) AS stok, SUM(s.satis_adet) AS satis"
        '  FROM derived."bayii_sube_takip__sube" s'
        f" WHERE {where}"
        "  GROUP BY s.depo, s.book_name, s.publisher, s.duzey, s.sourceindex, s.barcode),"
        " g AS ("
        "  SELECT depo, book_name, publisher, duzey,"
        "         SUM(stok) AS stok, SUM(satis) AS satis_adet,"
        "         CASE WHEN SUM(stok) <= 0 THEN 5 ELSE 0 END AS gonderilecek"
        "  FROM f GROUP BY depo, book_name, publisher, duzey)"
    )
    try:
        kpi = ctx.read_sql(
            base + " SELECT COALESCE(SUM(stok),0) AS stok, COALESCE(SUM(satis_adet),0) AS satis,"
                   " COUNT(DISTINCT depo) AS depo, COALESCE(SUM(gonderilecek),0) AS gonder FROM g", params)
        df = ctx.read_sql(base + " SELECT * FROM g ORDER BY satis_adet DESC LIMIT 1000", params)
    except Exception:  # noqa: BLE001
        return empty
    if df.empty:
        return empty

    return {
        "kpis": [
            {"key": "stok", "label": "Toplam Stok", "value": float(kpi["stok"][0]), "format": "int"},
            {"key": "satis", "label": "Toplam Satış Adedi", "value": float(kpi["satis"][0]), "format": "int"},
            {"key": "depo", "label": "Depo Sayısı", "value": int(kpi["depo"][0]), "format": "int"},
        ],
        "charts": [{
            "type": "bar", "title": "Depoya Göre Satış (ilk 15)",
            "x": list(df.groupby("depo")["satis_adet"].sum().sort_values(ascending=False).head(15).index),
            "series": [{"name": "Satış", "data": [round(float(v), 1) for v in
                        df.groupby("depo")["satis_adet"].sum().sort_values(ascending=False).head(15).values]}],
        }],
        "table": {
            "columns": [
                {"key": "depo", "label": "Depo", "format": "text"},
                {"key": "book_name", "label": "Kitap", "format": "text"},
                {"key": "publisher", "label": "Yayınevi", "format": "text"},
                {"key": "duzey", "label": "Düzey", "format": "text"},
                {"key": "stok", "label": "Stok", "format": "int"},
                {"key": "satis_adet", "label": "Satış Adedi", "format": "int"},
                {"key": "gonderilecek", "label": "Gönderilecek Adet", "format": "int"},
            ],
            "rows": df.fillna("").to_dict(orient="records"),
        },
    }
'''

# ---- DASHBOARD 6: Kurumsal — Şube ----
KURUMSAL_SUBE_CODE = (PERAKENDE_SUBE_CODE
                      .replace('Perakende — Şube', 'Kurumsal — Şube')
                      .replace('CATEGORY = "PERAKENDE YAYIN"', 'CATEGORY = "KURUMSAL DENEME"'))


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
    {
        "key": "bayii_sube_takip",
        "title": "Bayii & Şube Miktar Takip",
        "description": "raw → derived.bayii_sube_takip__bayii (bayii satış) + __sube (depo stok+satış)",
        "code": BAYII_SUBE_TAKIP_CODE,
        "schedule": "40 6 * * *",
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
    {
        "key": "perakende_bayii_panel",
        "title": "Perakende — Bayii",
        "description": "Bayii × kitap satış + Düzey Nüfus/Hedef + Gönderilecek Adet (PERAKENDE YAYIN)",
        "code": PERAKENDE_BAYII_CODE,
    },
    {
        "key": "kurumsal_bayii_panel",
        "title": "Kurumsal — Bayii",
        "description": "Bayii × kitap satış + Düzey Nüfus/Hedef + Gönderilecek Adet (KURUMSAL DENEME)",
        "code": KURUMSAL_BAYII_CODE,
    },
    {
        "key": "perakende_sube_panel",
        "title": "Perakende — Şube",
        "description": "Depo × kitap STOK + satış + Gönderilecek Adet (PERAKENDE YAYIN)",
        "code": PERAKENDE_SUBE_CODE,
    },
    {
        "key": "kurumsal_sube_panel",
        "title": "Kurumsal — Şube",
        "description": "Depo × kitap STOK + satış + Gönderilecek Adet (KURUMSAL DENEME)",
        "code": KURUMSAL_SUBE_CODE,
    },
]
