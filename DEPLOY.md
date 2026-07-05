# Canlıya Alma (Production Deployment) — DATA-449

İşler Veri Platformu'nu İşler Teknoloji VPS'ine (Şube Sipariş app ile aynı sunucu) taşıma
runbook'u. İhsan `https://rapor.veriz.co` üzerinden mağaza & yayınevi raporlarına erişir.

## Mimari kararı (Mert'e bildirilecek özet)

- **Topoloji A:** Tüm platform yığını (postgres, redis, backend, worker, beat, frontend) tek VPS'te,
  Şube Sipariş app'in yanında. Ayrı Postgres/Redis (izolasyon).
- **TLS/URL:** Kendi reverse proxy'miz **yok**. VPS'te zaten çalışan `sube-siparis-web` (Caddy)
  80/443'ü yönetiyor ve otomatik HTTPS yapıyor. `rapor.veriz.co`'yu ona bir site bloğu olarak
  ekliyoruz; `query.veriz.co` (POMS) ile aynı desen. Şube Sipariş compose'una dokunulmaz.
- **Logo erişimi:** VPS özel LAN'daki Logo MSSQL'e (`192.168.46.174`) doğrudan erişemez. Ofisteki
  **Windows** makinesinden VPS'e reverse-SSH tüneli (NSSM servisi) açılır; yalnız `Logo:1433`'ü VPS
  docker gateway'ine (`172.28.0.1:1433`) taşır. Ofis firewall'ında inbound port açılmaz.
  Bkz. [deploy/logo-tunnel-windows.md](deploy/logo-tunnel-windows.md).
- **Güvenlik:** Logo'ya read-only `isler_ro` kullanıcısı ile bağlanılır (yalnız `LOGO`/`META`).

```
İhsan ─https─> sube-siparis Caddy(:443) ──rapor.veriz.co──> isler_frontend(nginx) ─/api─> isler_backend ─> isler_pg
                     (mevcut, dokunulmaz)                              isler_worker/beat ─┐
Windows(ofis) ─reverse-SSH(NSSM)─> VPS:172.28.0.1:1433 <──────────────────────────────────┘ (günlük ingest)
        └── forward ── 192.168.46.174:1433 (Logo MSSQL, isler_ro)
```

## Durum / ön koşullar

- [x] DNS: `rapor.veriz.co` A kaydı → VPS public IP. **(yapıldı)**
- [x] Logo read-only kullanıcı `isler_ro` (LOGO+META db_datareader). **(yapıldı, test OK)**
- [x] VPS'te Docker + Compose v2. **(var)**
- [x] 80/443 mevcut Caddy'de; çakışma yok, entegre edilecek. **(doğrulandı)**
- [ ] Ofiste sürekli açık Windows makinesi (Logo LAN erişimli) — tünel için.

---

## Adım 1 — Kodu commit'le ve VPS'e al

Çalışma ağacında commit'lenmemiş mağaza/yayınevi işi + deploy dosyaları var:

```bash
# yerelde (Mac)
git add -A          # *.xlsx artık .gitignore'da; 21MB'lık dosya girmez
git commit -m "DATA-449: mağaza & yayınevi raporları + prod deployment"
git push
```

VPS'te (Şube Sipariş'ten AYRI dizin):

```bash
git clone <repo-url> /opt/isler-bi && cd /opt/isler-bi
# veya mevcutsa: cd /opt/isler-bi && git pull
```

## Adım 2 — Prod ortam dosyası

```bash
cp .env.prod.example .env.prod
nano .env.prod
#   PG_PASSWORD     -> openssl rand -base64 24
#   APP_JWT_SECRET  -> openssl rand -hex 32
#   LOGO_USER=isler_ro   LOGO_PASSWORD=<DBeaver'da girdiğin şifre>
#   LOGO_SERVER=172.28.0.1  (tünel hedefi — DEĞİŞTİRME)
#   FRONTEND_PORT=8091 (8080 POMS'ta dolu)
```

## Adım 3 — VPS sshd: tünelin docker gateway'e bağlanmasına izin ver

Reverse tünel `172.28.0.1:1433`'e bind edecek; bu `GatewayPorts` gerektirir.

```bash
grep -q '^GatewayPorts' /etc/ssh/sshd_config || echo 'GatewayPorts clientspecified' | sudo tee -a /etc/ssh/sshd_config
sudo sshd -t && sudo systemctl reload ssh    # config testi + reload (mevcut oturum kopmaz)
```

