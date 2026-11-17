#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unificador e Verificador de Listas M3U de IPTV.
Baixa múltiplas listas públicas, remove duplicados, padroniza categorias (group-title),
testa a disponibilidade dos links em paralelo e gera docs/lista_unificada.m3u e docs/index.html.
"""

import concurrent.futures
import datetime
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple

import requests
import urllib3

# Desabilita avisos de SSL para servidores de stream com certificados autoassinados
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PLAYLIST_SOURCES = [
    {
        "name": "Canais abertos Brasil",
        "url": "https://github.com/iptv-com/iptv/raw/refs/heads/main/lists/brazil.m3u",
        "default_category": "Brasil Abertos",
        "origin": "BR",
    },
    {
        "name": "Canais Brasil (iptv-org)",
        "url": "https://iptv-org.github.io/iptv/countries/br.m3u",
        "default_category": "Brasil Abertos",
        "origin": "BR",
    },
    {
        "name": "Canais em Português",
        "url": "https://iptv-org.github.io/iptv/languages/por.m3u",
        "default_category": "Brasil Abertos",
        "origin": "BR",
    },
    {
        "name": "Filmes e Séries 24h Brasil (Pluto TV)",
        "url": "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/plutotv_br.m3u",
        "default_category": "Filmes e Séries BR",
        "origin": "BR_MOVIES",
    },
    {
        "name": "Esportes",
        "url": "https://iptv-org.github.io/iptv/categories/sports.m3u",
        "default_category": "Esportes",
        "origin": "SPORTS",
    },
    {
        "name": "Canais abertos EUA",
        "url": "https://iptv-org.github.io/iptv/countries/us.m3u",
        "default_category": "EUA Abertos",
        "origin": "US",
    },
    {
        "name": "Filmes e Séries 24h EUA (Pluto TV)",
        "url": "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/plutotv_us.m3u",
        "default_category": "Filmes e Séries EUA",
        "origin": "US_MOVIES",
    },
]

CATEGORY_ORDER = [
    "Brasil Abertos",
    "Filmes e Séries BR",
    "Esportes",
    "EUA Abertos",
    "Filmes e Séries EUA",
]

REQUEST_TIMEOUT = 5
MAX_WORKERS = 80
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VLC/3.0.20 LibVLC/3.0.20"

GROUP_TITLE_REGEX = re.compile(r'group-title="([^"]*)"', re.IGNORECASE)


def determine_category(extinf_line: str, default_category: str, origin: str) -> str:
    """
    Determina a categoria limpa em português dentro das 5 categorias oficiais:
    "Brasil Abertos", "Filmes e Séries BR", "Esportes", "EUA Abertos" e "Filmes e Séries EUA".
    """
    if origin in ("BR_MOVIES", "US_MOVIES", "SPORTS"):
        return default_category

    match = GROUP_TITLE_REGEX.search(extinf_line)
    raw_group = match.group(1).lower() if match else ""

    if any(k in raw_group for k in ("sport", "esporte", "futebol", "soccer")):
        return "Esportes"

    if any(k in raw_group for k in ("movie", "series", "filme", "série", "cinema", "classic")):
        if origin == "BR":
            return "Filmes e Séries BR"
        if origin == "US":
            return "Filmes e Séries EUA"

    return default_category


def normalize_extinf(extinf_line: str, category: str) -> Tuple[str, str]:
    """
    Atualiza ou adiciona o atributo group-title na linha #EXTINF e retorna
    (linha_extinf_atualizada, nome_do_canal).
    """
    line = extinf_line.strip()
    if GROUP_TITLE_REGEX.search(line):
        line = GROUP_TITLE_REGEX.sub(f'group-title="{category}"', line)
    else:
        # Insere group-title antes da vírgula que separa os atributos do nome do canal
        if "," in line:
            parts = line.split(",", 1)
            line = f'{parts[0]} group-title="{category}",{parts[1]}'
        else:
            line = f'{line} group-title="{category}"'

    channel_name = line.split(",", 1)[1].strip() if "," in line else "Canal Sem Nome"
    return line, channel_name


def fetch_playlist(source: Dict[str, str]) -> List[Dict[str, str]]:
    """Baixa uma lista M3U e extrai seus canais."""
    name = source["name"]
    url = source["url"]
    default_cat = source["default_category"]
    origin = source["origin"]

    print(f"[*] Baixando lista: {name} ({url})...")
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"    [!] Erro ao baixar {name}: {exc}")
        return []

    channels: List[Dict[str, str]] = []
    current_extinf: Optional[str] = None
    extra_directives: List[str] = []

    for raw_line in resp.text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF"):
            current_extinf = line
            extra_directives = []
        elif line.startswith("#"):
            if current_extinf is not None and not line.startswith("#EXTM3U"):
                extra_directives.append(line)
        elif line.startswith("http://") or line.startswith("https://"):
            if current_extinf:
                category = determine_category(current_extinf, default_cat, origin)
                updated_extinf, channel_name = normalize_extinf(current_extinf, category)
                channels.append(
                    {
                        "name": channel_name,
                        "category": category,
                        "extinf": updated_extinf,
                        "extras": "\n".join(extra_directives),
                        "url": line,
                    }
                )
            current_extinf = None
            extra_directives = []

    print(f"    [+] {len(channels)} canais encontrados em '{name}'.")
    return channels


def check_stream_url(channel: Dict[str, str], session: requests.Session) -> Optional[Dict[str, str]]:
    """
    Testa a disponibilidade do link do stream com HTTP HEAD/GET e timeout de 5 segundos.
    Retorna o dicionário do canal se estiver online, ou None se estiver fora do ar.
    """
    url = channel["url"]
    headers = {"User-Agent": USER_AGENT}

    try:
        resp = session.head(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            verify=False,
        )
        if 200 <= resp.status_code < 400:
            return channel

        # Alguns servidores de streaming rejeitam HEAD (403/405/400/501), tentamos GET em modo stream
        if resp.status_code in (400, 401, 403, 404, 405, 501):
            with session.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                stream=True,
                allow_redirects=True,
                verify=False,
            ) as get_resp:
                if 200 <= get_resp.status_code < 400:
                    return channel
    except requests.RequestException:
        # Fallback rápido com GET caso o HEAD tenha falhado por reset de conexão
        try:
            with session.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                stream=True,
                allow_redirects=True,
                verify=False,
            ) as get_resp:
                if 200 <= get_resp.status_code < 400:
                    return channel
        except requests.RequestException:
            return None
    except Exception:
        return None

    return None


def generate_html(
    output_html_path: str,
    total_active: int,
    total_tested: int,
    category_counts: Dict[str, int],
    updated_at: str,
) -> None:
    """Gera a página docs/index.html exibindo o link direto da lista e a contagem de canais ativos."""
    cards_html = ""
    for cat in CATEGORY_ORDER:
        count = category_counts.get(cat, 0)
        cards_html += f"""
            <div class="stat-card">
                <span class="stat-count">{count}</span>
                <span class="stat-label">{cat}</span>
            </div>"""

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lista IPTV Unificada - Status & Download</title>
    <style>
        :root {{
            --bg: #0f172a;
            --card: #1e293b;
            --accent: #38bdf8;
            --accent-hover: #0284c7;
            --text: #f8fafc;
            --muted: #94a3b8;
            --success: #22c55e;
            --border: #334155;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem 1rem;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            max-width: 780px;
            width: 100%;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2.5rem;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(34, 197, 94, 0.15);
            color: var(--success);
            padding: 0.35rem 0.85rem;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }}
        .badge-dot {{
            width: 8px;
            height: 8px;
            background-color: var(--success);
            border-radius: 50%;
        }}
        h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}
        p.subtitle {{
            color: var(--muted);
            margin-bottom: 2rem;
        }}
        .hero-stat {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            margin-bottom: 1.5rem;
        }}
        .hero-stat .number {{
            font-size: 3rem;
            font-weight: 800;
            color: var(--accent);
            display: block;
            line-height: 1.1;
        }}
        .hero-stat .desc {{
            color: var(--muted);
            font-size: 0.95rem;
            margin-top: 0.35rem;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
            gap: 0.85rem;
            margin-bottom: 2rem;
        }}
        .stat-card {{
            background: rgba(15, 23, 42, 0.45);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1rem;
            text-align: center;
        }}
        .stat-count {{
            display: block;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text);
        }}
        .stat-label {{
            font-size: 0.8rem;
            color: var(--muted);
        }}
        .link-box {{
            background: #0b1120;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
        }}
        .link-box code {{
            color: var(--accent);
            font-size: 0.95rem;
            word-break: break-all;
            flex: 1;
        }}
        .btn-group {{
            display: flex;
            gap: 0.5rem;
        }}
        .btn {{
            background: var(--accent);
            color: #0f172a;
            border: none;
            padding: 0.6rem 1.1rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            font-size: 0.9rem;
            transition: background 0.2s;
        }}
        .btn:hover {{
            background: var(--accent-hover);
            color: #fff;
        }}
        .footer {{
            font-size: 0.85rem;
            color: var(--muted);
            text-align: center;
            border-top: 1px solid var(--border);
            padding-top: 1.25rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="badge">
            <span class="badge-dot"></span>
            Atualizada Automaticamente a cada 12h
        </div>
        <h1>Lista M3U Unificada</h1>
        <p class="subtitle">Canais verificados, deduplicados e categorizados automaticamente.</p>

        <div class="hero-stat">
            <span class="number">{total_active}</span>
            <span class="desc">Canais Ativos e Online (de {total_tested} links únicos testados)</span>
        </div>

        <div class="stats-grid">{cards_html}
        </div>

        <h3 style="margin-bottom: 0.6rem; font-size: 1rem;">Link Direto da Lista M3U:</h3>
        <div class="link-box">
            <code id="m3u-url">lista_unificada.m3u</code>
            <div class="btn-group">
                <button class="btn" onclick="copyUrl()">Copiar Link</button>
                <a class="btn" href="lista_unificada.m3u" download>Baixar .M3U</a>
            </div>
        </div>

        <div class="footer">
            Última verificação: <strong>{updated_at}</strong>
        </div>
    </div>

    <script>
        const fullUrl = new URL('lista_unificada.m3u', window.location.href).href;
        document.getElementById('m3u-url').textContent = fullUrl;

        function copyUrl() {{
            navigator.clipboard.writeText(fullUrl).then(() => {{
                alert('Link copiado para a área de transferência!');
            }});
        }}
    </script>
</body>
</html>
"""
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)


