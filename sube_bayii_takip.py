#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import traceback
from datetime import datetime, date
from email.mime.text import MIMEText

import gspread
import pandas as pd
import pyodbc
import smtplib
from gspread_dataframe import set_with_dataframe


# =========================
# MAIL
# =========================
def send_mail(subject, body, to_emails):
    from_email = "unalmertefew@gmail.com"
    from_password = "ujcn lxjz bbsp egln"

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(to_emails)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(from_email, from_password)
            smtp.sendmail(from_email, to_emails, msg.as_string())
    except Exception as me:
        print(f"[WARN] Mail gönderilemedi: {me}")


recipients = ["irfan.boran@isler.com.tr"]


# =========================
# AYARLAR
# =========================
day = datetime.today().strftime("%Y-%m-%d")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1dx1JaES2TZQwNlqB5OoP_MmwiIqcUnuTDJ35ZXood20/edit"
SERVICE_ACCOUNT_JSON = r"C:\Users\mert\Desktop\kurumsalrapor\kurumsalrapor-87ee4f03798c.json"

EXCLUDE_CODES = {"S.06.HEDİYELİ", "S.34.HEDİYEKİTAP"}

LOGO_SERVER = "192.168.46.174,1433"
META_SERVER = "192.168.46.174,1433"

LOGO_DB = "LOGO"
META_DB = "META"

DB_USERNAME = "mert"
LOGO_PASSWORD = "A3VLfd-6jy=9@AK_2023"
META_PASSWORD = "A3VLfd-6jy=9@AK_2023"

CONN_STR_LOGO = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={LOGO_SERVER};"
    f"DATABASE={LOGO_DB};"
    f"UID={DB_USERNAME};"
    f"PWD={LOGO_PASSWORD};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

CONN_STR_META = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={META_SERVER};"
    f"DATABASE={META_DB};"
    f"UID={DB_USERNAME};"
    f"PWD={META_PASSWORD};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)


# =========================
# SIGN HELPERS
# =========================
def calc_stock_signed_amount(df: pd.DataFrame) -> pd.Series:
    amt = pd.to_numeric(df["AMOUNT"], errors="coerce").fillna(0).abs()
    signed = pd.Series(0.0, index=df.index)

    stock_in = (
        ((df["IOCODE"] == 1) & (df["TRCODE"].isin([2, 3, 4, 13, 14, 50])))
        | ((df["IOCODE"] == 2) & (df["TRCODE"] == 25))
    )

    stock_out = (
        ((df["IOCODE"] == 0) & (df["TRCODE"] == 7))
        | ((df["IOCODE"] == 3) & (df["TRCODE"] == 25))
        | ((df["IOCODE"] == 4) & (df["TRCODE"].isin([7, 8, 51])))
    )

    signed.loc[stock_in] = amt.loc[stock_in]
    signed.loc[stock_out] = -amt.loc[stock_out]

    return signed

def calc_sales_signed_amount(df: pd.DataFrame) -> pd.Series:
    """
    Satış adedi için signed amount.
    Satış +, iade -.
    Satış dışı stok hareketleri burada 0 kalır.
    """
    amt = pd.to_numeric(df["AMOUNT"], errors="coerce").fillna(0).abs()
    signed = pd.Series(0.0, index=df.index)

    sale_mask = (
        ((df["IOCODE"] == 0) & (df["TRCODE"] == 7))      # online satış
        | ((df["IOCODE"] == 4) & (df["TRCODE"].isin([7, 8])))  # normal satış
    )

    return_mask = (
        (df["IOCODE"] == 1) & (df["TRCODE"].isin([2, 3, 4]))   # iadeler
    )

    signed.loc[sale_mask] = amt.loc[sale_mask]
    signed.loc[return_mask] = -amt.loc[return_mask]

    return signed


