# Logo Tüneli — Windows kaynak makine

Ofisteki, Logo LAN'ına (`192.168.46.174`) erişimi olan **sürekli açık Windows makinesinde** kurulur.
Amaç: Windows'tan VPS'e giden reverse-SSH tüneli; yalnız `192.168.46.174:1433`'ü VPS docker
gateway'ine (`172.28.0.1:1433`) taşır. Ofis firewall'ında inbound port açılmaz (yalnız giden SSH).

> Windows'ta `autossh` yok. Yerine **built-in OpenSSH client + NSSM servisi** kullanıyoruz
> (NSSM süreç ölürse otomatik yeniden başlatır — autossh'in Windows karşılığı).

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

## Adım 4 — Kalıcı servis (NSSM)

```powershell
# NSSM indir: https://nssm.cc/download  -> nssm.exe'yi C:\logo-tunnel\ içine koy
cd C:\logo-tunnel
.\nssm.exe install LogoTunnel "C:\Windows\System32\OpenSSH\ssh.exe" `
  "-N -i C:\logo-tunnel\id_tunnel -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new -R 172.28.0.1:1433:192.168.46.174:1433 tunnel@VPS_PUBLIC_IP"

# Otomatik başlat + çökerse yeniden başlat (NSSM varsayılanı zaten restart)
.\nssm.exe set LogoTunnel Start SERVICE_AUTO_START
.\nssm.exe set LogoTunnel AppExit Default Restart
.\nssm.exe set LogoTunnel AppRestartDelay 10000
.\nssm.exe start LogoTunnel
```

Kontrol / yönetim:

```powershell
Get-Service LogoTunnel
.\nssm.exe status LogoTunnel
.\nssm.exe restart LogoTunnel
# Logları dosyaya almak istersen:
# .\nssm.exe set LogoTunnel AppStdout C:\logo-tunnel\out.log
# .\nssm.exe set LogoTunnel AppStderr C:\logo-tunnel\err.log
```

## NSSM istemiyorsan — Task Scheduler alternatifi

`C:\logo-tunnel\tunnel.ps1`:

```powershell
while ($true) {
  ssh -N -i C:\logo-tunnel\id_tunnel `
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 `
    -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new `
    -R 172.28.0.1:1433:192.168.46.174:1433 tunnel@VPS_PUBLIC_IP
  Start-Sleep -Seconds 10   # kopunca 10 sn sonra yeniden dene
}
```

Task Scheduler: "At startup" tetikleyici, "Run whether user is logged on or not",
komut: `powershell -ExecutionPolicy Bypass -File C:\logo-tunnel\tunnel.ps1`.

## Sorun giderme

| Belirti | Neden / çözüm |
|---|---|
| `Permissions for 'id_tunnel' are too open` | Adım 2 `icacls` çalıştırılmadı |
| `remote port forwarding failed for listen port 1433` | VPS'te `GatewayPorts clientspecified` yok, ya da 172.28.0.1 henüz yok (stack down) |
| `Connection refused` (ingest) | Servis durmuş: `nssm status LogoTunnel`; Logo makinesi/SQL ayakta mı |
| Bağlanıyor ama ingest 1433'e ulaşamıyor | Windows makinesi 192.168.46.174:1433'e erişebiliyor mu: `Test-NetConnection 192.168.46.174 -Port 1433` |
