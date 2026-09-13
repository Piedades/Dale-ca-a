"""
Busca los partidos programados para una fecha en besoccer.es y los
empareja con los nombres de equipo usados en nuestros CSV.

AVISO: esto depende de la estructura HTML actual de besoccer.es.
Si la web cambia su maquetación, el parseo puede dejar de funcionar.
Por eso guarda siempre el HTML crudo en el último fallo (last_fetch.html)
para poder diagnosticar qué cambió.
"""
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.besoccer.es"

# Slug de competición en besoccer.es -> nuestro código de liga
COMPETITION_SLUGS = {
    "primera": "SP1",
    "premier": "E0",
    "serie_a": "I1",
    "bundesliga": "D1",
    "ligue_1": "F1",
}

ALIASES_PATH = Path(__file__).parent / "team_aliases.json"


def load_aliases() -> dict:
    if ALIASES_PATH.exists():
        with open(ALIASES_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _dedupe_name(raw: str) -> str:
    """besoccer.es repite el nombre del equipo dos veces seguidas en el texto
    (ej. 'Levante Levante' o 'BarcelonaBarcelona'). Esta función lo detecta
    y se queda con una sola copia."""
    raw = raw.strip()
    n = len(raw)

    # Caso "NombreNombre" pegado sin espacio
    if n % 2 == 0 and raw[:n // 2] == raw[n // 2:]:
        return raw[:n // 2].strip()

    # Caso "Nombre Nombre" con espacio en medio
    parts = raw.split(" ")
    half = len(parts) // 2
    if half > 0 and parts[:half] == parts[half:2 * half]:
        return " ".join(parts[:half])

    return raw


def resolve_team_name(besoccer_name: str, league_code: str, known_teams: list, aliases: dict) -> str | None:
    """Intenta encontrar el nombre que usamos en los CSV para un equipo de besoccer.es."""
    name = besoccer_name.strip()

    # 1. Coincidencia exacta
    if name in known_teams:
        return name

    # 2. Alias explícito guardado
    league_aliases = aliases.get(league_code, {})
    if name in league_aliases:
        return league_aliases[name]

    # 3. Coincidencia por contención (ej. "Atlético Madrid" contiene "Atlético")
    name_lower = name.lower()
    for team in known_teams:
        if team.lower() in name_lower or name_lower in team.lower():
            return team

    return None


def fetch_matches_for_date(date_str: str) -> list[dict]:
    """
    date_str: 'YYYY-MM-DD'
    Devuelve una lista de dicts: {"league_code", "home_raw", "away_raw", "time"}
    Solo incluye partidos de las 5 ligas que seguimos.
    """
    url = f"{BASE_URL}/livescore/{date_str}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.besoccer.es/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    # Guardamos el HTML crudo por si hay que depurar el parseo
    debug_path = Path(__file__).parent / "last_fetch.html"
    debug_path.write_text(resp.text, encoding="utf-8")

    soup = BeautifulSoup(resp.text, "html.parser")

    matches = []
    current_league = None

    # Recorremos el documento en orden: enlaces a /competicion/ marcan la
    # sección, enlaces a /partido/ son los partidos de esa sección.
    for
