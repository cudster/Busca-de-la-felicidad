"""Validador de contenido por WhatsApp — EMISOR.

Manda al cliente cada post pendiente de su Google Sheet como un mensaje de
WhatsApp con el caption completo + una lista interactiva de 4 acciones
(Aprobar / Modificar / Descartar / Rechazar).

La gracia: la acción y el post van CODIFICADOS en el id de cada fila de la
lista —`apr|<slug>|<post_id>|<accion>`—, así cuando el cliente responde, el
receptor (parche del webhook de Jarvis) sabe exactamente qué fila del Sheet
tocar, sin guardar estado.

El Sheet sigue siendo la fuente de verdad: esto solo lo alimenta a distancia.
publish.py publica lo que quede con approved=TRUE, igual que hoy.

Uso:
    # prueba: manda el primer pendiente a tu propio número
    python3 whatsapp_aprobacion.py --client rossacuore --to <numero> --limit 1
    # tanda diaria: manda todos los pendientes
    python3 whatsapp_aprobacion.py --client rossacuore --to <numero>

Credenciales de WhatsApp (Cloud API): toma WA_TOKEN y WA_PHONE_NUMBER_ID del
entorno; si no están, las lee de la .env de Jarvis (~/Downloads/jarvis-whatsapp).
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

import sheets

GRAPH = "https://graph.facebook.com/v21.0"

# Etiquetas de la lista interactiva. WhatsApp: título de fila <= 24 chars,
# descripción <= 72, id <= 200.
ACCIONES = [
    ("aprobar", "✅ Aprobar", "Publicar tal cual en su fecha"),
    ("modificar", "✏️ Modificar", "Quiero un cambio (te lo escribo)"),
    ("descartar", "🗑️ Descartar", "No publicar este post"),
    ("rechazar", "❌ Rechazar", "No me gusta, genera otro"),
]

JARVIS_ENV = pathlib.Path.home() / "Downloads" / "jarvis-whatsapp" / ".env"


def _wa_creds():
    token = os.environ.get("WA_TOKEN", "")
    phone_id = os.environ.get("WA_PHONE_NUMBER_ID", "")
    if (not token or not phone_id) and JARVIS_ENV.exists():
        for linea in JARVIS_ENV.read_text().splitlines():
            if linea.startswith("WA_TOKEN=") and not token:
                token = linea.split("=", 1)[1].strip()
            elif linea.startswith("WA_PHONE_NUMBER_ID=") and not phone_id:
                phone_id = linea.split("=", 1)[1].strip()
    if not token or not phone_id:
        sys.exit("Faltan WA_TOKEN / WA_PHONE_NUMBER_ID (en el entorno o en la .env de Jarvis).")
    return token, phone_id


def _subir_media(phone_id, token, ruta):
    """Sube un archivo local a la Cloud API y devuelve su media_id."""
    import mimetypes
    import uuid

    datos = pathlib.Path(ruta).read_bytes()
    mime = mimetypes.guess_type(ruta)[0] or "image/jpeg"
    frontera = uuid.uuid4().hex
    nl = b"\r\n"
    cuerpo = b"".join([
        b"--" + frontera.encode() + nl,
        b'Content-Disposition: form-data; name="messaging_product"' + nl + nl,
        b"whatsapp" + nl,
        b"--" + frontera.encode() + nl,
        b'Content-Disposition: form-data; name="type"' + nl + nl,
        mime.encode() + nl,
        b"--" + frontera.encode() + nl,
        b'Content-Disposition: form-data; name="file"; filename="' + pathlib.Path(ruta).name.encode() + b'"' + nl,
        b"Content-Type: " + mime.encode() + nl + nl,
        datos + nl,
        b"--" + frontera.encode() + b"--" + nl,
    ])
    req = urllib.request.Request(
        f"{GRAPH}/{phone_id}/media",
        data=cuerpo,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={frontera}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["id"]
    except urllib.error.HTTPError as e:
        sys.exit(f"WhatsApp media error {e.code}: {e.read().decode(errors='replace')}")


def _resolver_imagen(row):
    """Devuelve ('url', valor) | ('local', ruta) | None según asset_path/media_url."""
    for campo in ("media_url", "asset_path"):
        v = str(row.get(campo, "")).strip()
        if not v:
            continue
        if v.startswith("http://") or v.startswith("https://"):
            return ("url", v)
        p = pathlib.Path(v)
        if not p.is_absolute():
            p = pathlib.Path.cwd() / v
        if p.exists():
            return ("local", str(p))
    return None


def enviar_imagen(to, phone_id, token, imagen, caption):
    """Manda una imagen (por url o subiendo un archivo local) con caption."""
    tipo, valor = imagen
    if tipo == "url":
        img = {"link": valor}
    else:
        img = {"id": _subir_media(phone_id, token, valor)}
    if caption:
        img["caption"] = caption[:1024]
    _post(phone_id, token, {
        "messaging_product": "whatsapp", "to": to, "type": "image", "image": img,
    })


def _post(phone_id, token, payload):
    req = urllib.request.Request(
        f"{GRAPH}/{phone_id}/messages",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detalle = e.read().decode(errors="replace")
        sys.exit(f"WhatsApp API error {e.code}: {detalle}")


def _tipo_es(t):
    return {"image": "📷 Foto", "reel": "🎬 Reel", "carousel": "🎠 Carrusel"}.get(t, t)


def formatear_cuerpo(row, niche):
    """Arma el texto del mensaje: encabezado + caption + hashtags."""
    caption = (row.get("caption_es") or row.get("caption_en") or "").strip()
    hashtags = (row.get("hashtags") or "").strip()
    partes = [
        f"*{row.get('id','')}*  ·  {row.get('date','')}  ·  {_tipo_es(row.get('type',''))}",
        "",
        caption,
    ]
    if hashtags:
        partes += ["", hashtags]
    return "\n".join(partes)


def enviar_para_aprobar(to, niche, row, phone_id, token, marca="", demo_img=None):
    """Manda un post para aprobar. Si hay imagen: foto+caption y luego la lista.

    Devuelve el wa message id de la lista interactiva.
    """
    post_id = row.get("id", "")
    header = (marca or niche).strip()[:60]

    # 1) Imagen con el caption completo (para verlo antes de decidir).
    imagen = _resolver_imagen(row)
    if imagen is None and demo_img:
        imagen = ("local", demo_img) if not demo_img.startswith("http") else ("url", demo_img)
    if imagen is not None:
        enviar_imagen(to, phone_id, token, imagen, formatear_cuerpo(row, niche))
        cuerpo_lista = f"👆 {post_id} · {row.get('date','')} · {_tipo_es(row.get('type',''))}\n¿Qué hacemos con este post?"
    else:
        # Sin imagen: el texto completo va en la lista.
        cuerpo_lista = formatear_cuerpo(row, niche)

    # 2) Lista interactiva con las 4 acciones.
    filas = [
        {"id": f"apr|{niche}|{post_id}|{accion}", "title": titulo, "description": desc}
        for accion, titulo, desc in ACCIONES
    ]
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": f"📋 {header} — revisión"},
            "body": {"text": cuerpo_lista},
            "footer": {"text": "Elige una acción abajo 👇"},
            "action": {
                "button": "Responder",
                "sections": [{"title": "¿Qué hacemos?", "rows": filas}],
            },
        },
    }
    resp = _post(phone_id, token, payload)
    return resp.get("messages", [{}])[0].get("id", "")


def _load_client(slug):
    p = pathlib.Path("clients") / slug / "config.json"
    if not p.exists():
        sys.exit(f"No existe clients/{slug}/config.json")
    return json.loads(p.read_text())


def _sheet_id_de_cliente(cfg):
    env_key = (
        cfg.get("channels", {}).get("instagram", {}).get("sheet_id_env")
        or "SHEET_ID"
    )
    sid = os.environ.get(env_key, "")
    if not sid and pathlib.Path(".env").exists():
        for linea in pathlib.Path(".env").read_text().splitlines():
            if linea.startswith(f"{env_key}="):
                sid = linea.split("=", 1)[1].strip()
                break
    if not sid:
        sys.exit(f"No encuentro el Sheet ID (env {env_key}).")
    return sid


def enviar_pendientes(slug, to, limit=None, solo=None, demo_img=None):
    cfg = _load_client(slug)
    marca = cfg.get("name", slug)
    sheet_id = _sheet_id_de_cliente(cfg)
    token, phone_id = _wa_creds()

    sp, ws = sheets.get_worksheet(sheet_id)
    filas = ws.get_all_records()
    _si = ("true", "sí", "si", "1", "aprobado", "aprobada")
    pendientes = [
        r for r in filas
        if str(r.get("approved", "")).strip().lower() not in _si
        and str(r.get("published", "")).strip().lower() not in _si
    ]
    if solo:
        pendientes = [r for r in pendientes if r.get("id") in solo]
    if limit:
        pendientes = pendientes[:limit]

    if not pendientes:
        print("No hay posts pendientes por aprobar. 🎉")
        return

    print(f"Enviando {len(pendientes)} post(s) a {to} para aprobación de {marca}…")
    for r in pendientes:
        mid = enviar_para_aprobar(to, slug, r, phone_id, token, marca=marca, demo_img=demo_img)
        print(f"  → {r.get('id')} enviado (wa_id={mid[:24]}…)")


def main():
    ap = argparse.ArgumentParser(description="Manda posts a aprobar por WhatsApp.")
    ap.add_argument("--client", required=True, help="slug del cliente (ej: rossacuore)")
    ap.add_argument("--to", required=True, help="número destino (dígitos, ej: 569XXXXXXXX)")
    ap.add_argument("--limit", type=int, default=None, help="máximo de posts a enviar")
    ap.add_argument("--only", default=None, help="ids separados por coma (ej: 2026-10-P01)")
    ap.add_argument("--demo-img", default=None, help="imagen de respaldo (ruta/URL) si el post no tiene asset")
    args = ap.parse_args()
    solo = [s.strip() for s in args.only.split(",")] if args.only else None
    enviar_pendientes(args.client, args.to.replace("+", "").strip(), args.limit, solo, args.demo_img)


if __name__ == "__main__":
    main()