# =========================
# DB OKUMA
# =========================
def connection_logo(sql: str) -> pd.DataFrame:
    conn = pyodbc.connect(CONN_STR_LOGO)
    df = pd.read_sql(sql, conn)
    conn.close()

    df = df[df["CANCELLED"] == 0].copy()
    df = df[df["SOURCEINDEX"] != 9].copy()
    df = df[df["BookCode"].astype(str).str.startswith("İY", na=False)].copy()

    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).abs()
    df["NetSale"] = pd.to_numeric(df["NetSale"], errors="coerce").fillna(0).abs()

    df["Adj_Quantity"] = df["Quantity"]
    df.loc[df["TRCODE"].isin([2, 3]), "Adj_Quantity"] = -df.loc[df["TRCODE"].isin([2, 3]), "Quantity"]

    df["Adj_NetSale"] = df["NetSale"]
    df.loc[df["TRCODE"].isin([2, 3]), "Adj_NetSale"] = -df.loc[df["TRCODE"].isin([2, 3]), "NetSale"]

    df["SaleDate"] = pd.to_datetime(df["SaleDate"], errors="coerce")

    return df[
        [
            "DealerCode",
            "DealerName",
            "BookCode",
            "BookName",
            "barcode",
            "SaleDate",
            "Adj_Quantity",
            "Adj_NetSale",
            "TRCODE",
            "SOURCEINDEX",
            "CANCELLED",
        ]
    ]


def all_products_func() -> pd.DataFrame:
    conn = pyodbc.connect(CONN_STR_META)
    ap = pd.read_sql("SELECT * FROM dbo.all_products;", conn)
    conn.close()
    return ap


# =========================
# GSHEETS
# =========================
def open_spreadsheet(spreadsheet_url: str, service_account_json: str):
    gc = gspread.service_account(filename=service_account_json)
    return gc.open_by_url(spreadsheet_url)


def upsert_sheet(sh, df: pd.DataFrame, sheet_name: str, include_index: bool = False):
    try:
        ws = sh.worksheet(sheet_name)
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        rows = max(2, len(df) + 10)
        cols = max(2, len(df.columns) + (1 if include_index else 0) + 2)
        ws = sh.add_worksheet(title=sheet_name, rows=rows, cols=cols)

    set_with_dataframe(
        ws,
        df,
        include_index=include_index,
        include_column_header=True,
        resize=True,
    )
    return ws


# =========================
# SQL
# =========================
SQL_new = f"""
SELECT
    C.CODE              AS DealerCode,
    C.DEFINITION_       AS DealerName,
    S.CODE              AS BookCode,
    S.Name              AS BookName,
    S.PRODUCERCODE      AS barcode,
    ST.AMOUNT           AS Quantity,
    I.TRCODE            AS TRCODE,
    ST.SOURCEINDEX      AS SOURCEINDEX,
    ST.LINENET
      + COALESCE(ST.VATAMNT, 0)
      + COALESCE(ST.ADDTAXAMOUNT, 0)  AS NetSale,
    I.DATE_             AS SaleDate,
    ST.CANCELLED        AS CANCELLED
FROM LG_035_01_STLINE ST
JOIN LG_035_01_INVOICE I  ON ST.INVOICEREF = I.LOGICALREF
JOIN LG_035_ITEMS      S  ON ST.STOCKREF   = S.LOGICALREF
JOIN LG_035_CLCARD     C  ON I.CLIENTREF   = C.LOGICALREF
WHERE I.DATE_ >= '2025-01-01'
  AND I.DATE_ <= '{day}'

UNION ALL

SELECT
    C.CODE              AS DealerCode,
    C.DEFINITION_       AS DealerName,
    S.CODE              AS BookCode,
    S.Name              AS BookName,
    S.PRODUCERCODE      AS barcode,
    ST.AMOUNT           AS Quantity,
    I.TRCODE            AS TRCODE,
    ST.SOURCEINDEX      AS SOURCEINDEX,
    ST.LINENET
      + COALESCE(ST.VATAMNT, 0)
      + COALESCE(ST.ADDTAXAMOUNT, 0)  AS NetSale,
    I.DATE_             AS SaleDate,
    ST.CANCELLED        AS CANCELLED
FROM LG_036_01_STLINE ST
JOIN LG_036_01_INVOICE I  ON ST.INVOICEREF = I.LOGICALREF
JOIN LG_036_ITEMS      S  ON ST.STOCKREF   = S.LOGICALREF
JOIN LG_036_CLCARD     C  ON I.CLIENTREF   = C.LOGICALREF
WHERE I.DATE_ >= '2025-01-01'
  AND I.DATE_ <= '{day}'
"""


