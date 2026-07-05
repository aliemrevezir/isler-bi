# Logo Tüneli — Windows kaynak makine

Ofisteki, Logo LAN'ına (`192.168.46.174`) erişimi olan **sürekli açık Windows makinesinde** kurulur.
Amaç: Windows'tan VPS'e giden reverse-SSH tüneli; yalnız `192.168.46.174:1433`'ü VPS docker
gateway'ine (`172.28.0.1:1433`) taşır. Ofis firewall'ında inbound port açılmaz (yalnız giden SSH).

> Tünel **7/24 açık DEĞİL** — güvenlik için yalnız ihtiyaç halinde açılır. Ingest günde bir kez
> (beat, 06:00) çalıştığından, Task Scheduler tüneli 05:55'te açıp ~50 dk sonra otomatik kapatır.
> Ad-hoc ingest için task elle "Run" edilir.

## Ön koşullar (VPS tarafı — DEPLOY.md Adım 3 ile aynı)

- VPS sshd'de `GatewayPorts clientspecified` açık ve `sshd reload` edilmiş.
- VPS'te kısıtlı `tunnel` kullanıcısı; authorized_keys'e Windows public key'i **`restrict,port-forwarding`** ön ekiyle eklenmiş.
- Docker stack ayakta (yoksa `172.28.0.1` adresi host'ta oluşmaz, bind reddedilir).

## Adım 1 — OpenSSH client'ı doğrula

PowerShell (yönetici):

```powershell
ssh -V
# Yoksa: Settings > Apps > Optional Features > "OpenSSH Client" ekle, veya:
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

## Adım 2 — Anahtar üret

```powershell
mkdir C:\logo-tunnel 2>$null
ssh-keygen -t ed25519 -f C:\logo-tunnel\id_tunnel -N '""'
# Public key'i göster — içeriğini VPS'teki tunnel kullanıcısının authorized_keys'ine ekle:
type C:\logo-tunnel\id_tunnel.pub
```

VPS'te (satır başına `restrict,port-forwarding ` ekleyerek):

```
restrict,port-forwarding ssh-ed25519 AAAA...buraya... windows-logo-tunnel
```

Anahtar dosyasını yalnız SYSTEM okuyabilsin (NSSM servisi SYSTEM olarak koşacak; aksi halde
OpenSSH "bad permissions" der):

```powershell
icacls C:\logo-tunnel\id_tunnel /inheritance:r
icacls C:\logo-tunnel\id_tunnel /grant:r "SYSTEM:(R)" "Administrators:(R)"
```

## Adım 3 — Elle test (servis yapmadan önce)

Docker stack VPS'te ayaktayken:

```powershell
ssh -N -i C:\logo-tunnel\id_tunnel `
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 `
  -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new `
  -R 172.28.0.1:1433:192.168.46.174:1433 `
  tunnel@VPS_PUBLIC_IP
```

Başka bir pencerede, VPS'te doğrula:

```bash
docker exec isler_worker python -c "import socket; socket.create_connection(('172.28.0.1',1433),5); print('Logo OK')"
```

`Logo OK` görüyorsan tünel çalışıyor. Ctrl+C ile testi kapat, servise geç.

## Adım 4 — İhtiyaç halinde açılan tünel (Task Scheduler penceresi)

Tüneli sürekli açık tutmuyoruz. Task Scheduler günlük **05:55**'te açar, **ExecutionTimeLimit**
ile ~50 dk sonra otomatik kapatır (06:00 ingest'i kapsar). PowerShell (yönetici):

```powershell
$action  = New-ScheduledTaskAction -Execute "C:\Windows\System32\OpenSSH\ssh.exe" `
  -Argument '-N -i C:\logo-tunnel\id_tunnel -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new -R 172.28.0.1:1433:192.168.46.174:1433 tunnel@VPS_PUBLIC_IP'
$trigger  = New-ScheduledTaskTrigger -Daily -At 5:55AM
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 50) -StartWhenAvailable
Register-ScheduledTask -TaskName "LogoTunnel-Ingest" -Action $action -Trigger $trigger `
  -Settings $settings -User "SYSTEM" -RunLevel Highest
```

Notlar:
- `-User "SYSTEM"` çalışır çünkü Adım 2'deki `icacls` anahtarı SYSTEM'e okuma verdi.
- Windows yerel saati **Europe/Istanbul** olmalı (beat 06:00 Istanbul). Değilse trigger saatini kaydır.
- Ingest > 50 dk sürerse `ExecutionTimeLimit`'i artır.

### Ad-hoc (elle) ingest

```powershell
Start-ScheduledTask -TaskName "LogoTunnel-Ingest"   # tüneli hemen açar (50 dk pencere)
# ...UI'dan "Şimdi Çek" ya da VPS'te ingest çalıştır...
Stop-ScheduledTask  -TaskName "LogoTunnel-Ingest"   # işin bitince erken kapat (opsiyonel)
```

Durum/log: `Get-ScheduledTask LogoTunnel-Ingest | Get-ScheduledTaskInfo`

> Alternatif — tünelin 7/24 açık olmasını istersen NSSM ile servis yapılabilir
> (`nssm install LogoTunnel ssh.exe "..."`), ama bu proje bilinçli olarak pencere yaklaşımını seçti.

## Sorun giderme

| Belirti | Neden / çözüm |
|---|---|
| `Permissions for 'id_tunnel' are too open` | Adım 2 `icacls` çalıştırılmadı |
| `remote port forwarding failed for listen port 1433` | VPS'te `GatewayPorts clientspecified` yok, ya da 172.28.0.1 henüz yok (stack down) |
| `Connection refused` (ingest) | Servis durmuş: `nssm status LogoTunnel`; Logo makinesi/SQL ayakta mı |
| Bağlanıyor ama ingest 1433'e ulaşamıyor | Windows makinesi 192.168.46.174:1433'e erişebiliyor mu: `Test-NetConnection 192.168.46.174 -Port 1433` |
