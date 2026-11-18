#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unificador e Verificador de Listas M3U de IPTV.
Regras de Filtragem Regional e por Tipo:
- Brasil: Canais Abertos (incluindo Globo, Band, SBT, Cultura), Filmes e Séries, Esportes, Notícias, Entretenimento, etc.
- Peru, Chile, Colômbia, Bolívia, Venezuela (e demais da América do Sul): APENAS Esportes.
- América do Norte: APENAS EUA, México e Canadá, e APENAS canais de Notícias, Entretenimento (e Filmes/Séries) e Esportes.
- Europa: APENAS canais de Esportes e Notícias.
- Sem Oriente Médio, Ásia, África, Oceania e sem Anime.
"""

import concurrent.futures
import datetime
import json
import os
import re
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ESSENTIAL_BR_CHANNELS = [
    {
        "name": "Rede Globo (TV Clube HD)",
        "category": "Brasil Abertos",
        "genre": "Canais Abertos / Variedades",
        "country": "Brasil",
        "region": "BR",
        "logo": "https://i.imgur.com/O02TF2r.png",
        "extinf": '#EXTINF:-1 tvg-id="RedeGlobo.br@HD" tvg-logo="https://i.imgur.com/O02TF2r.png" group-title="Brasil Abertos",Rede Globo (TV Clube HD)',
        "extras": "",
        "url": "https://5c483b9d1019c.streamlock.net/8186/8186/playlist.m3u8",
    },
    {
        "name": "TV Globo Brasília (1080p)",
        "category": "Brasil Abertos",
        "genre": "Canais Abertos / Variedades",
        "country": "Brasil",
        "region": "BR",
        "logo": "https://i.imgur.com/O02TF2r.png",
        "extinf": '#EXTINF:-1 tvg-id="TVGloboBrasilia.br@HD" tvg-logo="https://i.imgur.com/O02TF2r.png" group-title="Brasil Abertos",TV Globo Brasília (1080p)',
        "extras": "",
        "url": "http://79.127.238.228:14173",
    },
    {
        "name": "TV Globo Bahia (FHD)",
        "category": "Brasil Abertos",
        "genre": "Canais Abertos / Variedades",
        "country": "Brasil",
        "region": "BR",
        "logo": "https://i.imgur.com/O02TF2r.png",
        "extinf": '#EXTINF:-1 tvg-id="TVGloboBahia.br@HD" tvg-logo="https://i.imgur.com/O02TF2r.png" group-title="Brasil Abertos",TV Globo Bahia (FHD)',
        "extras": "",
        "url": "http://hls1.sua.tv/live/globotvbahiafhdbr2/s.m3u8",
    },
    {
        "name": "GloboNews (1080p)",
        "category": "Brasil Abertos",
        "genre": "Notícias",
        "country": "Brasil",
        "region": "BR",
        "logo": "https://i.imgur.com/3yZyaCm.png",
        "extinf": '#EXTINF:-1 tvg-id="GloboNews.br@HD" tvg-logo="https://i.imgur.com/3yZyaCm.png" group-title="Brasil Abertos",GloboNews (1080p)',
        "extras": "",
        "url": "http://79.127.238.228:14093",
    },
    {
        "name": "Globoplay Novelas / Viva (1080p)",
        "category": "Filmes e Séries BR",
        "genre": "Entretenimento",
        "country": "Brasil",
        "region": "BR",
        "logo": "https://i.ibb.co/m5TBCDL2/Globoplay-Novelas-1.png",
        "extinf": '#EXTINF:-1 tvg-id="GloboplayNovelas.br@HD" tvg-logo="https://i.ibb.co/m5TBCDL2/Globoplay-Novelas-1.png" group-title="Filmes e Séries BR",Globoplay Novelas / Viva (1080p)',
        "extras": "",
        "url": "http://79.127.238.228:14455",
    },
    {
        "name": "GE Fast - Globo Esporte (1080p)",
        "category": "Esportes",
        "genre": "Esportes",
        "country": "Brasil",
        "region": "BR",
        "logo": "https://i.imgur.com/O02TF2r.png",
        "extinf": '#EXTINF:-1 tvg-id="GEFast.br@HD" tvg-logo="https://i.imgur.com/O02TF2r.png" group-title="Esportes",GE Fast - Globo Esporte (1080p)',
        "extras": "",
        "url": "https://amg00716-globo-amg00716c1-tcl-br-9495.playouts.now.amagi.tv/playlist.m3u8",
    },
    {
        "name": "Band (Rede Bandeirantes / Arapuan HD)",
        "category": "Brasil Abertos",
        "genre": "Canais Abertos / Variedades",
        "country": "Brasil",
        "region": "BR",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/22/Logotipo_da_Rede_Bandeirantes.svg/512px-Logotipo_da_Rede_Bandeirantes.svg.png",
        "extinf": '#EXTINF:-1 tvg-id="Band.br@HD" tvg-logo="https://upload.wikimedia.org/wikipedia/commons/thumb/2/22/Logotipo_da_Rede_Bandeirantes.svg/512px-Logotipo_da_Rede_Bandeirantes.svg.png" group-title="Brasil Abertos",Band (Rede Bandeirantes / Arapuan HD)',
        "extras": "",
        "url": "https://5b7f3c45ab7c2.streamlock.net/arapuan/ngrp:arapuan_all/chunklist.m3u8",
    },
    {
        "name": "Band Sports (HD)",
        "category": "Esportes",
        "genre": "Esportes",
        "country": "Brasil",
        "region": "BR",
        "logo": "https://i.imgur.com/Im17222.png",
        "extinf": '#EXTINF:-1 tvg-id="BandSports.br@HD" tvg-logo="https://i.imgur.com/Im17222.png" group-title="Esportes",Band Sports (HD)',
        "extras": "",
        "url": "http://170.83.16.50/BAND_SPORTS/index.m3u8",
    },
    {
        "name": "SBT Nacional (HD)",
        "category": "Brasil Abertos",
        "genre": "Canais Abertos / Variedades",
        "country": "Brasil",
        "region": "BR",
        "logo": "https://i.imgur.com/tc1ALuu.png",
        "extinf": '#EXTINF:-1 tvg-id="SBTNacional.br@HD" tvg-logo="https://i.imgur.com/tc1ALuu.png" group-title="Brasil Abertos",SBT Nacional (HD)',
        "extras": "",
        "url": "https://cdn.live.br1.jmvstream.com/w/LVW-10801/LVW10801_Xvg4R0u57n/chunklist.m3u8",
    },
    {
        "name": "TV Cultura (HD)",
        "category": "Brasil Abertos",
        "genre": "Cultura e Documentários",
        "country": "Brasil",
        "region": "BR",
        "logo": "https://i.imgur.com/3f1c7t0.png",
        "extinf": '#EXTINF:-1 tvg-id="TVCultura.br@HD" tvg-logo="https://i.imgur.com/3f1c7t0.png" group-title="Brasil Abertos",TV Cultura (HD)',
        "extras": "",
        "url": "https://player-tvcultura.stream.uol.com.br/live/tvcultura.m3u8",
    },
]

PLAYLIST_SOURCES = [
    {
        "name": "Canais Essenciais Brasil",
        "url": "https://raw.githubusercontent.com/brito219/iptv-brasil/main/essenciais.m3u",
        "default_category": "Brasil Abertos",
        "origin": "BR",
        "default_country": "br",
    },
    {
        "name": "Canais abertos Brasil",
        "url": "https://github.com/iptv-com/iptv/raw/refs/heads/main/lists/brazil.m3u",
        "default_category": "Brasil Abertos",
        "origin": "BR",
        "default_country": "br",
    },
    {
        "name": "Canais Brasil (iptv-org)",
        "url": "https://iptv-org.github.io/iptv/countries/br.m3u",
        "default_category": "Brasil Abertos",
        "origin": "BR",
        "default_country": "br",
    },
    {
        "name": "Canais em Português",
        "url": "https://iptv-org.github.io/iptv/languages/por.m3u",
        "default_category": "Brasil Abertos",
        "origin": "BR",
        "default_country": "br",
    },
    {
        "name": "Filmes e Séries 24h Brasil (Pluto TV)",
        "url": "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/plutotv_br.m3u",
        "default_category": "Filmes e Séries BR",
        "origin": "BR_MOVIES",
        "default_country": "br",
    },
    {
        "name": "Esportes",
        "url": "https://iptv-org.github.io/iptv/categories/sports.m3u",
        "default_category": "Esportes",
        "origin": "SPORTS",
        "default_country": "",
    },
    {
        "name": "Canais abertos EUA",
        "url": "https://iptv-org.github.io/iptv/countries/us.m3u",
        "default_category": "EUA Abertos",
        "origin": "US",
        "default_country": "us",
    },
    {
        "name": "Filmes e Séries 24h EUA (Pluto TV)",
        "url": "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/plutotv_us.m3u",
        "default_category": "Filmes e Séries EUA",
        "origin": "US_MOVIES",
        "default_country": "us",
    },
]

CATEGORY_ORDER = [
    "Brasil Abertos",
    "Filmes e Séries BR",
    "Esportes",
    "EUA Abertos",
    "Filmes e Séries EUA",
]

# Mapeamento (Código ISO -> (Nome do País, Região))
# Regiões:
# - BR: Brasil (todos os tipos permitidos, exceto anime)
# - SA_OTHER: Peru, Chile, Colômbia, Bolívia, Venezuela, Argentina, etc. (APENAS Esportes)
# - NA: EUA, México e Canadá (APENAS Esportes, Notícias e Entretenimento)
# - EU: Europa (APENAS Esportes e Notícias)
COUNTRY_REGION_MAP: Dict[str, Tuple[str, str]] = {
    # Brasil
    "br": ("Brasil", "BR"),
    # América do Sul (exceto Brasil) -> Apenas Esportes
    "pe": ("Peru", "SA_OTHER"),
    "cl": ("Chile", "SA_OTHER"),
    "co": ("Colômbia", "SA_OTHER"),
    "bo": ("Bolívia", "SA_OTHER"),
    "ve": ("Venezuela", "SA_OTHER"),
    "ar": ("Argentina", "SA_OTHER"),
    "uy": ("Uruguai", "SA_OTHER"),
    "py": ("Paraguai", "SA_OTHER"),
    "ec": ("Equador", "SA_OTHER"),
    # América do Norte -> Apenas EUA, México e Canadá (Esportes, Notícias e Entretenimento)
    "us": ("Estados Unidos", "NA"),
    "mx": ("México", "NA"),
    "ca": ("Canadá", "NA"),
    # Europa -> Apenas Esportes e Notícias
    "pt": ("Portugal", "EU"),
    "es": ("Espanha", "EU"),
    "uk": ("Reino Unido", "EU"),
    "gb": ("Reino Unido", "EU"),
    "fr": ("França", "EU"),
    "de": ("Alemanha", "EU"),
    "it": ("Itália", "EU"),
    "nl": ("Países Baixos", "EU"),
    "be": ("Bélgica", "EU"),
    "ch": ("Suíça", "EU"),
    "at": ("Áustria", "EU"),
    "ie": ("Irlanda", "EU"),
    "se": ("Suécia", "EU"),
    "no": ("Noruega", "EU"),
    "dk": ("Dinamarca", "EU"),
    "fi": ("Finlândia", "EU"),
    "pl": ("Polônia", "EU"),
    "cz": ("República Tcheca", "EU"),
    "sk": ("Eslováquia", "EU"),
    "hu": ("Hungria", "EU"),
    "ro": ("Romênia", "EU"),
    "bg": ("Bulgária", "EU"),
    "gr": ("Grécia", "EU"),
    "hr": ("Croácia", "EU"),
    "rs": ("Sérvia", "EU"),
    "si": ("Eslovênia", "EU"),
    "ua": ("Ucrânia", "EU"),
    "lt": ("Lituânia", "EU"),
    "lv": ("Letônia", "EU"),
    "ee": ("Estônia", "EU"),
    "lu": ("Luxemburgo", "EU"),
    "mc": ("Mônaco", "EU"),
    "mt": ("Malta", "EU"),
    "ad": ("Andorra", "EU"),
    "is": ("Islândia", "EU"),
}

MIDDLE_EAST_ASIA_KEYWORDS = (
    "al jazeera", "aljazeera", "al arabiya", "alarabiya", "alkass", "al kass",
    "dubai", "abu dhabi", "sharjah", "bahrain", "kuwait", "oman", "qatar",
    "saudi", "rotana", "mbc", "ssc ", "ksa ", "bein ", "iraq", "iran", "kurd",
    "asharq", "nile", "zamalek", "on time sports", "angel tv", "peace tv",
    "arryadia", "tamazight", "medi1", "al aoula", "2m monde", "watania",
    "hespress", "echourouk", "ennahar", "algeria", "tunisia", "libya",
    "yemen", "syria", "lebanon", "jordan", "palestine", "makkah", "madinah",
    "quran", "sunnah", "iqraa", "majd", "resalah", "aliman", "almayadeen",
    "al manar", "al hadath", "al ghad", "al hurra", "rudaw", "zagros",
    "kurdistan", "persian", "farsi", "afghan", "pakistan", "india ", "indian",
    "bangla", "nepal", "sri lanka", "cctv", "cgtn", "tvb", "nhk", "kbs",
    "sbs ", "mbc korea", "arirang", "ytv", "myanmar", "thai", "vietnam",
    "indonesia", "malaysia", "philippines", "kazakh", "uzbek", "turkmen",
    "azerbaijan", "armenia", "georgia", "trt ", "haberturk", "a spor",
    "tpa ", "tvcabo", "zap ", "zimbo", "girassol", "stve", "rtpa",
)

ANIME_KEYWORDS = (
    "anime", "animax", "naruto", "boruto", "one piece", "dragon ball",
    "yu-gi-oh", "yugioh", "beyblade", "bakugan", "inuyasha", "sailor moon",
    "pokemon", "pokémon", "digimon", "bleach", "death note", "hunter x hunter",
    "fairy tail", "attack on titan", "demon slayer", "jujutsu", "lupin",
    "detective conan", "conan", "cardcaptor", "saint seiya", "cavaleiros do zodiaco",
    "super campeoes", "super campeões", "captain tsubasa", "shaman king",
    "astro boy", "speed racer", "ghost in the shell", "evangelion",
    "cowboy bebop", "fullmetal", "gundam", "macross", "robotech",
    "retrocrush", "crunchyroll", "hidive", "toonami", "geekdot", "otaku",
    "tokusatsu", "ultraman", "jaspion", "kamen rider", "super sentai",
    "totoro", "ghibli", "akira",
)

REQUEST_TIMEOUT = 5
MAX_WORKERS = 80
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VLC/3.0.20 LibVLC/3.0.20"

GROUP_TITLE_REGEX = re.compile(r'group-title="([^"]*)"', re.IGNORECASE)
TVG_ID_REGEX = re.compile(r'tvg-id="([^"]*)"', re.IGNORECASE)
TVG_LOGO_REGEX = re.compile(r'tvg-logo="([^"]*)"', re.IGNORECASE)
COUNTRY_CODE_REGEX = re.compile(r'\.([a-z]{2})(?:@|$)', re.IGNORECASE)

NON_WESTERN_SCRIPT_REGEX = re.compile(
    r'[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u0900-\u097F\u0E00-\u0E7F\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF]'
)


def classify_genre(extinf_line: str, channel_name: str, origin: str) -> str:
    """
    Classifica o tipo do canal em:
    - 'Esportes'
    - 'Notícias'
    - 'Entretenimento'
    - 'Canais Abertos / Variedades'
    - 'Cultura e Documentários'
    - 'Música'
    - 'Infantil'
    - 'Outros'
    """
    if origin == "SPORTS":
        return "Esportes"

    match = GROUP_TITLE_REGEX.search(extinf_line)
    raw_group = match.group(1).lower() if match else ""
    lower_name = channel_name.lower()
    combined = f"{raw_group} {lower_name}"

    # Bloqueia canais de vendas/religiosos/clima local de entrarem como entretenimento
    if any(k in raw_group for k in ("shop", "religious", "weather", "legislative")):
        if "news" not in raw_group:
            return "Outros"

    if any(k in combined for k in (
        "sport", "esporte", "futebol", "soccer", "nfl", "nba", "mlb", "nhl", "ufc",
        "fight", "wrestling", "golf", "tennis", "motor", "racing", "f1", "nascar",
        "billiard", "poker", "surf", "skate", "boxing", "mma", "dazn", "espn",
        "fox sports", "cbs sports", "beinsports", "tudn", "tyc", "deport", "ovacion",
        "teletrak", "win sports", "meridiano",
    )):
        return "Esportes"

    if any(k in combined for k in (
        "news", "notícia", "noticia", "jornal", "cnn", "bbc news", "sky news",
        "fox news", "cnbc", "bloomberg", "msnbc", "nbc news", "cbs news", "abc news",
        "globonews", "bandnews", "record news", "sbt news", "jovem pan news",
        "euronews", "france 24", "dw ", "bfm", "sic noticias", "rtp 3", "24h",
        "weather", "c-span", "reuters", "associated press", "newsmax", "scripps news",
        "live now", "livenow",
    )):
        return "Notícias"

    if any(k in combined for k in (
        "entertainment", "entretenimento", "movie", "movies", "filme", "filmes",
        "cinema", "cine", "series", "série", "series", "novela", "drama", "action",
        "ação", "comedy", "comédia", "humor", "thriller", "terror", "horror",
        "sci-fi", "western", "romance", "reality", "game show", "talk", "pop culture",
        "retrô", "retro", "classic", "crime", "mystery", "suspense", "paramount",
        "hallmark", "amc", "tcm", "syfy", "star trek", "csi", "ncis", "hell's kitchen",
        "masterchef", "top gear", "failarmy", "pet collective", "nosey", "mtv",
        "bet ", "vh1", "e!", "bravo", "tlc", "hgtv", "food network", "cooking",
        "tastemade", "court tv", "law & crime", "ion ", "bounce", "grit", "laff",
        "me tv", "metv", "antena", "buzzr", "deal or no deal", "family feud",
        "jeopardy", "wheel of fortune", "price is right", "baywatch", "doctor who",
        "curiosit", "fofoca", "tv brasileira",
    )):
        return "Entretenimento"

    if origin in ("BR_MOVIES", "US_MOVIES"):
        return "Entretenimento"

    if any(k in combined for k in ("music", "música", "musica", "vevo", "trace", "stingray", "karaoke", "concert")):
        return "Música"

    if any(k in combined for k in ("doc", "history", "história", "nature", "natureza", "science", "ciência", "discovery", "nat geo", "smithsonian", "cultura", "educat", "travel", "viagem")):
        return "Cultura e Documentários"

    if any(k in combined for k in ("kids", "infantil", "criança", "junior", "nick", "disney", "cartoon", "baby", "pbs kids", "lego", "ryan", "smurfs", "garfield", "turma da monica")):
        return "Infantil"

    return "Canais Abertos / Variedades"


def filter_and_classify_channel(
    extinf_line: str,
    channel_name: str,
    origin: str,
    default_country: str,
) -> Optional[Tuple[str, str, str]]:
    """
    Aplica todas as regras de filtragem:
    - Sem Oriente Médio, Ásia, África, Oceania e sem Anime.
    - Brasil: Todos os tipos permitidos.
    - Peru, Chile, Colômbia, Bolívia, Venezuela (e demais da América do Sul): APENAS Esportes.
    - América do Norte (EUA, México, Canadá): APENAS Notícias, Entretenimento e Esportes.
    - Europa: APENAS Esportes e Notícias.
    Retorna (country_name, region_code, genre) ou None se descartado.
    """
    lower_name = channel_name.lower()
    lower_extinf = extinf_line.lower()

    if NON_WESTERN_SCRIPT_REGEX.search(channel_name):
        return None

    if any(k in lower_name for k in MIDDLE_EAST_ASIA_KEYWORDS):
        return None

    if any(k in lower_name or k in lower_extinf for k in ANIME_KEYWORDS):
        return None

    tvg_match = TVG_ID_REGEX.search(extinf_line)
    tvg_id = tvg_match.group(1) if tvg_match else ""
    cc_match = COUNTRY_CODE_REGEX.search(tvg_id)

    country_name = None
    region_code = None

    if cc_match:
        cc = cc_match.group(1).lower()
        if "@br" in tvg_id.lower() or "brazil" in lower_name or "brasil" in lower_name:
            country_name, region_code = ("Brasil", "BR")
        elif cc in COUNTRY_REGION_MAP:
            country_name, region_code = COUNTRY_REGION_MAP[cc]
        else:
            return None
    elif default_country and default_country in COUNTRY_REGION_MAP:
        country_name, region_code = COUNTRY_REGION_MAP[default_country]
    else:
        return None

    genre = classify_genre(extinf_line, channel_name, origin)

    # Regra 1: Brasil -> permite todos os gêneros (exceto Outros/Shop indesejados se quiser, mas mantém abertos)
    if region_code == "BR":
        if genre == "Outros":
            genre = "Canais Abertos / Variedades"
        return country_name, region_code, genre

    # Regra 2: Peru, Chile, Colômbia, Bolívia, Venezuela e demais da América do Sul -> SÓ Esportes
    if region_code == "SA_OTHER":
        if genre == "Esportes":
            return country_name, region_code, genre
        return None

    # Regra 3: América do Norte (EUA, México, Canadá) -> SÓ Notícias, Entretenimento e Esportes
    if region_code == "NA":
        if genre in ("Esportes", "Notícias", "Entretenimento"):
            return country_name, region_code, genre
        return None

    # Regra 4: Europa -> SÓ Esportes e Notícias
    if region_code == "EU":
        if genre in ("Esportes", "Notícias"):
            return country_name, region_code, genre
        return None

    return None


def determine_category(genre: str, region_code: str, origin: str) -> str:
    """Mapeia para as 5 categorias limpas do group-title."""
    if genre == "Esportes":
        return "Esportes"
    if region_code == "BR":
        if origin == "BR_MOVIES" or genre == "Entretenimento":
            return "Filmes e Séries BR"
        return "Brasil Abertos"
    if region_code == "NA":
        if origin == "US_MOVIES" or genre == "Entretenimento":
            return "Filmes e Séries EUA"
        return "EUA Abertos"
    if region_code == "EU":
        return "EUA Abertos"
    return "Esportes"


def normalize_extinf(extinf_line: str, category: str) -> Tuple[str, str, str]:
    """Atualiza o atributo group-title na linha #EXTINF."""
    line = extinf_line.strip()
    if GROUP_TITLE_REGEX.search(line):
        line = GROUP_TITLE_REGEX.sub(f'group-title="{category}"', line)
    else:
        if "," in line:
            parts = line.split(",", 1)
            line = f'{parts[0]} group-title="{category}",{parts[1]}'
        else:
            line = f'{line} group-title="{category}"'

    channel_name = line.split(",", 1)[1].strip() if "," in line else "Canal Sem Nome"
    logo_match = TVG_LOGO_REGEX.search(line)
    logo_url = logo_match.group(1).strip() if logo_match else ""
    return line, channel_name, logo_url