# =========================
# SUMMARY HELPERS
# =========================
def build_summary(df_cat: pd.DataFrame) -> pd.DataFrame:
    out = (
        df_cat.groupby(["barcode", "DealerCode", "DealerName", "periyot"], as_index=False)
        .agg(
            {
                "BookName_x": (lambda x: sorted(x.astype(str))[0]),
                "Yayınevi": "first",
                "Adj_Quantity": "sum",
            }
        )
        .rename(
            columns={
                "BookName_x": "Kitap Adı",
                "Adj_Quantity": "25-26 Adet",
            }
        )
    )

    out = out[~out["Kitap Adı"].astype(str).str.startswith("*", na=False)].copy()

    kitap_totals = out.groupby("Kitap Adı", as_index=False)["25-26 Adet"].sum()
    valid_books = kitap_totals.loc[kitap_totals["25-26 Adet"] >= 500, "Kitap Adı"]
    out = out[out["Kitap Adı"].isin(valid_books)].copy()

    return out


def build_summary_k(df_cat: pd.DataFrame) -> pd.DataFrame:
    out = (
        df_cat.groupby(["barcode", "DealerCode", "DealerName", "periyot"], as_index=False)
        .agg(
            {
                "Grup": "first",
                "BookName_x": (lambda x: sorted(x.astype(str))[0]),
                "Yayınevi": "first",
                "Adj_Quantity": "sum",
            }
        )
        .rename(
            columns={
                "BookName_x": "Kitap Adı",
                "Adj_Quantity": "25-26 Adet",
            }
        )
    )

    out = out[~out["Kitap Adı"].astype(str).str.startswith("*", na=False)].copy()

    kitap_totals = out.groupby("Kitap Adı", as_index=False)["25-26 Adet"].sum()
    valid_books = kitap_totals.loc[kitap_totals["25-26 Adet"] >= 500, "Kitap Adı"]
    out = out[out["Kitap Adı"].isin(valid_books)].copy()

    return out


