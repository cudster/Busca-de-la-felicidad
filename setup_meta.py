#!/usr/bin/env python3
"""
Epic.Plane — Fase C: obtención de token de larga duración + IDs de Instagram.

Toma un token de usuario CORTO (generado a mano en el Graph API Explorer) y:
  1. Lo intercambia por un token de usuario de LARGA duración (~60 días).
  2. Lista tus páginas de Facebook y encuentra la vinculada a Instagram.
  3. Obtiene el token de PÁGINA de larga duración (el durable para automatizar).
  4. Obtiene el ID de tu cuenta de Instagram (IG Business Account ID).
  5. Escribe IG_USER_ID, META_PAGE_ID y META_PAGE_TOKEN en el archivo .env.

Requisitos en .env antes de correr (ver instrucciones que te pasé):
    META_APP_ID=...
    META_APP_SECRET=...
    META_SHORT_TOKEN=...        # token corto del Graph API Explorer

Uso:
    python3 setup_meta.py

Si tienes varias páginas de Facebook, el script te las lista; en ese caso
pon META_PAGE_ID=<id de la página correcta> en el .env y vuelve a correr.

No usa librerías externas (solo la stdlib de Python).
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
GRAPH_VERSION = "v21.0"  # si Meta lo rechaza por versión, súbelo (v22.0, v23.0…)
BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_PATH.exists():
        sys.exit("No existe .env. Copia .env.example a .env primero.")
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def upsert_env(updates: dict[str, str]) -> None:
    """Actualiza o agrega claves en el .env, preservando el resto."""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    remaining = dict(updates)
    out: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                continue
        out.append(raw)
    if remaining:
        out.append("")
        out.append("# --- Rellenado por setup_meta.py ---")
        for k, v in remaining.items():
            out.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


def graph_get(path: str, params: dict[str, str]) -> dict:
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(body).get("error", {})
            msg = err.get("message", body)
        except Exception:
            msg = body
        sys.exit(f"\n⚠️  Error de la Graph API en /{path}:\n   {msg}\n")
    except urllib.error.URLError as e:
        sys.exit(f"\n⚠️  No pude conectar con la Graph API: {e}\n")


def mask(token: str) -> str:
    return token[:8] + "…" + token[-4:] if len(token) > 15 else "…"


def main() -> None:
    env = load_env()
    app_id = env.get("META_APP_ID")
    app_secret = env.get("META_APP_SECRET")
    short_token = env.get("META_SHORT_TOKEN")
    preferred_page = env.get("META_PAGE_ID")  # opcional, si hay varias páginas

    missing = [k for k, v in {
        "META_APP_ID": app_id,
        "META_APP_SECRET": app_secret,
        "META_SHORT_TOKEN": short_token,
    }.items() if not v]
    if missing:
        sys.exit(
            "Faltan estas variables en .env: " + ", ".join(missing) +
            "\nComplétalas y vuelve a correr."
        )

    print("→ 1/4 Intercambiando token corto por uno de larga duración…")
    ll = graph_get("oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token,
    })
    ll_user_token = ll.get("access_token")
    if not ll_user_token:
        sys.exit(f"No recibí token largo. Respuesta: {ll}")
    print(f"   ✓ Token de usuario largo: {mask(ll_user_token)}")

    print("→ 2/4 Buscando tus páginas de Facebook…")
    accounts = graph_get("me/accounts", {
        "fields": "name,access_token,instagram_business_account",
        "access_token": ll_user_token,
    })
    pages = accounts.get("data", [])
    if not pages:
        sys.exit(
            "No apareció ninguna página de Facebook con este token.\n"
            "Revisa que generaste el token con los permisos pages_show_list y "
            "que tu usuario administra la página."
        )

    with_ig = [p for p in pages if p.get("instagram_business_account")]

    if preferred_page:
        chosen = next((p for p in pages if p.get("id") == preferred_page), None)
        if not chosen:
            sys.exit(f"META_PAGE_ID={preferred_page} no está entre tus páginas.")
    elif len(with_ig) == 1:
        chosen = with_ig[0]
    elif len(with_ig) == 0:
        listado = "\n".join(f"   - {p['name']} (id {p['id']})" for p in pages)
        sys.exit(
            "Ninguna de tus páginas muestra una cuenta de Instagram vinculada:\n"
            f"{listado}\n"
            "→ Revisa la Fase A: la página de FB debe estar conectada a Epic.Plane.\n"
            "  (En la app de IG, en ajustes profesionales, debe verse la página conectada.)"
        )
    else:
        listado = "\n".join(f"   - {p['name']} (id {p['id']})" for p in with_ig)
        sys.exit(
            "Tienes varias páginas con Instagram vinculado:\n"
            f"{listado}\n"
            "→ Pon META_PAGE_ID=<id de la página de Epic.Plane> en el .env y vuelve a correr."
        )

    page_id = chosen["id"]
    page_token = chosen["access_token"]  # largo/durable (viene de un user token largo)
    ig_user_id = chosen["instagram_business_account"]["id"]

    print(f"   ✓ Página: {chosen['name']} (id {page_id})")
    print(f"   ✓ Token de página (durable): {mask(page_token)}")
    print(f"   ✓ Instagram Business Account ID: {ig_user_id}")

    print("→ 3/4 Verificando la cuenta de Instagram…")
    ig = graph_get(ig_user_id, {
        "fields": "username,name,followers_count",
        "access_token": page_token,
    })
    print(f"   ✓ Conectado a @{ig.get('username','?')} "
          f"({ig.get('followers_count','?')} seguidores)")

    print("→ 4/4 Guardando en .env…")
    upsert_env({
        "IG_USER_ID": ig_user_id,
        "META_PAGE_ID": page_id,
        "META_PAGE_TOKEN": page_token,
    })
    print("   ✓ Guardados IG_USER_ID, META_PAGE_ID y META_PAGE_TOKEN en .env")

    print(
        "\n✓ Fase C lista. Ya podemos construir el publicador (Fase D).\n"
        "  Nota: el token corto (META_SHORT_TOKEN) ya no se necesita; el durable "
        "es META_PAGE_TOKEN."
    )


if __name__ == "__main__":
    main()