def fetch_playlist(source: Dict[str, str]) -> List[Dict[str, str]]:
    """Baixa uma lista M3U e extrai seus canais aplicando as regras de País e Tipo."""
    name = source["name"]
    url = source["url"]
    origin = source["origin"]
    default_country = source.get("default_country", "")

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
    filtered_out = 0
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
                ch_name_raw = current_extinf.split(",", 1)[1].strip() if "," in current_extinf else "Canal"
                res = filter_and_classify_channel(current_extinf, ch_name_raw, origin, default_country)
                if res is None:
                    filtered_out += 1
                else:
                    country_name, region_code, genre = res
                    category = determine_category(genre, region_code, origin)
                    updated_extinf, channel_name, logo_url = normalize_extinf(current_extinf, category)
                    channels.append(
                        {
                            "name": channel_name,
                            "category": category,
                            "genre": genre,
                            "country": country_name,
                            "region": region_code,
                            "logo": logo_url,
                            "extinf": updated_extinf,
                            "extras": "\n".join(extra_directives),
                            "url": line,
                        }
                    )
            current_extinf = None
            extra_directives = []

    print(
        f"    [+] {len(channels)} canais aprovados em '{name}' "
        f"({filtered_out} descartados pelas regras de país/tipo)."
    )
    return channels


