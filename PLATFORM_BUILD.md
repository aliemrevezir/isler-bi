# İşler Veri Platformu — v2 Build Dokümanı (Claude Code için)

> Bu doküman, mevcut MVP'nin (tek-amaçlı raporlama) yerine geçecek **genel amaçlı
> veri platformunun** sıfırdan kurulumu içindir. MVP'den kanıtlanmış parçalar yeniden
> kullanılır; eksik kalan altyapı (kalıcı job kuyruğu, scheduler, katman ayrımı) düzgün kurulur.

## Context

Mevcut MVP, Logo ERP satışından tek bir mart üretip sabit raporlar/dashboard'lar sunuyordu.
İhtiyaç büyüdü: **her gün Logo'dan ham veri çekip, kullanıcının yazdığı Python job'larıyla
işleyip, çıkan anlamlı veriyi dashboard'larda göstermek.** Akış üç net katman:

```
LOGO (MSSQL)  ──ingest──>  raw (Postgres)  ──jobs (editable Python)──>  derived (Postgres)  ──dashboards──>  UI
   kaynak                    günlük ayna            worker'lar çalıştırır        iş çıktıları         KPI/grafik/tablo
```

**MVP'den taşınan tecrübe:** Logo'ya `pytds` ile bağlanma (Mac'te ODBC yok), yıl-bazlı tablolar
(`LG_0xx`), TRCODE 2/3 iade negatifleştirme, NetSale = LINENET+VATAMNT+ADDTAXAMOUNT,
FastAPI+JWT+RBAC, editable Python + versiyonlama, React+Vite+Tailwind+ECharts+Monaco,
Docker compose. Bunlar yeniden kullanılır — **kod kopyalanmaz, desen taşınır**.

## Onaylanan kararlar
1. **Job altyapısı:** Celery + Redis + Beat (zamanlı + manuel tetikleme, retry, izole worker, ilerleme).
2. **Job izolasyonu:** Güven temelli **tam Python** (sandbox yok). Yalnız admin/analyst yazar/düzenler;
   RBAC + audit + versiyonlama + her job kendi derived şemasına yazar. (Dahili araç; güvenlik notu aşağıda.)
3. **Dashboard:** Job'tan ayrı katman. Job derived tablo üretir; dashboard o tabloları okuyup görselleştirir
   (editable Python/spec; aynı derived'den çok dashboard).
4. **Ingest:** Incremental (günlük tarih-bazlı delta) + tam yeniden çekim (backfill) komutu.

---

## Mimari & Servisler (Docker compose)

Tüm geliştirme ve çalıştırma Docker üzerinden. Servisler:

| Servis | Görev | Not |
|---|---|---|
| `postgres` | Platform DB (raw + derived + app şemaları) | Named volume |
| `redis` | Celery broker + result backend | |
| `backend` | FastAPI: auth, RBAC, ingest/job/dashboard CRUD + tetikleme, dashboard sorgulama | |
| `worker` | Celery worker: ingest job + kullanıcı transform job'larını çalıştırır | Logo + Postgres erişimi |
| `beat` | Celery Beat: zamanlanmış job'lar (günlük ingest, zamanlı transform'lar) | |
| `frontend` | React (nginx): `/api` ters proxy | |

> **Logo erişimi yalnız `worker`/`beat`** içindir (canlıda Logo DB'sinin olduğu makine/ağdan).
> `backend` Logo'ya bağlanmaz; job'ları Celery'ye kuyruklar. Geliştirmede VPN ile worker bağlanır.

### Postgres şemaları
- `raw`   — Logo aynası (yalnız ingest yazar; sadece gerekli sütunlar).
- `derived` — job çıktıları (her job kendi tablo(lar)ını yönetir).
- `app`   — platform metası (users, jobs, job_runs, dashboards, ingest_state, permissions, versions).

---

## 1) Ingest katmanı (LOGO → raw)

Amaç: ihtiyaç duyulan Logo tablolarını **gerekli sütunlarla** (gereksiz sütun taşımadan) günlük çekmek.

- **Bağlantı:** `pytds` (pure-Python; Mac/ODBC'siz). Yıl tablosu: `LG_{yıl-1990:03d}` (örn 2025→LG_035), dönem `01`.
- **Kaynak tablolar (başlangıç kapsamı):** `*_STLINE`, `*_INVOICE`, `*_ITEMS`, `*_CLCARD` (satış);
  `META.all_products` (ürün katalog). Her biri için **whitelist sütun listesi** koda gömülü.
- **Raw tablolar** (`raw` şeması), kaynak başına bir tablo, ingest sütun listesiyle birebir + `_ingested_at`,
  `_source_year`. Örn: `raw.stline`, `raw.invoice`, `raw.items`, `raw.clcard`, `raw.all_products`.
- **Incremental:** `app.ingest_state(source, last_watermark)` tutar (ör. INVOICE için `DATE_`/`LOGICALREF`).
  Günlük çalışmada watermark'tan büyük kayıtları çeker, raw'a upsert/append. Master tablolar
  (items/all_products/clcard) için tam-yenile (küçük) ya da değişiklik damgası.
- **Backfill:** `--from YYYY-MM-DD [--to ...] [--source ...]` ile tam yeniden çekim (watermark sıfırlama).
- **Çalıştırma:** Celery task `ingest_logo(sources, mode)`; Beat ile günlük; UI'dan manuel tetikleme.
  CLI eşdeğeri (`python -m ingest.run --incremental`) cron/elle çalıştırma için.

---

## 2) Jobs katmanı (raw → derived, editable Python)

Amaç: kullanıcının yazdığı Python ile raw'ı işleyip `derived` tablolar üretmek.

- **Job tanımı (DB'de):** `app.jobs(key, title, description, code, schedule, enabled, created_by, ...)`.
  Kod **editable** (Monaco). Versiyonlama: `app.job_versions(job_key, code, created_by, created_at)`.
- **Job kodu sözleşmesi:** Kullanıcı bir `run(ctx)` fonksiyonu yazar. `ctx` sağlar:
  - `ctx.read_sql(sql, params)` → pandas DataFrame (raw/derived okuma).
  - `ctx.write_table(name, df, mode="replace"|"append", key=[...])` → `derived.<job_key>__<name>` yazar/upsert.
  - `ctx.params`, `ctx.logger`, `ctx.run_id`. Pandas/numpy ve **tam Python** kullanılabilir.
- **Yürütme (güven temelli, tam Python):** Celery task `run_job(job_key, run_id)` worker'da çalışır.
  Sandbox YOK — tam Python. **Koruma:** yalnız admin/analyst düzenler (RBAC), her çalıştırma
  `app.job_runs(id, job_key, status, started/finished, rows_out, log, triggered_by)`'a yazılır (audit),
  versiyon geçmişi geri-alma sağlar, worker kaynak/zaman limiti (Celery `soft_time_limit`) uygular.
  Job yalnız kendi `derived.<job_key>__*` tablolarını yönetir (isim-uzayı izolasyonu; konvansiyon + kontrol).
- **Tetikleme:** (a) Beat ile `schedule` (cron ifadesi), (b) UI/endpoint'ten manuel "Çalıştır",
  (c) ingest bitince zincirleme (opsiyonel `depends_on`).
- **İlerleme/sonuç:** `job_runs` durumu + log; UI canlı gösterir (polling ya da SSE).

### Güvenlik notu (tam Python)
Job kodu worker içinde tam yetkiyle çalışır (dosya/ağ/os erişebilir). Bu kabul edilebilir çünkü:
dahili araç, yalnız güvenilir admin/analyst yazar, her değişiklik versiyonlanır, her çalıştırma audit'lenir.
Worker container'ı en az ayrıcalıkla, yalnız gereken ağ erişimiyle çalıştırılır; secret'lar env ile verilir.

---

## 3) Dashboard katmanı (derived → görselleştirme)

Amaç: derived tablolardan KPI/grafik/tablo üretmek. Job'dan **ayrı** katman; aynı derived'den çok dashboard.

- **Dashboard tanımı (DB'de):** `app.dashboards(key, title, description, code, ...)` + `dashboard_versions`.
- **Sözleşme:** `filter_schema()` (UI filtreleri) + `run(ctx)` → `{kpis, charts, table}` (MVP formatı korunur,
  böylece mevcut `Chart`/`DataTable`/`Filters` bileşenleri yeniden kullanılır). `ctx.read_sql` yalnız okuma
  (derived/raw). Görselleştirme **read-only** (yazmaz).
- Dashboard kodu da editable + versiyonlu. (İleride: derived üstüne semantik "görsel sorgu oluşturucu".)
- **Çıktı sözleşmesi:** `{kpis:[{key,label,value,format}], charts:[{type,title,x,series:[{name,data,type?,yAxisIndex?}]}],
  table:{columns:[{key,label,format}],rows:[]}}`. Excel export ortak.

---

## Auth & RBAC
- JWT (PyJWT) + passlib/bcrypt. Roller: `admin`, `analyst`, `viewer`.
- `admin`: her şey. `analyst`: job/dashboard yazar/düzenler/çalıştırır, ingest tetikler. `viewer`: dashboard görür.
- Kaynak-bazlı izin: `app.permissions(resource_type, resource_key, role, can_view, can_edit, can_run)`.
- Tüm tetikleme/çalıştırma uçları audit'lenir (kim, ne zaman).

## API yüzeyi (taslak, `/api`)
- `auth/login`, `auth/me`
- `ingest/sources` (liste/durum), `ingest/run` (POST, manuel tetikle), `ingest/state`
- `jobs` CRUD, `jobs/{key}/code` (get/put + versions), `jobs/{key}/run` (POST), `jobs/{key}/runs` (geçmiş/log)
- `dashboards` CRUD, `dashboards/{key}/code` (get/put + versions), `dashboards/{key}/run` (POST filters), `/export`
- `dashboards/{key}/meta` (filter_schema), `tables` (derived şema introspection — job/dashboard yazarken yardım)

## Repo yapısı (öneri)
```
platform/
  docker-compose.yml          # postgres, redis, backend, worker, beat, frontend
  ingest/                     # pytds Logo bağlantısı, kaynak tanımları (sütun whitelist), incremental+backfill
  app/ (backend)              # FastAPI: auth, RBAC, models, routers, celery app, ctx (read_sql/write_table)
    celery_app.py, tasks.py   # ingest_logo, run_job (worker tarafı)
  worker/                     # Celery worker entrypoint (app.tasks'i yükler) — backend imajını paylaşır
  frontend/                   # React+Vite+TS+Tailwind+ECharts+Monaco
  README.md
```
> `backend` ve `worker` aynı imajı paylaşabilir (farklı entrypoint): biri uvicorn, diğeri `celery worker`/`beat`.

## Frontend (UI)
- Sayfalar: **Ingest** (kaynaklar + durum + "Şimdi çek"), **Jobs** (liste, Monaco editör, çalıştır, run geçmişi/log),
  **Dashboards** (liste + görüntüleme + editör), **Login**. Nav rol-bazlı.
- Yeniden kullanılacak MVP bileşenleri: `Chart`, `DataTable`, `Filters`, `format.ts`, Monaco editör sarmalayıcı, auth context.

## Yol haritası (fazlar)
- **Faz 0 — İskelet:** compose (postgres+redis+backend+worker+beat+frontend), auth/RBAC, `app` şeması, sağlık uçları.
- **Faz 1 — Ingest:** pytds bağlantı, kaynak/sütun whitelist, raw şeması, incremental + backfill, Beat günlük + manuel tetikleme, `ingest_state`. Doğrulama: raw toplamları = ERP.
- **Faz 2 — Jobs:** job CRUD + Monaco editör + versiyonlama, `ctx` (read_sql/write_table), Celery `run_job`, `job_runs` audit/log, manuel + zamanlı tetikleme. Örnek job (raw satış → derived sezon/ürün özetleri).
- **Faz 3 — Dashboards:** dashboard CRUD + editör + versiyonlama, `run`→{kpis,charts,table}, filtreler, export, derived şema introspection. MVP'deki kurumsal panelleri derived üstünde yeniden üret.
- **Faz 4 — Sağlamlaştırma:** ilerleme/SSE, retry/zaman limitleri, izinler, izleme, README + örnek crontab/Beat, e2e doğrulama.

## Doğrulama (her faz)
- Ingest: raw kayıt sayısı/toplamları ERP'den bağımsız sorguyla birebir (mevcut `verify` deseni).
- Jobs: örnek job'ın derived çıktısı beklenen toplamlarla; run audit kaydı; versiyon geri-alma.
- Dashboards: çıktı sözleşmesi + bilinen toplamla çapraz kontrol; RBAC (viewer görür, yetkisiz 401/403).
- Tümü Docker compose ile ayağa kalkar; backend↔worker↔redis↔postgres bağlanır; frontend `/api` proxy çalışır.

## MVP'den taşınacak kanıtlanmış parçalar (referans: mevcut repo)
- **Logo bağlantı/SQL:** `etl/db.py` (`logo_conn`/`firm_code_for_year`), `etl/kurumsal_extract.py`,
  `satis_cek.py`/`rapor.py` (sütun anlamları, TRCODE, NetSale).
- **Editable Python + versiyonlama deseni:** `backend/app/reports/*`, `routers/reports.py` (code get/put + versions).
- **Auth/RBAC:** `backend/app/auth.py`, `models.py`, `seed.py`.
- **Frontend bileşenleri:** `frontend/src/components/{Chart,DataTable,Filters}.tsx`, `format.ts`,
  `pages/Editor.tsx` (Monaco), `auth.tsx`.
- **Docker:** `docker-compose.yml`, `backend/Dockerfile`+`entrypoint.sh`, `frontend/Dockerfile`+`nginx.conf`.

## Açık varsayımlar (gerekirse düzeltilecek)
- Temiz yeni yapı; mevcut repo'da `platform/` olarak ya da yeni repo (Claude Code'a bu doküman verilir).
- İlk ingest kapsamı satış zinciri + ürün katalog; yeni kaynaklar sütun-whitelist ekleyerek genişler.
- `backend` ve `worker` aynı imajı paylaşır (bakım kolaylığı).
