#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dms.py — Community Manager: atención de DMs de Instagram.

Modelo seguro para mensajes PRIVADOS (más delicados que comentarios):
- NO auto-inventa respuestas a pedidos/consultas.
- Envía UN acuse instantáneo, cálido y en la voz de la marca, que **deriva a
  WhatsApp** (para pedidos) y avisa que un humano responde a la brevedad.
- **Escala** el contenido real del DM a la cola humana (data/comments/).
- Respeta la ventana de 24h de Meta (solo responde DMs recientes).
- Guarda las conversaciones ya saludadas para no re-saludar.

Requisitos:
- Token de Página con scope **instagram_manage_messages** (regenéralo en el Graph
  API Explorer + setup_meta.py, como con los comentarios).
- IG_USER_ID / META_PAGE_TOKEN del cliente en .env.

Uso:
  python3 dms.py --check                 # prueba que el token puede leer DMs
  python3 dms.py                          # DRY-RUN: muestra qué haría
  python3 dms.py --post                   # envía los acuses de verdad
  python3 dms.py --client rossacuore --post
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
GRAPH_VERSION = "v21.0"
BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
STATE_DIR = ROOT / "data" / "dms"
WINDOW_HOURS = 24  # política de mensajería de Meta

# Acuse por cliente (voz de la marca). {wa} = link de WhatsApp de la bio.
ACK = {
    "epic-plane": "Thanks for the message! ✈️ We read every DM — we'll get back to you shortly. 🙌",
    "rossacuore": "¡Hola! Gracias por escribir a Rossacuore 🤎 Para encargos y consultas te "
                  "atendemos por WhatsApp (link en la bio) y un humano te responde a la brevedad ✨",
    "_default": "¡Gracias por tu mensaje! Te respondemos a la brevedad 🙌",
}


def load_env(extra_keys=None) -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    keys = {"IG_USER_ID", "META_PAGE_TOKEN"} | set(extra_keys or ())
    for key in keys:
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def load_client(slug: str) -> dict:
    path = ROOT / "clients" / slug / "config.json"
    if not path.exists():
        return {"ig_env": "IG_USER_ID", "token_env": "META_PAGE_TOKEN", "brand": slug}
    cfg = json.loads(path.read_text(encoding="utf-8"))
    ig = (cfg.get("channels", {}).get("instagram", {}) or {})
    return {
        "brand": cfg.get("name", slug),
        "ig_env": ig.get("ig_user_id_env", "IG_USER_ID"),
        "token_env": ig.get("token_env", "META_PAGE_TOKEN"),
    }


def _request(method: str, path: str, params: dict, json_body: dict | None = None) -> dict:
    url = f"{BASE}/{path}"
    if method == "GET":
        url = url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="GET")
    else:
        url = url + "?" + urllib.parse.urlencode(params)
        data = json.dumps(json_body or {}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
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


def conversations(ig_id: str, token: str) -> list[dict]:
    r = _request("GET", f"{ig_id}/conversations",
                 {"platform": "instagram", "fields": "id,updated_time", "access_token": token})
    return r.get("data", [])


def messages(convo_id: str, token: str) -> list[dict]:
    r = _request("GET", convo_id,
                 {"fields": "messages{id,from,message,created_time}", "access_token": token})
    return (r.get("messages", {}) or {}).get("data", [])


def send_dm(ig_id: str, token: str, recipient_id: str, text: str) -> str:
    r = _request("POST", f"{ig_id}/messages",
                 {"access_token": token},
                 json_body={"recipient": {"id": recipient_id}, "message": {"text": text}})
    return r.get("message_id", "ok")


def _state_path(slug: str) -> Path:
    return STATE_DIR / f"greeted-{slug}.json"


def load_state(slug: str) -> set:
    p = _state_path(slug)
    if p.exists():
        try:
            return set(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_state(slug: str, greeted: set) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_path(slug).write_text(json.dumps(sorted(greeted), ensure_ascii=False, indent=2), encoding="utf-8")


def _recent(ts: str) -> bool:
    try:
        t = dt.datetime.fromisoformat(ts.replace("+0000", "+00:00"))
        return (dt.datetime.now(dt.timezone.utc) - t) <= dt.timedelta(hours=WINDOW_HOURS)
    except Exception:
        return False


def cmd_check(ig_id, token) -> None:
    try:
        convos = conversations(ig_id, token)
        print(f"✓ Token puede LEER DMs ({len(convos)} conversaciones).")
        print("  Para ENVIAR necesitas instagram_manage_messages; prueba --post en 1 DM reciente.")
    except RuntimeError as e:
        print(f"✗ No pude leer DMs: {e}")
        print("  Agrega el scope instagram_manage_messages (Graph API Explorer + setup_meta.py).")


def run(slug, ig_id, token, do_post) -> None:
    greeted = load_state(slug)
    ack = ACK.get(slug, ACK["_default"])
    to_greet, escalate = [], []
    try:
        convos = conversations(ig_id, token)
    except RuntimeError as e:
        sys.exit(f"No pude leer conversaciones: {e}\n(¿Falta el scope instagram_manage_messages?)")
    for cv in convos:
        cid = cv.get("id")
        try:
            msgs = messages(cid, token)
        except RuntimeError:
            continue
        # último mensaje entrante (no nuestro)
        inbound = [m for m in msgs if str(m.get("from", {}).get("id")) != str(ig_id)]
        if not inbound:
            continue
        last = inbound[0]  # la API los da del más nuevo al más viejo
        if not _recent(last.get("created_time", "")):
            continue
        sender = last.get("from", {}).get("id")
        key = f"{cid}:{sender}"
        if key in greeted:
            continue
        to_greet.append({"cid": cid, "sender": sender, "text": last.get("message", ""), "key": key})
        escalate.append({"user_id": sender, "text": last.get("message", ""), "at": last.get("created_time")})

    print(f"\n=== DMs ({slug}) — {len(to_greet)} por saludar/derivar ===")
    for g in to_greet:
        print(f"  de {g['sender']}: {g['text'][:60]!r}  →  acuse+WhatsApp")
    if escalate:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        qp = STATE_DIR / f"escalate-{slug}-{dt.date.today().isoformat()}.json"
        qp.write_text(json.dumps(escalate, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  📥 Cola humana guardada en {qp}")

    if not do_post:
        print("\n(DRY-RUN — nada enviado. Usa --post para enviar los acuses.)")
        return

    done = 0
    for g in to_greet:
        try:
            send_dm(ig_id, token, g["sender"], ack)
            greeted.add(g["key"]); done += 1
            print(f"  ✓ acuse enviado a {g['sender']}")
        except RuntimeError as e:
            print(f"  ✗ {g['sender']}: {e}")
    save_state(slug, greeted)
    print(f"✓ {done} acuses enviados. Estado actualizado.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Community Manager — DMs de Instagram (acuse + derivar + escalar).")
    ap.add_argument("--client", default="epic-plane", help="Cliente/slug.")
    ap.add_argument("--post", action="store_true", help="Envía de verdad (sin esto, DRY-RUN).")
    ap.add_argument("--check", action="store_true", help="Prueba lectura de DMs y sale.")
    args = ap.parse_args()
    client = load_client(args.client)
    env = load_env(extra_keys=(client["ig_env"], client["token_env"]))
    ig_id, token = env.get(client["ig_env"]), env.get(client["token_env"])
    if not ig_id or not token:
        sys.exit(f"Faltan {client['ig_env']}/{client['token_env']} en .env para '{args.client}'.")
    if args.check:
        cmd_check(ig_id, token); return
    run(args.client, ig_id, token, args.post)


if __name__ == "__main__":
    main()
