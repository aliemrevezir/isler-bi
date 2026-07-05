# CI/CD Kurulumu — push-to-deploy (GHCR + VPS pull)

Akış: `master`'a push → GitHub Actions backend+frontend imajlarını build edip **GHCR**'a push
eder → `deployer` kullanıcısına SSH ile bağlanıp VPS'te **pull + up** çalıştırır (prod'da build yok).

İki anahtar kullanıyoruz (bilinçli ayrım):
- **Anahtar A (Actions → VPS):** private'ı GitHub secret'ta, public'i `deployer` authorized_keys'te.
- **Anahtar B (VPS → GitHub, `git pull`):** private VPS'te kalır, public GitHub'da deploy key.

---

## 1) VPS: `deployer` kullanıcısı

```bash
sudo useradd -m -s /bin/bash deployer
sudo usermod -aG docker deployer                 # docker çalıştırma yetkisi
sudo chown -R deployer:deployer /opt/isler-bi    # git pull + compose için sahiplik
sudo mkdir -p /home/deployer/.ssh && sudo chmod 700 /home/deployer/.ssh
sudo chown deployer:deployer /home/deployer/.ssh

# .env.prod'u deployer okuyabilsin (secret; 600 + deployer sahipliği)
sudo chown deployer:deployer /opt/isler-bi/.env.prod && sudo chmod 600 /opt/isler-bi/.env.prod
```

## 2) Anahtar A — Actions → VPS SSH

```bash
# VPS'te üret (parolasız)
sudo -u deployer ssh-keygen -t ed25519 -f /home/deployer/.ssh/id_ci -N ""
# public'i deployer'ın authorized_keys'ine ekle (Actions bununla girecek)
sudo -u deployer bash -c 'cat /home/deployer/.ssh/id_ci.pub >> /home/deployer/.ssh/authorized_keys && chmod 600 /home/deployer/.ssh/authorized_keys'
# PRIVATE anahtarı göster → GitHub secret VPS_SSH_KEY'e yapıştır (aşağıda)
sudo cat /home/deployer/.ssh/id_ci
```

## 3) Anahtar B — VPS → GitHub (`git pull`)

```bash
sudo -u deployer ssh-keygen -t ed25519 -f /home/deployer/.ssh/id_repo -N ""
# git bu repo için id_repo kullansın
sudo -u deployer tee /home/deployer/.ssh/config >/dev/null <<'EOF'
Host github.com
  IdentityFile ~/.ssh/id_repo
  IdentitiesOnly yes
EOF
sudo chmod 600 /home/deployer/.ssh/config
sudo chown deployer:deployer /home/deployer/.ssh/config
# public'i göster → GitHub repo Deploy key olarak ekle (read-only)
sudo cat /home/deployer/.ssh/id_repo.pub
```

GitHub'da: **repo → Settings → Deploy keys → Add deploy key** → `id_repo.pub` yapıştır,
"Allow write access" **işaretsiz**.

Doğrula:

```bash
sudo -u deployer bash -lc 'cd /opt/isler-bi && git pull --ff-only'
```

## 4) GHCR login — VPS özel imajları çekebilsin

GHCR imajları private. `deployer` bir kez login olmalı (creds `~/.docker/config.json`'da kalır).

1. GitHub → **Settings → Developer settings → Personal access tokens → Tokens (classic)** →
   yeni token, **`read:packages`** yetkisi. (Fine-grained token'da: Packages → Read.)
2. VPS'te:

```bash
sudo -u deployer bash -lc 'echo GHCR_PAT_BURAYA | docker login ghcr.io -u aliemrevezir --password-stdin'
```

## 5) GitHub repo secrets

**repo → Settings → Secrets and variables → Actions → New repository secret:**

| Secret | Değer |
|---|---|
| `VPS_HOST` | VPS public IP (ör. `1.2.3.4`) |
| `VPS_USER` | `deployer` |
| `VPS_SSH_KEY` | Adım 2'deki **id_ci private** anahtarın tamamı (`-----BEGIN...END-----`) |

> GHCR'a **push** için ekstra secret yok — workflow yerleşik `GITHUB_TOKEN` kullanır.

## 6) İlk çalıştırma

`.github/workflows/deploy.yml` repo'da olduğundan, `master`'a bir sonraki push otomatik tetikler.
Elle de tetikleyebilirsin: **Actions → build & deploy → Run workflow**.

İlk run: imajları GHCR'a basar, sonra VPS'te pull+up yapar. Akış:
`Actions sekmesi`nde yeşil ✓ → `https://rapor.veriz.co` yeni sürümle güncel.

---

## Notlar / sorun giderme

- **İlk deploy'dan önce** stack elle local-build ile ayaktaydı; ilk CI run GHCR imajlarına geçirir.
  `up -d` container'ları GHCR imajlarıyla yeniden yaratır (kısa kesinti).
- **Rollback:** compose imaj tag'ini `:latest` yerine bir commit SHA'ya sabitleyip `up -d`, ya da
  önceki commit'i `master`'a push/revert et.
- **Actions deploy adımı SSH'ta takılırsa:** VPS firewall'da 22 açık mı, `VPS_HOST`/anahtar doğru mu.
- **`pull` "denied":** deployer GHCR login olmamış (Adım 4) ya da PAT'ta `read:packages` yok.
- **`git pull` "Permission denied (publickey)":** Adım 3 deploy key eksik/yanlış.
- Compose değişmediği sürece deploy sadece imaj çeker; Caddyfile'a dokunulmaz.
```