Kısıtlı `tunnel` kullanıcısı (yalnız port yönlendirme):

```bash
sudo useradd -m -s /usr/sbin/nologin tunnel
sudo mkdir -p /home/tunnel/.ssh && sudo chmod 700 /home/tunnel/.ssh
# Windows'ta üretilen id_tunnel.pub içeriğini, başına 'restrict,port-forwarding ' ekleyerek yapıştır:
sudo nano /home/tunnel/.ssh/authorized_keys
sudo chmod 600 /home/tunnel/.ssh/authorized_keys
sudo chown -R tunnel:tunnel /home/tunnel/.ssh
```

## Adım 4 — Platform yığınını ayağa kaldır

```bash
cd /opt/isler-bi
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

> `-f` ile dosyalar açıkça sayıldığından dev `docker-compose.override.yml` YÜKLENMEZ
> → prod nginx + reload'suz uvicorn. Kontrol:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker network inspect isler-bi_default | grep Gateway     # 172.28.0.1 görmeli
docker inspect isler_frontend --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
#   -> "isler-bi_default sube-siparis_default" (ikisi de olmalı)
```

## Adım 5 — Caddy'ye rapor.veriz.co bloğunu ekle

`deploy/rapor-caddy-block.txt` içeriğini mevcut Caddyfile'ın sonuna ekle ve reload et:

```bash
cat /opt/isler-bi/deploy/rapor-caddy-block.txt >> /root/sube-siparis/frontend/Caddyfile
docker exec sube-siparis-web-1 caddy reload --config /etc/caddy/Caddyfile   # sıfır kesinti
```

Birkaç saniye sonra `https://rapor.veriz.co` TLS ile açılmalı (Caddy otomatik sertifika alır).
Sertifika/log kontrol: `docker logs -f sube-siparis-web-1`

## Adım 6 — Logo tüneli (Windows ofis makinesi)

[deploy/logo-tunnel-windows.md](deploy/logo-tunnel-windows.md) adımlarını izle: OpenSSH client,
anahtar üret, public key'i Adım 3'teki `tunnel` kullanıcısına ekle, NSSM servisi kur.

Doğrulama (VPS'te, stack ayakta + tünel kurulu):

```bash
docker exec isler_worker python -c "import socket; socket.create_connection(('172.28.0.1',1433),5); print('Logo OK')"
```

## Adım 7 — İlk veri yüklemesi

UI'dan (`admin` ile giriş `https://rapor.veriz.co`): **Ingest → Şimdi Çek** →
**Jobs → Çalıştır** → **Dashboards** dolar. Alternatif ilk backfill:

```bash
docker exec isler_worker python -m app.ingest.run --backfill --from 2023-01-01
```

---

## Deploy sonrası SERTLEŞTİRME (atlanmamalı)

- [ ] **Demo şifrelerini değiştir.** Seed `admin/admin123`, `analist/analist123`, `viewer/viewer123`
      basıyor. İlk girişte admin şifresini değiştir; kullanılmayanı pasifleştir.
- [ ] İhsan için ayrı kullanıcı (uygun rol) aç; `rapor.veriz.co` + kullanıcı/şifre paylaş.
- [ ] Postgres yedeği (cron): `docker exec isler_pg pg_dump -U isler isler | gzip > /backup/isler_$(date +\%F).sql.gz`
- [ ] Platform portları zaten `127.0.0.1`'e bind; VPS firewall'da 5432/6379/8000/8091 dışarı kapalı olsun.

## Güncelleme

```bash
cd /opt/isler-bi && git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build
# Caddyfile değişmediyse Caddy'ye dokunma.
```

## Sorun giderme

| Belirti | Neden / çözüm |
|---|---|
| `rapor.veriz.co` açılmıyor / TLS yok | Caddy reload edilmedi; `docker logs sube-siparis-web-1`; DNS yayıldı mı |
| 502 (rapor) | isler_frontend `sube-siparis_default` ağında değil (Adım 4 kontrolü) |
| Dashboard boş | ingest/job çalışmadı → Adım 7 |
| Ingest "connection refused" | Tünel down (Windows NSSM), ya da `GatewayPorts clientspecified` eksik/sshd reload edilmedi |
| `remote port forwarding failed` (Windows) | `172.28.0.1` yok (stack down) veya GatewayPorts kapalı |
