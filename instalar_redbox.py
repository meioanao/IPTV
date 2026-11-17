#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de configuração completa da TV Box Android (Redbox) via ADB:
1. Localiza ou baixa o Android Platform Tools (adb).
2. Conecta na Redbox via ADB e aguarda autorização na tela da TV.
3. Verifica a arquitetura do processador (ro.product.cpu.abi).
4. Baixa as releases mais recentes do GitHub na pasta apks/:
   - Jellyfin Android TV
   - SmartTube (compatível com a arquitetura detectada)
   - Proton VPN (versão oficial direct-release, sem fdroid)
   - Projectivy Launcher (release oficial spocky/miproja1)
5. Instala em lote todos os arquivos .apk da pasta apks/ via 'adb install -r'.
6. Configura o DNS privado (one.one.one.one) via ADB.
"""

import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from typing import List, Optional, Tuple

import requests

DEFAULT_IPS = ["192.168.15.19:5555", "192.168.1.50:5555"]
APKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apks")
PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"


def find_or_install_adb() -> str:
    """Verifica se o adb está instalado; caso contrário, baixa o Android Platform Tools oficial."""
    adb_in_path = shutil.which("adb")
    if adb_in_path:
        print(f"[+] ADB encontrado no PATH: {adb_in_path}")
        return adb_in_path

    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "platform-tools", "adb.exe"),
        r"C:\platform-tools\adb.exe",
    ]
    for path in candidates:
        if os.path.isfile(path):
            print(f"[+] ADB encontrado em: {path}")
            return path

    print("[*] ADB não encontrado. Baixando Android Platform Tools oficial...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    zip_path = os.path.join(base_dir, "platform-tools.zip")
    urllib.request.urlretrieve(PLATFORM_TOOLS_URL, zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(base_dir)
    os.remove(zip_path)

    adb_extracted = os.path.join(base_dir, "platform-tools", "adb.exe")
    print(f"[+] Android Platform Tools instalado em: {adb_extracted}")
    return adb_extracted


def run_adb(adb_path: str, args: List[str], timeout: int = 120) -> Tuple[int, str]:
    """Executa um comando ADB e retorna (returncode, output)."""
    cmd = [adb_path] + args
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return 1, "Timeout ao executar comando ADB."


def connect_redbox(adb_path: str, target_ips: List[str]) -> Optional[str]:
    """Verifica primeiro se a Redbox já está conectada via USB; se não, tenta conectar via IP."""
    run_adb(adb_path, ["start-server"], timeout=15)

    # 1. Verifica dispositivos já conectados (USB ou TCP)
    _, devices_out = run_adb(adb_path, ["devices"], timeout=10)
    for line in devices_out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            dev_id = parts[0]
            print(f"[+] Dispositivo Android detectado e autorizado: {dev_id}")
            return dev_id

    for target in target_ips:
        print(f"\n[*] Tentando conectar na Redbox em {target}...")
        _, out = run_adb(adb_path, ["connect", target], timeout=15)
        print(f"    Saída: {out}")

        if "connected to" in out.lower() or "already connected" in out.lower():
            # Verifica se precisa aceitar popup de autorização na TV
            for attempt in range(15):
                _, devices_out = run_adb(adb_path, ["devices"], timeout=10)
                for line in devices_out.splitlines():
                    if target in line:
                        if "\tdevice" in line:
                            print(f"[+] Conectado e autorizado com sucesso em {target}!")
                            return target
                        elif "\tunauthorized" in line:
                            print(
                                f"    [!] Aguardando você aceitar o popup 'Permitir depuração USB/ADB' na tela da TV ({attempt + 1}/15)..."
                            )
                time.sleep(2)
            # Mesmo se não confirmou imediatamente, retorna se conectou
            _, state_out = run_adb(adb_path, ["-s", target, "get-state"], timeout=10)
            if "device" in state_out:
                return target

    return None


def get_device_abi(adb_path: str, device_id: Optional[str]) -> str:
    """Obtém a arquitetura do processador da TV Box via ADB."""
    if not device_id:
        print("[!] TV Box desconectada no momento. Usando arquitetura padrão 'armeabi-v7a' para download inicial.")
        return "armeabi-v7a"

    _, abi = run_adb(adb_path, ["-s", device_id, "shell", "getprop", "ro.product.cpu.abi"], timeout=10)
    abi = abi.strip()
    if abi in ("armeabi-v7a", "arm64-v8a", "x86", "x86_64"):
        print(f"[+] Arquitetura detectada da Redbox: {abi}")
        return abi

    print(f"[!] Não foi possível ler ABI exata ('{abi}'). Usando 'armeabi-v7a'.")
    return "armeabi-v7a"


def download_file(url: str, dest_path: str) -> bool:
    """Baixa um arquivo exibindo o progresso."""
    filename = os.path.basename(dest_path)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 100_000:
        print(f"    [=] Já existe em apks/: {filename} ({os.path.getsize(dest_path) / (1024*1024):.1f} MB)")
        return True

    print(f"    [*] Baixando {filename}...")
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
        size_mb = downloaded / (1024 * 1024)
        print(f"    [+] Concluído: {filename} ({size_mb:.1f} MB)")
        return True
    except Exception as exc:
        print(f"    [!] Erro ao baixar {filename}: {exc}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


def download_github_apks(abi: str) -> List[str]:
    """Consulta as releases mais recentes do GitHub e baixa os APKs compatíveis."""
    os.makedirs(APKS_DIR, exist_ok=True)
    downloaded_files: List[str] = []
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Redbox-Installer"}

    # 1. Jellyfin para Android TV
    print("\n[1/4] Buscando última release do Jellyfin Android TV (jellyfin/jellyfin-androidtv)...")
    try:
        r = requests.get("https://api.github.com/repos/jellyfin/jellyfin-androidtv/releases/latest", headers=headers, timeout=15)
        r.raise_for_status()
        for asset in r.json().get("assets", []):
            name = asset["name"]
            if name.startswith("jellyfin-androidtv-v") and name.endswith("-release.apk"):
                dest = os.path.join(APKS_DIR, name)
                if download_file(asset["browser_download_url"], dest):
                    downloaded_files.append(dest)
                break
    except Exception as e:
        print(f"    [!] Falha ao consultar Jellyfin: {e}")

    # 2. SmartTube (compatível com a arquitetura detectada)
    print(f"\n[2/4] Buscando última release do SmartTube (yuliskov/SmartTube) para arquitetura '{abi}'...")
    try:
        r = requests.get("https://api.github.com/repos/yuliskov/SmartTube/releases/latest", headers=headers, timeout=15)
        r.raise_for_status()
        assets = r.json().get("assets", [])
        matched_asset = None
        for asset in assets:
            name = asset["name"]
            if name.startswith("SmartTube_stable_") and abi in name and name.endswith(".apk"):
                matched_asset = asset
                break
        if not matched_asset:
            for asset in assets:
                if asset["name"].startswith("SmartTube_stable_") and "universal" in asset["name"]:
                    matched_asset = asset
                    break
        if matched_asset:
            dest = os.path.join(APKS_DIR, matched_asset["name"])
            if download_file(matched_asset["browser_download_url"], dest):
                downloaded_files.append(dest)
    except Exception as e:
        print(f"    [!] Falha ao consultar SmartTube: {e}")

    # 3. Proton VPN (ignorando versões fdroid)
    print("\n[3/4] Buscando última release do Proton VPN (ProtonVPN/android-app)...")
    try:
        r = requests.get("https://api.github.com/repos/ProtonVPN/android-app/releases/latest", headers=headers, timeout=15)
        r.raise_for_status()
        for asset in r.json().get("assets", []):
            name = asset["name"]
            if name.startswith("ProtonVPN-") and name.endswith(".apk") and "fdroid" not in name.lower():
                dest = os.path.join(APKS_DIR, name)
                if download_file(asset["browser_download_url"], dest):
                    downloaded_files.append(dest)
                break
    except Exception as e:
        print(f"    [!] Falha ao consultar Proton VPN: {e}")

    # 4. Projectivy Launcher (repositório oficial spocky/miproja1)
    print("\n[4/4] Buscando última release do Projectivy Launcher (spocky/miproja1)...")
    try:
        r = requests.get("https://api.github.com/repos/spocky/miproja1/releases/latest", headers=headers, timeout=15)
        r.raise_for_status()
        for asset in r.json().get("assets", []):
            name = asset["name"]
            if name.endswith(".apk"):
                dest = os.path.join(APKS_DIR, name)
                if download_file(asset["browser_download_url"], dest):
                    downloaded_files.append(dest)
                break
    except Exception as e:
        print(f"    [!] Falha ao consultar Projectivy Launcher: {e}")

    # 5. Apps de Streaming compatíveis com Android 7.0 (Netflix, Prime Video, ProtonVPN SDK24)
    streaming_apks = [
        ("Netflix-7.120.6.apk", "https://pool.apk.aptoide.com/appupdater/com-netflix-mediaclient-35594-71690417-83dd84133ac2c812c611557c8993a298.apk"),
        ("PrimeVideo-AndroidTV.apk", "https://pool.apk.aptoide.com/ganesapps/com-amazon-amazonvideo-livingroom-999999999-66813648-f601df5de003b7054e6cfa85df84bac3.apk"),
        ("ProtonVPN-4.9.40.23-SDK24.apk", "https://github.com/ProtonVPN/android-app/releases/download/4.9.40.23/ProtonVPN-4.9.40.23.apk"),
    ]
    print("\n[*] Verificando APKs adicionais (Netflix, Prime Video, ProtonVPN SDK24)...")
    for filename, url in streaming_apks:
        dest = os.path.join(APKS_DIR, filename)
        if download_file(url, dest):
            downloaded_files.append(dest)

    return downloaded_files


def install_all_apks(adb_path: str, device_id: str, abi: str) -> None:
    """Instala em lote todos os APKs presentes na pasta apks/."""
    apk_files = sorted(
        [
            os.path.join(APKS_DIR, f)
            for f in os.listdir(APKS_DIR)
            if f.lower().endswith(".apk")
        ]
    )

    if not apk_files:
        print("[!] Nenhum arquivo .apk encontrado na pasta apks/.")
        return

    print(f"\n[*] Iniciando instalação em lote de {len(apk_files)} APK(s) na Redbox ({device_id})...")
    successes: List[str] = []
    failures: List[Tuple[str, str]] = []

    for apk_path in apk_files:
        apk_name = os.path.basename(apk_path)
        # Se houver APKs do SmartTube de outra arquitetura na pasta, ignora o incompatível
        if apk_name.startswith("SmartTube_stable_"):
            if abi == "armeabi-v7a" and "arm64-v8a" in apk_name:
                continue
            if abi == "arm64-v8a" and "armeabi-v7a" in apk_name:
                continue

        print(f"  -> Instalando {apk_name}...")
        code, out = run_adb(adb_path, ["-s", device_id, "install", "-r", apk_path], timeout=180)
        if code == 0 and "success" in out.lower():
            print(f"     [+] Sucesso: {apk_name}")
            successes.append(apk_name)
        else:
            reason = out.splitlines()[-1] if out else "Erro desconhecido"
            print(f"     [!] FALHOU: {apk_name} -> {reason}")
            failures.append((apk_name, reason))

    print("\n" + "=" * 60)
    print(f" RESUMO DA INSTALAÇÃO ({len(successes)} instalados, {len(failures)} falharam)")
    print("=" * 60)
    for s in successes:
        print(f"  [OK] {s}")
    for f_name, f_reason in failures:
        print(f"  [ERRO] {f_name}: {f_reason}")


def configure_private_dns(adb_path: str, device_id: str) -> None:
    """Configura o DNS privado da Redbox para one.one.one.one via ADB."""
    print(f"\n[*] Configurando DNS Privado (one.one.one.one) na Redbox ({device_id})...")
    c1, o1 = run_adb(adb_path, ["-s", device_id, "shell", "settings", "put", "global", "private_dns_mode", "hostname"])
    c2, o2 = run_adb(adb_path, ["-s", device_id, "shell", "settings", "put", "global", "private_dns_specifier", "one.one.one.one"])
    _, mode = run_adb(adb_path, ["-s", device_id, "shell", "settings", "get", "global", "private_dns_mode"])
    _, spec = run_adb(adb_path, ["-s", device_id, "shell", "settings", "get", "global", "private_dns_specifier"])

    if c1 == 0 and c2 == 0:
        print(f"[+] DNS Privado configurado com sucesso! (mode={mode}, specifier={spec})")
    else:
        print(f"[!] Aviso ao configurar DNS Privado: {o1} {o2}")


def debloat_and_set_launcher(adb_path: str, device_id: str) -> None:
    """Desativa apps promocionais/launchers antigos e define o FLauncher como Home padrão (100% opaco e sem ghosting na GPU Mali-400)."""
    print(f"\n[*] Definindo FLauncher como tela inicial (Home) padrão...")
    run_adb(adb_path, ["-s", device_id, "shell", "cmd", "package", "set-home-activity", "me.efesser.flauncher/.MainActivity"])
    run_adb(adb_path, ["-s", device_id, "shell", "settings", "put", "secure", "enabled_accessibility_services", "null"])
    run_adb(adb_path, ["-s", device_id, "shell", "settings", "put", "secure", "accessibility_enabled", "0"])

    bloatware_packages = [
        "com.uv.droid.launcher.mxqlauncher",
        "com.oranth.tvlaunchek",
        "com.mm.droid.livetv.redplaybox",
        "com.mm.droid.livetv.tve",
        "com.dd.kk.live",
        "com.hd.sport.live",
        "com.simple.appstore.flymarket",
        "com.system.clean.tool",
        "com.android.icore",
        "com.android.osext",
        "com.android.shext",
        "com.uv.droid.uota",
        "com.uv.droid.uotaback",
    ]
    print("[*] Executando debloat seguro (desativando launchers antigos e apps promocionais)...")
    for pkg in bloatware_packages:
        run_adb(adb_path, ["-s", device_id, "shell", "am", "force-stop", pkg])
        _, out = run_adb(adb_path, ["-s", device_id, "shell", "pm", "disable-user", "--user", "0", pkg])
        print(f"    - {pkg}: {out}")

    run_adb(adb_path, ["-s", device_id, "shell", "am", "start", "-n", "me.efesser.flauncher/.MainActivity"])
    run_adb(adb_path, ["-s", device_id, "shell", "input", "keyevent", "KEYCODE_HOME"])


def main() -> int:
    print("=" * 65)
    print(" CONFIGURADOR AUTOMÁTICO DE TV BOX ANDROID (REDBOX) VIA ADB")
    print("=" * 65)

    # 1. Verificar/instalar ADB
    adb_path = find_or_install_adb()

    # 2. Definir IPs alvo (permite passar IP por argumento de linha de comando)
    target_ips = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_IPS
    normalized_ips = [ip if ":" in ip else f"{ip}:5555" for ip in target_ips]

    # 3. Tentar conectar na Redbox
    device_id = connect_redbox(adb_path, normalized_ips)

    # 4. Detectar arquitetura (ABI)
    abi = get_device_abi(adb_path, device_id)

    # 5. Baixar APKs oficiais do GitHub
    download_github_apks(abi)

    # Se não conectou antes, não consegue instalar ainda
    if not device_id:
        print("\n" + "!" * 65)
        print(" [ATENÇÃO] Os APKs do GitHub já foram baixados na pasta 'apks/',")
        print(" porém a Redbox recusou a conexão ADB (porta 5555 fechada ou IP offline).")
        print(" Verifique na TV Box se a 'Depuração USB / Depuração por Rede' está")
        print(" ativada nas Opções do Desenvolvedor e rode novamente:")
        print("   python instalar_redbox.py 192.168.15.19")
        print("!" * 65)
        return 2

    # 6. Instalar todos os APKs da pasta apks/ em lote
    install_all_apks(adb_path, device_id, abi)

    # 7. Configurar DNS privado (one.one.one.one)
    configure_private_dns(adb_path, device_id)

    # 8. Debloat seguro e definição do Projectivy Launcher como Home padrão
    debloat_and_set_launcher(adb_path, device_id)

    print("\n[+] Processo concluído!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
