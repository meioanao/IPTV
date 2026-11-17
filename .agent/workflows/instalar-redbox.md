---
description: Conecta na TV Box (Redbox) via ADB, detecta a arquitetura, baixa os APKs mais recentes do GitHub, instala todos os APKs da pasta apks/ em lote e configura o DNS privado Cloudflare.
---

# Workflow `/instalar-redbox`

Este workflow automatiza a configuração completa da TV Box Android (Redbox) via ADB na rede local.

## Passos Executados

1. **Verificar ADB**: Localiza o `adb.exe` instalado em `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe` (ou baixa o Android Platform Tools oficial caso necessário).
2. **Conectar à TV Box via ADB**:
   ```powershell
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" connect 192.168.15.19:5555
   ```
   *(Se o popup de autorização aparecer na TV, aguarda a confirmação do usuário).*
3. **Detectar Arquitetura da CPU**:
   ```powershell
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell getprop ro.product.cpu.abi
   ```
4. **Baixar APKs Atualizados do GitHub (`apks/`)**:
   - **Jellyfin para Android TV** (`jellyfin/jellyfin-androidtv` — `jellyfin-androidtv-v*-release.apk`)
   - **SmartTube** (`yuliskov/SmartTube` — `SmartTube_stable_*` correspondente à arquitetura da box)
   - **Proton VPN** (`ProtonVPN/android-app` — `ProtonVPN-*.apk`, ignorando versões `fdroid`)
   - **Projectivy Launcher** (`spocky/miproja1` — `ProjectivyLauncher-*.apk`)
5. **Instalar todos os APKs de `apks/` em lote**:
   - Instala tanto os APKs baixados do GitHub quanto os APKs locais de streaming colocados em `apks/` (Prime Video, Disney+, Paramount+, Netflix, etc.) usando `adb install -r`, registrando eventuais falhas sem interromper os demais.
6. **Configurar DNS Privado (`one.one.one.one`)**:
   ```powershell
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell settings put global private_dns_mode hostname
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell settings put global private_dns_specifier one.one.one.one
   ```

## Execução Rápida em Um Comando

// turbo
```powershell
python -u instalar_redbox.py 192.168.15.19:5555
```
