#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comments.py — Community Manager: responde comentarios de Instagram.

Modo elegido por el dueño: **auto solo positivos simples + escalar el resto**.
- Positivo simple (elogio corto / emoji, sin pregunta ni tema delicado)
  -> respuesta corta, cálida, en la voz de la marca (plantilla; IA opcional).
- Todo lo demás (preguntas, PRECIOS, pedidos, reclamos, negativos, ambiguos)
  -> NO se responde solo: se ESCALA a un humano (cola en data/comments/).

Seguridad:
- NUNCA auto-responde sobre precios, reclamos o negativos.
- Guarda los ids ya respondidos para no duplicar.
- Por defecto DRY-RUN (muestra qué haría). Con --post publica de verdad.

Requisitos:
- Token de Página con scope **instagram_manage_comments** (y pages_read_engagement).
  Regenéralo en el Graph API Explorer y corre setup_meta.py, como con insights.
- Corre local o por cron (polling). No necesita servidor/webhook.

Uso:
  python3 comments.py --check                 # prueba token/scope
  python3 comments.py                          # DRY-RUN: clasifica y muestra
  python3 comments.py --post                   # publica las respuestas auto
  python3 comments.py --days 7 --niche epic-plane
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, re, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
GRAPH_VERSION = "v21.0"
BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
STATE_DIR = ROOT / "data" / "comments"

# --- palabras que OBLIGAN a escalar (no auto-responder) ---
PRICE_WORDS = ["precio", "cuánto", "cuanto", "vale", "valor", "cost", "$", "cotiz", "presupuesto"]
ORDER_WORDS = ["pedido", "encargar", "encargo", "comprar", "quiero uno", "quiero una", "reserva",
               "despacho", "envío", "envio", "delivery", "order", "buy", "how much", "dm", "mp"]
NEG_WORDS = ["malo", "mala", "pésimo", "pesimo", "asco", "horrible", "estafa", "reclamo", "queja",
             "nunca", "peor", "feo", "caro", "tarde", "no llegó", "no llego", "bad", "worst", "scam", "refund"]
POSITIVE_HINTS = ["hermosa", "hermoso", "linda", "lindo", "bella", "bello", "genial", "increíble",
                  "increible", "espectacular", "wow", "amo", "amor", "me encanta", "encanta",
                  "beautiful", "amazing", "love", "gorgeous", "stunning", "epic",
                  "🔥", "😍", "❤️", "🤎", "👏", "✈️", "🙌", "😱", "👌", "💯"]

