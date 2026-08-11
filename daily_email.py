#!/usr/bin/env python3
"""
Epic.Plane — Correo diario con el resultado del último post + feedback.

Trae de la Graph API las métricas del post más reciente (likes, comentarios, y
—si el token tiene el permiso— alcance/guardados/compartidos), las compara con el
promedio reciente, arma un mini-análisis accionable y lo envía por correo.

Envío: Gmail SMTP (desde la cuenta dedicada) a felipecood@gmail.com.

Uso local:
    python3 daily_email.py            # envía el correo
    python3 daily_email.py --dry-run  # imprime el correo, no lo envía

Requiere en .env (o como variables de entorno / GitHub Secrets):
    IG_USER_ID, META_PAGE_TOKEN
    GMAIL_USER          (ej. epic.plane85@gmail.com — remitente)
    GMAIL_APP_PASSWORD  (contraseña de aplicación de Gmail, 16 chars)
    EMAIL_TO            (opcional; por defecto felipecood@gmail.com)
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import smtplib
import ssl
import urllib.error
import urllib.parse
import urllib.request
import json
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GRAPH = "https://graph.facebook.com/v21.0/"
DEFAULT_TO = "felipecood@gmail.com"


def cfg() -> dict:
    e = {}
    p = ROOT / ".env"
    if p.exists():
        for l in p.read_text(encoding="utf-8").splitlines():
            if "=" in l and not l.strip().startswith("#"):
                k, _, v = l.partition("=")
                e[k.strip()] = v.strip().strip('"').strip("'")
    e.update({k: os.environ[k] for k in
              ("IG_USER_ID", "META_PAGE_TOKEN", "GMAIL_USER", "GMAIL_APP_PASSWORD", "EMAIL_TO")
              if os.environ.get(k)})
    return e


def g(path: str, params: dict, tok: str) -> dict:
    params = dict(params, access_token=tok)
    url = GRAPH + path + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return {"_error": json.loads(e.read().decode()).get("error", {}).get("message", "")}
        except Exception:
            return {"_error": str(e)}


def insights(mid: str, tok: str):
    for m in ("reach,saved,shares,total_interactions", "reach,saved,shares", "reach"):
        d = g(f"{mid}/insights", {"metric": m}, tok)
        if "_error" not in d:
            return {x["name"]: x["values"][0]["value"] for x in d.get("data", [])}
        if "permission" in (d.get("_error", "") or "").lower():
            return None
    return {}


def build(c: dict):
    ig, tok = c["IG_USER_ID"], c["META_PAGE_TOKEN"]
    prof = g(ig, {"fields": "username,followers_count"}, tok)
    followers = prof.get("followers_count", 0)
    media = g(ig + "/media", {
        "fields": "id,media_type,media_product_type,timestamp,permalink,like_count,comments_count,caption",
        "limit": "10",
    }, tok).get("data", [])
    if not media:
        return None
    p = media[0]
    ins = insights(p["id"], tok)
    reach = ins.get("reach") if ins else None
    saved = ins.get("saved") if ins else None
    shares = ins.get("shares") if ins else None

    # Comparar solo con posts recientes (últimos 45 días), no con los virales de 2021-22.
    def age(x):
        t = dt.datetime.strptime(x["timestamp"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
        return (dt.datetime.now(dt.timezone.utc) - t).days
    prev = [x for x in media[1:] if age(x) <= 45][:7]
    avg_like = round(sum(x.get("like_count", 0) for x in prev) / len(prev)) if prev else 0
    avg_com = round(sum(x.get("comments_count", 0) for x in prev) / len(prev), 1) if prev else 0

    likes = p.get("like_count", 0)
    coms = p.get("comments_count", 0)
    tipo = "Reel" if p.get("media_product_type") == "REELS" else \
           ("Carrusel" if p["media_type"] == "CAROUSEL_ALBUM" else "Imagen")
    hook = (p.get("caption") or "").split("\n")[0][:80]

    # Feedback accionable
    fb = []
    if avg_like:
        d = round((likes - avg_like) / avg_like * 100)
        fb.append(f"Likes: <b>{likes}</b> (prom. reciente {avg_like}, {'+' if d>=0 else ''}{d}%).")
    else:
        fb.append(f"Likes: <b>{likes}</b>.")
    if coms > 0:
        fb.append(f"🎉 <b>{coms} comentario(s)</b> — el gancho para comentar está funcionando. "
                  f"Respóndelos todos hoy (activa el algoritmo).")
    else:
        fb.append("0 comentarios — prueba un gancho más directo ('adivina el avión', 'esto o esto') "
                  "y responde rápido si llega alguno.")
    if reach is not None and followers:
        fb.append(f"Alcance: <b>{reach:,}</b> ({round(reach/followers*100,2)}% de tus seguidores) · "
                  f"guardados {saved} · compartidos {shares}.")
    else:
        fb.append("Alcance/guardados/compartidos: N/D (falta el permiso instagram_manage_insights).")

    # Veredicto del día
    if coms > 0 and avg_like and likes > avg_like:
        verdict = "📈 Va mejorando: más likes y hay comentarios. Seguir con este estilo."
    elif coms > 0:
        verdict = "🟢 Aparecieron comentarios — buena señal. El alcance se recupera de a poco."
    else:
        verdict = "🟡 Aún reconstruyendo alcance (cuenta que estuvo dormida). Constancia + engagement diario + stories."

    subject = f"Epic.Plane · último post: {likes}♥ {coms}💬 ({p['timestamp'][:10]})"
    body = f"""\
<div style="font-family:system-ui,Arial,sans-serif;max-width:520px;color:#111">
  <h2 style="margin:0 0 4px">Resultado de tu último post</h2>
  <p style="color:#666;margin:0 0 14px">@{prof.get('username')} · {followers:,} seguidores · {tipo}</p>
  <p style="background:#f4f6f9;border-radius:10px;padding:12px 14px;margin:0 0 14px;font-style:italic">
    "{hook}"</p>
  <ul style="line-height:1.7;padding-left:18px;margin:0 0 14px">
    {''.join(f'<li>{x}</li>' for x in fb)}
  </ul>
  <p style="background:#eef7ee;border-radius:10px;padding:12px 14px;margin:0 0 14px"><b>{verdict}</b></p>
  <p style="margin:0"><a href="{p.get('permalink','')}" style="color:#1a73e8">Ver el post ↗</a></p>
  <p style="color:#999;font-size:12px;margin-top:18px">Reporte automático de Epic.Plane.</p>
</div>"""
    return subject, body


def send(c: dict, subject: str, body: str) -> None:
    user = c.get("GMAIL_USER")
    pw = c.get("GMAIL_APP_PASSWORD")
    to = c.get("EMAIL_TO", DEFAULT_TO)
    if not user or not pw:
        raise SystemExit("Faltan GMAIL_USER / GMAIL_APP_PASSWORD (env o .env).")
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.sendmail(user, [to], msg.as_string())
    print(f"✓ Correo enviado a {to}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    c = cfg()
    if not c.get("IG_USER_ID") or not c.get("META_PAGE_TOKEN"):
        raise SystemExit("Faltan IG_USER_ID / META_PAGE_TOKEN.")
    r = build(c)
    if not r:
        raise SystemExit("No hay posts para reportar.")
    subject, body = r
    if args.dry_run:
        print("ASUNTO:", subject)
        print(body)
        return
    send(c, subject, body)


if __name__ == "__main__":
    main()
