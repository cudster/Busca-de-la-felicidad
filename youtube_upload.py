#!/usr/bin/env python3
"""Fase 2c: sube un video a YouTube (Data API v3), con los metadatos del plan.

Setup (una sola vez):
  1) En Google Cloud (mismo proyecto de la agencia): habilita "YouTube Data API v3".
  2) Crea credenciales OAuth de tipo "App de escritorio" y descarga el JSON como
     `client_secret.json` en esta carpeta.
  3) Corre:  python3 youtube_upload.py --auth
     Se abre el navegador, das consentimiento con la cuenta DUEÑA del canal, y se
     guarda `token.json`.

Subir un video ya producido (videos/<canal>-<id>.mp4):
  python3 youtube_upload.py --channel autos-pov --video 2026-10-S01
  # se sube como PRIVADO por defecto (tú lo publicas a mano cuando quieras);
  # usa --public para subirlo público (requiere la app verificada por Google).

Requiere: pip install google-auth-oauthlib google-api-python-client
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VIDEOS = ROOT / "videos"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET = ROOT / "client_secret.json"
TOKEN = ROOT / "token.json"
CATEGORY_AUTOS = "2"  # Autos & Vehicles


def _need(msg: str):
    sys.exit(msg)


def do_auth() -> None:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        _need("Falta google-auth-oauthlib. Instala:\n  pip install google-auth-oauthlib google-api-python-client")
    if not CLIENT_SECRET.exists():
        _need(f"Falta {CLIENT_SECRET}. Descárgalo de Google Cloud (OAuth app de escritorio).")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    print(f"✓ Autorizado. Token guardado en {TOKEN}. Ya puedes subir videos.")


def _credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    if not TOKEN.exists():
        _need("No hay token.json. Corre primero:  python3 youtube_upload.py --auth")
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return creds


def load_meta(channel: str, video_id: str) -> dict:
    month = video_id.rsplit("-", 1)[0]
    plan = ROOT / "youtube" / channel / f"plan-{month}.json"
    if not plan.exists():
        _need(f"No existe {plan}.")
    for v in json.loads(plan.read_text(encoding="utf-8")):
        if v["id"] == video_id:
            return v
    _need(f"No encontré {video_id} en el plan.")


def upload(channel: str, video_id: str, public: bool) -> None:
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        _need("Falta google-api-python-client. Instala:\n  pip install google-auth-oauthlib google-api-python-client")
    mp4 = VIDEOS / f"{channel}-{video_id}.mp4"
    if not mp4.exists():
        _need(f"No existe {mp4}. Produce el video primero con video_produce.py.")
    meta = load_meta(channel, video_id)
    yt = build("youtube", "v3", credentials=_credentials())
    body = {
        "snippet": {
            "title": meta.get("title", "")[:100],
            "description": (meta.get("description", "") + "\n\n" + " ".join(meta.get("hashtags", [])))[:4900],
            "tags": meta.get("tags", [])[:15],
            "categoryId": CATEGORY_AUTOS,
        },
        "status": {"privacyStatus": "public" if public else "private", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(mp4), chunksize=-1, resumable=True)
    print(f"→ Subiendo {mp4.name} como {'PÚBLICO' if public else 'PRIVADO'}…")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = req.execute()
    print(f"✓ Subido: https://youtu.be/{resp['id']}  (estado: {body['status']['privacyStatus']})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Fase 2c — sube un video a YouTube.")
    ap.add_argument("--auth", action="store_true", help="Setup de OAuth (una vez).")
    ap.add_argument("--channel", help="Canal (ej. autos-pov).")
    ap.add_argument("--video", help="Id del video (ej. 2026-10-S01).")
    ap.add_argument("--public", action="store_true", help="Subir público (default: privado).")
    args = ap.parse_args()
    if args.auth:
        do_auth()
        return
    if not args.channel or not args.video:
        _need("Indica --channel y --video (o --auth para el setup inicial).")
    upload(args.channel, args.video, args.public)


if __name__ == "__main__":
    main()