def main() -> int:
    start_time = time.time()
    print("=" * 65)
    print(" INICIANDO UNIFICAÇÃO E LIMPEZA DE LISTAS IPTV")
    print("=" * 65)

    # 1. Baixar todas as listas
    raw_channels: List[Dict[str, str]] = []
    for source in PLAYLIST_SOURCES:
        raw_channels.extend(fetch_playlist(source))

    print(f"\n[*] Total bruto de canais coletados: {len(raw_channels)}")

    # 2. Remover duplicados comparando pela URL do stream
    unique_channels: List[Dict[str, str]] = []
    seen_urls = set()

    for ch in raw_channels:
        norm_url = ch["url"].strip()
        if norm_url not in seen_urls:
            seen_urls.add(norm_url)
            unique_channels.append(ch)

    duplicates_removed = len(raw_channels) - len(unique_channels)
    print(f"[*] Duplicados removidos: {duplicates_removed}")
    print(f"[*] Canais únicos para verificar disponibilidade: {len(unique_channels)}")

    # 3. Verificação rápida de disponibilidade em paralelo (timeout = 5s)
    print(
        f"\n[*] Testando disponibilidade de {len(unique_channels)} streams "
        f"(timeout={REQUEST_TIMEOUT}s, workers={MAX_WORKERS})..."
    )

    active_channels: List[Dict[str, str]] = []
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=MAX_WORKERS,
        pool_maxsize=MAX_WORKERS,
        max_retries=0,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    completed = 0
    total_to_test = len(unique_channels)

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_channel = {
            executor.submit(check_stream_url, ch, session): ch for ch in unique_channels
        }
        for future in concurrent.futures.as_completed(future_to_channel):
            completed += 1
            result = future.result()
            if result is not None:
                active_channels.append(result)

            if completed % 250 == 0 or completed == total_to_test:
                print(
                    f"    -> Progresso: {completed}/{total_to_test} testados | "
                    f"Ativos até agora: {len(active_channels)}"
                )

    # 4. Ordenar por categoria e por nome do canal
    cat_rank = {cat: idx for idx, cat in enumerate(CATEGORY_ORDER)}
    active_channels.sort(
        key=lambda c: (cat_rank.get(c["category"], 99), c["name"].lower())
    )

    # Contabilizar por categoria
    category_counts: Dict[str, int] = {cat: 0 for cat in CATEGORY_ORDER}
    for ch in active_channels:
        category_counts[ch["category"]] = category_counts.get(ch["category"], 0) + 1

    # 5. Gerar docs/lista_unificada.m3u e docs/index.html
    docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    os.makedirs(docs_dir, exist_ok=True)

    output_m3u = os.path.join(docs_dir, "lista_unificada.m3u")
    output_html = os.path.join(docs_dir, "index.html")

    with open(output_m3u, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in active_channels:
            f.write(f'{ch["extinf"]}\n')
            if ch["extras"]:
                f.write(f'{ch["extras"]}\n')
            f.write(f'{ch["url"]}\n')

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
    generate_html(
        output_html_path=output_html,
        total_active=len(active_channels),
        total_tested=total_to_test,
        category_counts=category_counts,
        updated_at=now_str,
    )

    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(f" CONCLUÍDO EM {elapsed:.1f} SEGUNDOS!")
    print(f" Canais ativos salvos: {len(active_channels)} / {total_to_test}")
    for cat in CATEGORY_ORDER:
        print(f"   - {cat}: {category_counts.get(cat, 0)} canais")
    print(f" Arquivo M3U : {output_m3u}")
    print(f" Página HTML : {output_html}")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