def check_stream_url(channel: Dict[str, str], session: requests.Session) -> Optional[Dict[str, str]]:
    """Testa a disponibilidade do link do stream com HTTP HEAD/GET e timeout de 5 segundos."""
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


def generate_markdown_report(
    report_path: str,
    active_channels: List[Dict[str, str]],
    updated_at: str,
) -> None:
    """Gera o relatório completo de canais agrupados por Tipo e por País."""
    by_genre: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    by_country: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    for ch in active_channels:
        by_genre[ch["genre"]].append(ch)
        by_country[ch["country"]].append(ch)

    lines = [
        "# Relatório Completo de Canais Ativos (Por Tipo e Por País)",
        f"\nÚltima atualização: **{updated_at}** | Total de canais ativos: **{len(active_channels)}**\n",
        "## 1. Resumo por Tipo (Gênero)",
        "| Tipo / Gênero | Quantidade de Canais |",
        "| :--- | :---: |",
    ]
    for genre, ch_list in sorted(by_genre.items(), key=lambda x: -len(x[1])):
        lines.append(f"| **{genre}** | {len(ch_list)} |")

    lines.extend([
        "\n## 2. Resumo por País",
        "| País | Quantidade de Canais | Tipos Mantidos |",
        "| :--- | :---: | :--- |",
    ])
    for country, ch_list in sorted(by_country.items(), key=lambda x: -len(x[1])):
        genres_present = ", ".join(sorted(set(c["genre"] for c in ch_list)))
        lines.append(f"| **{country}** | {len(ch_list)} | {genres_present} |")

    lines.append("\n---\n## 3. Lista Detalhada de Canais por Tipo")
    for genre, ch_list in sorted(by_genre.items(), key=lambda x: -len(x[1])):
        lines.append(f"\n### {genre} ({len(ch_list)} canais)")
        for ch in sorted(ch_list, key=lambda c: (c["country"], c["name"].lower())):
            lines.append(f"- **{ch['name']}** ({ch['country']})")

    lines.append("\n---\n## 4. Lista Detalhada de Canais por País")
    for country, ch_list in sorted(by_country.items(), key=lambda x: -len(x[1])):
        lines.append(f"\n### {country} ({len(ch_list)} canais)")
        for ch in sorted(ch_list, key=lambda c: (c["genre"], c["name"].lower())):
            lines.append(f"- **{ch['name']}** (*{ch['genre']}*)")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def generate_html(
    output_html_path: str,
    active_channels: List[Dict[str, str]],
    total_tested: int,
    category_counts: Dict[str, int],
    updated_at: str,
) -> None:
    """Gera a página docs/index.html com estatísticas e um Grid visual interativo de todos os canais."""
    cards_html = ""
    for cat in CATEGORY_ORDER:
        count = category_counts.get(cat, 0)
        cards_html += f"""
            <div class="stat-card">
                <span class="stat-count">{count}</span>
                <span class="stat-label">{cat}</span>
            </div>"""

    channels_json = json.dumps(
        [
            {
                "name": ch["name"],
                "category": ch["category"],
                "genre": ch["genre"],
                "country": ch["country"],
                "logo": ch["logo"],
            }
            for ch in active_channels
        ],
        ensure_ascii=False,
    )

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lista IPTV Unificada - Grid de Canais & Status</title>
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
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem 1rem;
        }}
        .container {{
            max-width: 1180px;
            margin: 0 auto;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2rem;
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
        h1 {{ font-size: 2rem; margin-bottom: 0.3rem; }}
        p.subtitle {{ color: var(--muted); margin-bottom: 1.5rem; }}
        .hero-stat {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            text-align: center;
            margin-bottom: 1.25rem;
        }}
        .hero-stat .number {{
            font-size: 2.75rem;
            font-weight: 800;
            color: var(--accent);
            display: block;
            line-height: 1.1;
        }}
        .hero-stat .desc {{ color: var(--muted); font-size: 0.95rem; margin-top: 0.35rem; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 0.85rem;
            margin-bottom: 1.5rem;
        }}
        .stat-card {{
            background: rgba(15, 23, 42, 0.45);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.9rem;
            text-align: center;
        }}
        .stat-count {{ display: block; font-size: 1.4rem; font-weight: 700; color: var(--text); }}
        .stat-label {{ font-size: 0.8rem; color: var(--muted); }}
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
            margin-bottom: 2rem;
        }}
        .link-box code {{ color: var(--accent); font-size: 0.95rem; word-break: break-all; flex: 1; }}
        .btn-group {{ display: flex; gap: 0.5rem; }}
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
        }}
        .btn:hover {{ background: var(--accent-hover); color: #fff; }}
        .filters {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
        }}
        .filters input, .filters select {{
            background: #0b1120;
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.65rem 0.9rem;
            font-size: 0.9rem;
            flex: 1;
            min-width: 180px;
        }}
        .channels-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .channel-card {{
            background: #0b1120;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            gap: 0.55rem;
            transition: transform 0.15s, border-color 0.15s;
        }}
        .channel-card:hover {{
            border-color: var(--accent);
            transform: translateY(-2px);
        }}
        .channel-logo {{
            width: 84px;
            height: 54px;
            object-fit: contain;
            background: rgba(255, 255, 255, 0.04);
            border-radius: 6px;
            padding: 4px;
        }}
        .channel-name {{ font-weight: 700; font-size: 0.95rem; color: var(--text); }}
        .channel-tags {{ display: flex; flex-wrap: wrap; gap: 0.35rem; justify-content: center; }}
        .tag {{
            font-size: 0.72rem;
            padding: 0.15rem 0.5rem;
            border-radius: 999px;
            background: rgba(56, 189, 248, 0.12);
            color: var(--accent);
        }}
        .tag.country {{
            background: rgba(34, 197, 94, 0.12);
            color: var(--success);
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
        <h1>Lista M3U Unificada - Grid de Canais</h1>
        <p class="subtitle">Canais selecionados por País e Tipo (Esporte, Notícias, Entretenimento e Brasil).</p>

        <div class="hero-stat">
            <span class="number">{len(active_channels)}</span>
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

        <h3 style="margin-bottom: 0.75rem; font-size: 1.15rem;">Catálogo Visual em Grid (<span id="shown-count">{len(active_channels)}</span> canais):</h3>
        <div class="filters">
            <input type="text" id="search-input" placeholder="Buscar canal (ex: Globo, Band, ESPN, CNN)..." oninput="renderGrid()">
            <select id="genre-filter" onchange="renderGrid()">
                <option value="">Todos os Tipos (Gêneros)</option>
            </select>
            <select id="country-filter" onchange="renderGrid()">
                <option value="">Todos os Países</option>
            </select>
        </div>

        <div class="channels-grid" id="channels-grid"></div>

        <div class="footer">
            Última verificação: <strong>{updated_at}</strong>
        </div>
    </div>

    <script>
        const CHANNELS = {channels_json};
        const fullUrl = new URL('lista_unificada.m3u', window.location.href).href;
        document.getElementById('m3u-url').textContent = fullUrl;

        function copyUrl() {{
            navigator.clipboard.writeText(fullUrl).then(() => {{
                alert('Link copiado para a área de transferência!');
            }});
        }}

        const genres = [...new Set(CHANNELS.map(c => c.genre))].sort();
        const countries = [...new Set(CHANNELS.map(c => c.country))].sort();

        const genreSelect = document.getElementById('genre-filter');
        genres.forEach(g => {{
            const opt = document.createElement('option');
            opt.value = g;
            opt.textContent = g;
            genreSelect.appendChild(opt);
        }});

        const countrySelect = document.getElementById('country-filter');
        countries.forEach(c => {{
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            countrySelect.appendChild(opt);
        }});

        function renderGrid() {{
            const q = document.getElementById('search-input').value.toLowerCase().trim();
            const g = genreSelect.value;
            const c = countrySelect.value;

            const filtered = CHANNELS.filter(ch => {{
                if (q && !ch.name.toLowerCase().includes(q)) return false;
                if (g && ch.genre !== g) return false;
                if (c && ch.country !== c) return false;
                return true;
            }});

            document.getElementById('shown-count').textContent = filtered.length;
            const grid = document.getElementById('channels-grid');
            grid.innerHTML = filtered.map(ch => `
                <div class="channel-card">
                    ${{ch.logo ? `<img class="channel-logo" src="${{ch.logo}}" loading="lazy" onerror="this.style.display='none'">` : ''}}
                    <div class="channel-name">${{ch.name}}</div>
                    <div class="channel-tags">
                        <span class="tag">${{ch.genre}}</span>
                        <span class="tag country">${{ch.country}}</span>
                    </div>
                </div>
            `).join('');
        }}

        renderGrid();
    </script>
</body>
</html>
"""
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)


def main() -> int:
    start_time = time.time()
    print("=" * 65)
    print(" INICIANDO UNIFICAÇÃO E FILTRAGEM FINA POR PAÍS E TIPO")
    print("=" * 65)

    raw_channels: List[Dict[str, str]] = list(ESSENTIAL_BR_CHANNELS)
    for source in PLAYLIST_SOURCES:
        raw_channels.extend(fetch_playlist(source))

    print(f"\n[*] Total de canais após filtro fino por país/tipo: {len(raw_channels)}")

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

    cat_rank = {cat: idx for idx, cat in enumerate(CATEGORY_ORDER)}
    active_channels.sort(
        key=lambda c: (cat_rank.get(c["category"], 99), c["name"].lower())
    )

    category_counts: Dict[str, int] = {cat: 0 for cat in CATEGORY_ORDER}
    for ch in active_channels:
        category_counts[ch["category"]] = category_counts.get(ch["category"], 0) + 1

    docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    os.makedirs(docs_dir, exist_ok=True)

    output_m3u = os.path.join(docs_dir, "lista_unificada.m3u")
    output_html = os.path.join(docs_dir, "index.html")
    output_report = os.path.join(docs_dir, "relatorio_canais.md")

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
        active_channels=active_channels,
        total_tested=total_to_test,
        category_counts=category_counts,
        updated_at=now_str,
    )
    generate_markdown_report(
        report_path=output_report,
        active_channels=active_channels,
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
    print(f" Relatório MD: {output_report}")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
