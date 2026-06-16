# İşler Veri Platformu (v2)

Genel amaçlı veri platformu: **Logo ERP'den ham veri çek → kullanıcı Python job'larıyla işle → dashboard'larda göster.**

```
LOGO (MSSQL) ──ingest──> raw (Postgres) ──jobs (editable Python)──> derived (Postgres) ──dashboards──> UI
```

## Mimari

| Servis | Görev |
|---|---|
| `postgres` | Platform DB — `raw` (Logo aynası), `derived` (job çıktıları), `app` (meta) şemaları |
| `redis` | Celery broker + result backend |
| `backend` | FastAPI: auth, RBAC, ingest/job/dashboard CRUD + tetikleme. **Logo'ya bağlanmaz.** |
| `worker` | Celery worker: ingest + kullanıcı transform job'larını çalıştırır. Logo + Postgres erişimi. |
| `beat` | Celery Beat: günlük ingest (06:00) + DB cron job zamanlayıcı (her dakika) |
| `frontend` | React (nginx): `/api` ters proxy |

`backend`/`worker`/`beat` aynı imajı paylaşır; `entrypoint.sh` rolü seçer (`api`|`worker`|`beat`).

## Hızlı başlangıç

```bash
cp .env.example .env        # LOGO_PASSWORD ve APP_JWT_SECRET'ı doldur
docker compose up --build
```

- UI:        http://localhost:8080
- API:       http://localhost:8000/api/health
- Demo kullanıcılar: `admin/admin123`, `analist/analist123`, `viewer/viewer123`

> Logo erişimi yalnız `worker`/`beat` içindir; canlıda VPN/ağ erişimi olan makinede çalıştırın.

## Katmanlar

### 1) Ingest (Logo → raw)
- `pytds` ile bağlanır (Mac/ODBC'siz). Yıl tablosu: `LG_{yıl-1990:03d}` (2025 → LG_035).
- Kaynaklar (`app/ingest/sources.py`): `invoice`, `stline` (fact, tarih-bazlı incremental), `items`, `clcard`, `all_products` (master, tam yenile). Her kaynak **sütun whitelist'i** ile çekilir; raw'a küçük harf normalize sütunlar + `_ingested_at`, `_source_year`.
- **Incremental:** `app.ingest_state(source, last_watermark)`; sınır günü idempotent re-pull.
- **Backfill:** UI'dan (admin) tarih aralığıyla tam yeniden çekim. CLI: `python -m app.ingest.run --backfill --from 2023-01-01`.
- Tetikleme: Beat (günlük 06:00), UI "Şimdi Çek", CLI.

### 2) Jobs (raw → derived, editable Python)
- `app.jobs(key,title,code,schedule,...)` + `job_versions` (versiyonlama) + `job_runs` (audit/log).
- Kod sözleşmesi: `run(ctx)`. `ctx.read_sql(sql, params)` → DataFrame; `ctx.write_table(name, df, mode, key)` → `derived.<job_key>__<name>`; `ctx.params`, `ctx.logger`, `ctx.run_id`.
- **Tam Python (sandbox yok)** — güven temelli: yalnız admin/analyst yazar (RBAC), her sürüm versiyonlanır, her çalıştırma audit'lenir, Celery `soft_time_limit` uygular.
- Tetikleme: Beat cron (`schedule`), UI "Çalıştır", (opsiyonel) ingest sonrası zincir.

### 3) Dashboards (derived → görsel)
- `app.dashboards(key,title,code,...)` + `dashboard_versions`. **read-only.**
- Sözleşme: `filter_schema()` (UI filtreleri) + `run(ctx)` → `{kpis, charts, table}`. `ctx.read_sql`, `ctx.filters`.
- Aynı derived'den çok dashboard. Excel export ortak.

## Örnek içerik (seed)
- Job `satis_ozet` → `derived.satis_ozet__aylik` (mağaza×ürün×ay; NetSale, TRCODE iade).
- Job `urun_kategori` → `derived.urun_kategori__aylik` (META kategori/yayınevi zenginleştirme).
- Dashboard `satis_panel` (aylık ciro trendi + mağaza kırılımı), `kategori_panel` (kategori/yayınevi dağılımı).

İlk kullanım: **Ingest → Şimdi Çek** (raw dolar) → **Jobs → satis_ozet → Çalıştır** (derived dolar) → **Dashboards → Satış Paneli**.

## Auth & RBAC
- JWT (PyJWT) + bcrypt. Roller: `admin` (her şey), `analyst` (job/dashboard yazar/çalıştırır, ingest tetikler), `viewer` (dashboard görür).
- Kaynak-bazlı izinler `app.permissions`. Tüm tetiklemeler audit'lenir.

## Geliştirme notları
- Backend/worker tek imaj; şema+seed `api` açılışında idempotent çalışır.
- Beat zamanlaması `app/celery_app.py`; DB cron job'ları `tick_scheduler` her dakika `croniter` ile kontrol eder.
- Yeni kaynak: `sources.py`'ye sütun whitelist'i ekle.