# --- plantillas de respuesta para POSITIVOS SIMPLES (rotan; sin IA) ---
TEMPLATES = {
    "epic-plane": [
        "Glad you love it! ✈️", "Right?? 😍", "Appreciate you! 🙌", "Same here — never gets old ✈️",
        "Thanks for the love 🙏✈️", "This one's a beauty 😍", "Couldn't agree more 🔥",
    ],
    "rossacuore": [
        "¡Gracias! 🤎", "Nos alegra que te guste ✨", "Hecha con dedicación 🤎",
        "Gracias por el cariño 🙌", "Un gusto que la disfrutes ✨",
    ],
    "_default": ["¡Gracias! 🙌", "Nos alegra que te guste ✨", "Appreciate you! 🙏"],
}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    for key in ("IG_USER_ID", "META_PAGE_TOKEN"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def _request(method: str, path: str, params: dict[str, str]) -> dict:
    url = f"{BASE}/{path}"
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        url = url + "?" + data.decode()
        req = urllib.request.Request(url, method="GET")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            msg = body
        raise RuntimeError(f"Graph API /{path}: {msg}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Sin conexión con la Graph API: {e}") from None


def classify(text: str) -> tuple[str, str]:
    """Devuelve (accion, razon): 'auto' (positivo simple) o 'escalate'."""
    t = (text or "").strip().lower()
    if not t:
        return "escalate", "vacío/solo media"
    if "?" in t or "¿" in t:
        return "escalate", "es una pregunta"
    for w in PRICE_WORDS:
        if w in t:
            return "escalate", "menciona precio/cotización"
    for w in ORDER_WORDS:
        if w in t:
            return "escalate", "intención de pedido/compra"
    for w in NEG_WORDS:
        if w in t:
            return "escalate", "posible reclamo/negativo"
    # largo o con mención/etiqueta compleja -> mejor humano
    if len(t) > 120:
        return "escalate", "comentario largo"
    if any(h for h in POSITIVE_HINTS if isinstance(h, str) and h in t):
        return "auto", "positivo simple"
    # corto y neutro (ej. '✈️', 'jaja', 'top') -> auto suave
    if len(t) <= 25:
        return "auto", "corto/neutro"
    return "escalate", "ambiguo"


def pick_reply(niche: str, seed: int) -> str:
    opts = TEMPLATES.get(niche, TEMPLATES["_default"])
    return opts[seed % len(opts)]


def _state_path(niche: str) -> Path:
    return STATE_DIR / f"replied-{niche}.json"


def load_state(niche: str) -> set:
    p = _state_path(niche)
    if p.exists():
        try:
            return set(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_state(niche: str, replied: set) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_path(niche).write_text(json.dumps(sorted(replied), ensure_ascii=False, indent=2), encoding="utf-8")


def recent_media(ig_id: str, token: str, limit: int) -> list[dict]:
    r = _request("GET", ig_id + "/media",
                 {"fields": "id,caption,timestamp,media_type", "limit": str(limit), "access_token": token})
    return r.get("data", [])


def media_comments(media_id: str, token: str) -> list[dict]:
    r = _request("GET", media_id + "/comments",
                 {"fields": "id,text,username,timestamp", "limit": "50", "access_token": token})
    return r.get("data", [])


def reply_to(comment_id: str, token: str, message: str) -> str:
    r = _request("POST", comment_id + "/replies", {"message": message, "access_token": token})
    return r.get("id", "")


def cmd_check(env) -> None:
    ig, token = env.get("IG_USER_ID"), env.get("META_PAGE_TOKEN")
    if not ig or not token:
        sys.exit("Faltan IG_USER_ID / META_PAGE_TOKEN en .env")
    try:
        media = recent_media(ig, token, 1)
        print(f"✓ Token lee media ({len(media)} post reciente).")
    except RuntimeError as e:
        sys.exit(f"✗ No pude leer media: {e}")
    if media:
        try:
            media_comments(media[0]["id"], token)
            print("✓ Token puede LEER comentarios.")
        except RuntimeError as e:
            print(f"⚠️  No puedo leer comentarios: {e}\n   Agrega el scope instagram_manage_comments (Graph API Explorer + setup_meta.py).")
    print("Nota: para PUBLICAR respuestas necesitas instagram_manage_comments. Prueba con --post en 1 comentario.")


def run(env, niche: str, days: int, media_limit: int, do_post: bool) -> None:
    ig, token = env.get("IG_USER_ID"), env.get("META_PAGE_TOKEN")
    if not ig or not token:
        sys.exit("Faltan IG_USER_ID / META_PAGE_TOKEN en .env")
    replied = load_state(niche)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    media = recent_media(ig, token, media_limit)
    auto, escalate = [], []
    seed = len(replied)
    for m in media:
        try:
            comments = media_comments(m["id"], token)
        except RuntimeError as e:
            print(f"  ⚠️ {m['id']}: {e}")
            continue
        for c in comments:
            cid = c.get("id")
            if not cid or cid in replied:
                continue
            if (c.get("username") or "").lower() in ("epic.plane", niche):
                continue  # no responder a nosotros mismos
            action, reason = classify(c.get("text", ""))
            if action == "auto":
                msg = pick_reply(niche, seed); seed += 1
                auto.append({"cid": cid, "user": c.get("username"), "text": c.get("text"), "reply": msg})
            else:
                escalate.append({"cid": cid, "user": c.get("username"), "text": c.get("text"), "reason": reason})

    print(f"\n=== COMENTARIOS ({niche}) — {len(auto)} auto · {len(escalate)} a escalar ===")
    print("\n🟢 AUTO (positivos simples):")
    for a in auto:
        print(f"  @{a['user']}: {a['text'][:60]!r}  →  {a['reply']!r}")
    print("\n🟠 ESCALAR (los revisa un humano):")
    for e in escalate:
        print(f"  @{e['user']}: {e['text'][:70]!r}  [{e['reason']}]")

    # guarda la cola de escalados para el humano
    if escalate:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        qp = STATE_DIR / f"escalate-{niche}-{dt.date.today().isoformat()}.json"
        qp.write_text(json.dumps(escalate, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  📥 Cola de escalados guardada en {qp}")

    if not do_post:
        print("\n(DRY-RUN — nada publicado. Usa --post para responder los AUTO.)")
        return

    print("\n→ Publicando respuestas AUTO…")
    done = 0
    for a in auto:
        try:
            reply_to(a["cid"], token, a["reply"])
            replied.add(a["cid"]); done += 1
            print(f"  ✓ respondido a @{a['user']}")
        except RuntimeError as e:
            print(f"  ✗ @{a['user']}: {e}")
    save_state(niche, replied)
    print(f"✓ {done} respuestas publicadas. Estado actualizado.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Community Manager — responder comentarios de Instagram.")
    ap.add_argument("--niche", default="epic-plane", help="Cliente/nicho (voz de las plantillas).")
    ap.add_argument("--days", type=int, default=7, help="Ventana de posts recientes.")
    ap.add_argument("--media-limit", type=int, default=8, help="Cuántos posts recientes revisar.")
    ap.add_argument("--post", action="store_true", help="Publica de verdad (sin esto, DRY-RUN).")
    ap.add_argument("--check", action="store_true", help="Prueba token/scope y sale.")
    args = ap.parse_args()
    env = load_env()
    if args.check:
        cmd_check(env); return
    run(env, args.niche, args.days, args.media_limit, args.post)


if __name__ == "__main__":
    main()