# =========================
# MAIN
# =========================
def main():
    print("[INFO] 2025-2026 verisi çekiliyor...")
    df_new = connection_logo(SQL_new)

    print("[INFO] META all_products çekiliyor...")
    all_products = all_products_func()

    print("[INFO] Merge (barcode) ...")
    merged_new = df_new.merge(all_products, on="barcode", how="left")

    merged_new["DealerCode"] = (
        merged_new["DealerCode"]
        .astype(str)
        .str.replace("*", "", regex=False)
    )

    merged_new["periyot"] = pd.Timestamp("2025-07-01")
    merged_new.loc[
        merged_new["SaleDate"] < pd.Timestamp("2025-07-01"),
        "periyot"
    ] = pd.Timestamp("2025-01-01")

    bayii_df = merged_new[
        merged_new["DealerCode"].str.startswith("B.", na=False)
    ].copy()

    bayii_df = bayii_df[
        ~bayii_df["DealerCode"].isin(EXCLUDE_CODES)
    ].copy()

    print("[INFO] Kategori filtresi: PERAKENDE YAYIN (bayii)")
    perakende_bayii_raw = bayii_df[bayii_df["Kategori"] == "PERAKENDE YAYIN"].copy()

    perakende_bayii_summary = build_summary(perakende_bayii_raw)
    perakende_bayii = perakende_bayii_summary[
        ["DealerCode", "DealerName", "Kitap Adı", "Yayınevi", "25-26 Adet", "periyot"]
    ].copy()

    print("[INFO] Kategori filtresi: KURUMSAL DENEME (bayii)")
    kurumsal_bayii_raw = bayii_df[bayii_df["Kategori"] == "KURUMSAL DENEME"].copy()

    kurumsal_bayii_summary = build_summary_k(kurumsal_bayii_raw)

    kurumsal_bayii = (
        kurumsal_bayii_summary.groupby(
            ["Grup", "DealerCode", "DealerName", "periyot"],
            as_index=False,
        )
        .agg(
            {
                "Kitap Adı": (lambda x: sorted(x.astype(str))[0]),
                "Yayınevi": "first",
                "25-26 Adet": "sum",
            }
        )
    )

    kurumsal_deneme_bayii = kurumsal_bayii[
        ["DealerCode", "DealerName", "Kitap Adı", "Yayınevi", "25-26 Adet", "periyot"]
    ].copy()

    print("[INFO] EK: Stok + Satış (outer merge) hazırlanıyor...")

    # =========================
    # 1) STOK
    # =========================
    conn = pyodbc.connect(CONN_STR_LOGO)
    df_stock_raw = pd.read_sql(
        """
        SELECT
            LOGICALREF,
            STOCKREF,
            LINETYPE,
            TRCODE,
            SOURCEINDEX,
            IOCODE,
            INVOICEREF,
            CLIENTREF,
            AMOUNT,
            DATE_,
            CANCELLED
        FROM LG_036_01_STLINE
        """,
        conn,
    )
    conn.close()

    df_stock_raw = df_stock_raw[df_stock_raw["CANCELLED"] == 0].copy()
    df_stock_raw = df_stock_raw[df_stock_raw["SOURCEINDEX"] != 9].copy()

    df_stock_raw["AMOUNT_SIGNED"] = calc_stock_signed_amount(df_stock_raw)

    df_stok = (
        df_stock_raw.groupby(["STOCKREF", "SOURCEINDEX"], as_index=False)["AMOUNT_SIGNED"]
        .sum()
        .rename(columns={"AMOUNT_SIGNED": "STOK"})
    )

    conn = pyodbc.connect(CONN_STR_LOGO)
    items = pd.read_sql(
        """
        SELECT PRODUCERCODE, LOGICALREF, NAME
        FROM LG_036_ITEMS
        """,
        conn,
    )
    conn.close()

    df_stok = df_stok.merge(
        items,
        how="left",
        left_on="STOCKREF",
        right_on="LOGICALREF",
    )

    conn = pyodbc.connect(CONN_STR_LOGO)
    mapping = pd.read_sql(
        """
        SELECT NR, NAME AS DEPO
        FROM LOGO.dbo.L_CAPIWHOUSE
        WHERE FIRMNR = 36
        """,
        conn,
    )
    conn.close()

    df_stok = df_stok.merge(
        mapping,
        left_on="SOURCEINDEX",
        right_on="NR",
        how="left",
    )

    # =========================
    # 2) SATIŞ
    # =========================
    start_date = "2025-01-01"
    end_date = date.today().strftime("%Y-%m-%d")

    conn = pyodbc.connect(CONN_STR_LOGO)
    sales = pd.read_sql(
        f"""
        SELECT STOCKREF, SOURCEINDEX, AMOUNT, IOCODE, TRCODE, CANCELLED, CLIENTREF, DATE_
        FROM LG_036_01_STLINE
        WHERE DATE_ >= '{start_date}'
          AND DATE_ <= '{end_date}'

        UNION ALL

        SELECT STOCKREF, SOURCEINDEX, AMOUNT, IOCODE, TRCODE, CANCELLED, CLIENTREF, DATE_
        FROM LG_035_01_STLINE
        WHERE DATE_ >= '{start_date}'
          AND DATE_ <= '{end_date}'
        """,
        conn,
    )
    conn.close()

    sales["DATE_"] = pd.to_datetime(sales["DATE_"], errors="coerce")

    # satışla ilgili olmayan hareketleri tamamen dışarı at
    sales = sales[
        (sales["CANCELLED"] == 0)
        & (sales["CLIENTREF"] != 0)
        & (sales["SOURCEINDEX"] != 9)
        & (
            ((sales["IOCODE"] == 0) & (sales["TRCODE"] == 7))              # online satış
            | ((sales["IOCODE"] == 4) & (sales["TRCODE"].isin([7, 8])))    # satış
            | ((sales["IOCODE"] == 1) & (sales["TRCODE"].isin([2, 3, 4]))) # iade
        )
    ].copy()

    sales["periyot"] = pd.Timestamp("2025-07-01")
    sales.loc[
        sales["DATE_"] < pd.Timestamp("2025-07-01"),
        "periyot"
    ] = pd.Timestamp("2025-01-01")

    sales["SATIS_ADET"] = calc_sales_signed_amount(sales)

    sales_g = (
        sales.groupby(["STOCKREF", "SOURCEINDEX", "periyot"], as_index=False)["SATIS_ADET"]
        .sum()
    )

    # =========================
    # 3) MERGE
    # =========================
    sube_df = df_stok.merge(
        sales_g,
        on=["STOCKREF", "SOURCEINDEX"],
        how="outer",
    )

    sube_df["STOK"] = pd.to_numeric(sube_df["STOK"], errors="coerce").fillna(0)
    sube_df["SATIS_ADET"] = pd.to_numeric(sube_df["SATIS_ADET"], errors="coerce").fillna(0)

    sube_df = sube_df[
        ["SOURCEINDEX", "DEPO", "STOCKREF", "PRODUCERCODE", "STOK", "SATIS_ADET", "periyot"]
    ].copy()

    remove_depos = [
        "TOPTAN DEPO",
        "OSTİM DEPO",
        "ARIZALI",
        "ADA",
        "ILICAK",
        "OutletANK",
        "ÖRNEK",
        "YAYINEVİ",
        "TÜYAP İST",
        "ÖZYURT",
        "BARAN",
        "PazarlamaANK",
        "YENİKENT",
        "ERTEM-DEPO",
        "DENEME DEPO",
        "MEŞRUTİYET",
        "YENİMAHALLE",
        "BAĞLICA",
        "FATİH",
    ]

    sube_df = sube_df[
        ~sube_df["DEPO"].isin(remove_depos)
    ].copy()

    finito = sube_df.merge(
        all_products[["barcode", "Yayınevi", "BookName", "Kategori"]],
        left_on="PRODUCERCODE",
        right_on="barcode",
        how="left",
    ).drop(columns="PRODUCERCODE")

    finito = finito[finito["BookName"].notna()].copy()

    perakende_sube = finito.loc[
        finito["Kategori"] == "PERAKENDE YAYIN",
        ["barcode", "SOURCEINDEX", "DEPO", "BookName", "Yayınevi", "STOK", "SATIS_ADET", "periyot"],
    ].copy()

    kurumsal_sube = finito.loc[
        finito["Kategori"] == "KURUMSAL DENEME",
        ["barcode", "SOURCEINDEX", "DEPO", "BookName", "Yayınevi", "STOK", "SATIS_ADET", "periyot"],
    ].copy()

    unique_bayii = (
        perakende_bayii.dropna(subset=["DealerCode"])
        .drop_duplicates(subset=["DealerCode"])
        .reset_index(drop=True)[["DealerCode"]]
    )

    unique_books_df = pd.DataFrame(
        {
            "BookName": pd.concat(
                [
                    kurumsal_sube["BookName"],
                    perakende_sube["BookName"],
                    kurumsal_bayii["Kitap Adı"],
                    perakende_bayii["Kitap Adı"],
                ]
            ).dropna().unique()
        }
    )

    unique_books_duzey = unique_books_df.merge(
        all_products[["BookName", "Düzey"]],
        on="BookName",
        how="left",
    )

    print("[INFO] Google Sheets'e yazılıyor...")
    sh = open_spreadsheet(SPREADSHEET_URL, SERVICE_ACCOUNT_JSON)

    upsert_sheet(sh, perakende_bayii, "perakende_bayii")
    upsert_sheet(sh, perakende_sube, "perakende_sube")
    upsert_sheet(sh, kurumsal_deneme_bayii, "kurumsal_bayii")
    upsert_sheet(sh, kurumsal_sube, "kurumsal_sube")

    ws_values = sh.worksheet("values")
    ws_values.update(range_name="K1", values=[[datetime.now().strftime("%Y-%m-%d %H:%M:%S")]])
    ws_values.update(range_name="E:E", values=[[""]] * 500)

    values_data = [[v] for v in unique_bayii["DealerCode"].astype(str).tolist()]
    ws_values.update(range_name="E1", values=values_data)

    set_with_dataframe(
        ws_values,
        unique_books_duzey,
        row=1,
        col=13,
        include_index=False,
        include_column_header=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("[ERROR] Çalışma sırasında hata oluştu:", str(e))
        traceback.print_exc()

        subject = "[Kurumsal Rapor Bayii 25-26] HATA OLUŞTU"
        body = f"Hata mesajı: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        send_mail(subject, body, recipients)
        sys.exit(1)