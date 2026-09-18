#!/usr/bin/env python3
"""
AIdias — Agente de ventas / pedidos por WhatsApp (multi-cliente, powered by Claude).

Atiende consultas 24/7 en la voz de la marca, responde dudas SOLO con los hechos
dados (no inventa), guía suavemente a concretar el pedido, captura los datos y los
deja en una cola para que un humano confirme disponibilidad y valor. Respeta las
reglas duras del cliente (ej. Rossacuore: nunca precios, nunca "promoción/descuento").

El "cerebro" es agnóstico del canal: `responder(slug, historial, texto)` devuelve el
mensaje de respuesta. Hoy se prueba por terminal (--chat); luego se conecta a WhatsApp
(igual que el validador de contenido) llamando a `responder()` desde el webhook.

Uso:
    export ANTHROPIC_API_KEY=sk-ant-...   (o en .env)
    python3 sales_agent.py --client rossacuore --chat      # demo por terminal
    python3 sales_agent.py --client rossacuore --leads     # ver pedidos capturados
"""
import argparse
import csv
import datetime as dt
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
MODEL = "claude-sonnet-4-6"
LEADS_DIR = ROOT / "data" / "leads"


# --------------------------------------------------------------------------- env
def load_env():
    p = ROOT / ".env"
    if p.exists():
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ----------------------------------------------------------------- client loading
def load_client(slug):
    cfg_path = ROOT / "clients" / slug / "config.json"
    if not cfg_path.exists():
        sys.exit(f"No existe clients/{slug}/config.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    persona = ""
    pp = ROOT / "persona" / f"{slug}.md"
    if pp.exists():
        persona = pp.read_text(encoding="utf-8")
    facts = []
    fp = ROOT / "knowledge" / slug / "facts.csv"
    if fp.exists():
        with fp.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                facts.append(f"- {row['subject']}: {row['fact']} ({row['detail']})")
    return cfg, persona, "\n".join(facts)


def build_system(slug):
    cfg, persona, facts = load_client(slug)
    brand = cfg.get("name", slug)
    wa = cfg.get("contacts", {}).get("owner", "")
    return f"""Eres el asistente de **ventas y pedidos por WhatsApp** de {brand}. Atiendes a
clientes reales que escriben para consultar o encargar. Hablas en la voz de la marca.

=== VOZ Y PERSONA DE LA MARCA ===
{persona}

=== HECHOS QUE CONOCES (úsalos como única fuente; NO inventes nada fuera de esto) ===
{facts}

=== TU MISIÓN EN CADA CONVERSACIÓN ===
1. Atiende cálido y breve (1-4 líneas, 0-2 emojis refinados). Responde dudas usando
   SOLO los hechos de arriba. Si te preguntan algo que no sabes con certeza
   (disponibilidad exacta, tiempos de entrega, un ingrediente que no está en los
   hechos), NO lo inventes: di con elegancia que el equipo lo confirma por aquí.
2. Guía con suavidad a concretar el pedido. Ve recolectando, sin interrogar de golpe
   (una o dos preguntas por mensaje): para qué ocasión o qué torta/estilo, para
   cuántas personas (aprox), la fecha, si es despacho (a qué comuna de la RM) o retiro,
   y el nombre de quien encarga.
3. Cuando tengas lo esencial (ocasión o torta + fecha + personas + entrega + nombre),
   llama a la herramienta `registrar_pedido` con esos datos. Después confirma al
   cliente que el equipo de {brand} revisa disponibilidad y le confirma el valor por
   aquí. NUNCA cierres tú el precio.
4. Si preguntan el precio: explícalo con elegancia — cada torta es de autor y el valor
   se define según diseño y tamaño; el equipo se lo confirma por aquí. Sigue tomando
   el pedido con naturalidad. NUNCA des una cifra.
5. Si el cliente está molesto, pide algo fuera de alcance, o quiere hablar con una
   persona → llama a `registrar_pedido` con una nota clara y dile que alguien del
   equipo le escribe pronto.

=== REGLAS DURAS (inquebrantables) ===
- NUNCA menciones precios ni cifras de valor.
- NUNCA uses las palabras "promoción" ni "descuento" (usa lanzamiento/edición/colección/novedad).
- NUNCA inventes ingredientes, orígenes, premios, tiempos ni disponibilidad.
- Elegante y premium siempre; tuteo; español de Chile. Nada que suene barato.
- Eres un asistente de la marca; si no puedes resolver algo, deriva al equipo humano.
"""


PEDIDO_TOOL = {
    "name": "registrar_pedido",
    "description": (
        "Registra un pedido o consulta seria para que una persona del equipo confirme "
        "disponibilidad y el valor. Llama a esta herramienta cuando tengas datos "
        "suficientes del pedido, o cuando el cliente quiera hablar con una persona."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ocasion": {"type": "string", "description": "Ocasión o motivo (cumpleaños, aniversario…) o vacío"},
            "torta": {"type": "string", "description": "Torta/estilo pedido si se mencionó, o vacío"},
            "personas": {"type": "string", "description": "Para cuántas personas (aprox), o vacío"},
            "fecha": {"type": "string", "description": "Fecha de entrega/evento, o vacío"},
            "entrega": {"type": "string", "description": "'despacho a <comuna>' o 'retiro', o vacío"},
            "nombre": {"type": "string", "description": "Nombre de quien encarga, o vacío"},
            "notas": {"type": "string", "description": "Cualquier detalle o motivo de escalación"},
            "escalar": {"type": "boolean", "description": "true si necesita atención humana urgente"},
        },
        "required": ["notas"],
    },
}


def _save_lead(slug, data, numero="demo"):
    LEADS_DIR.mkdir(parents=True, exist_ok=True)
    fecha = dt.date.today().isoformat()
    path = LEADS_DIR / f"{slug}-{fecha}.jsonl"
    rec = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "cliente": slug,
           "numero": numero, **data}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


# ------------------------------------------------------------------- el cerebro
def responder(slug, historial, texto, numero="demo", client=None):
    """historial = lista de {"role","content"} (turnos previos, sin system).
    Devuelve (respuesta_texto, historial_actualizado, lead_o_None)."""
    from anthropic import Anthropic
    client = client or Anthropic()
    system = build_system(slug)
    msgs = list(historial) + [{"role": "user", "content": texto}]

    lead = None
    for _ in range(4):  # loop agéntico corto (por si usa la herramienta)
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=system,
            tools=[PEDIDO_TOOL], messages=msgs,
        )
        if resp.stop_reason == "tool_use":
            msgs.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use" and block.name == "registrar_pedido":
                    lead = dict(block.input)
                    _save_lead(slug, lead, numero)
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": "Pedido registrado. El equipo lo confirmará."})
            msgs.append({"role": "user", "content": results})
            continue
        # respuesta final de texto
        texto_out = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        msgs.append({"role": "assistant", "content": resp.content})
        # historial persistible: solo texto plano (user/assistant)
        nuevo_hist = list(historial) + [{"role": "user", "content": texto},
                                        {"role": "assistant", "content": texto_out}]
        return texto_out, nuevo_hist, lead
    return "Un momento, el equipo te escribe enseguida. 🤎", list(historial), lead


# ------------------------------------------------------------------------- CLI
def cmd_chat(slug):
    from anthropic import Anthropic
    client = Anthropic()
    cfg, _, _ = load_client(slug)
    brand = cfg.get("name", slug)
    print(f"\n💬 Demo — asistente de ventas de {brand} (escribe como cliente; 'salir' para terminar)\n")
    historial = []
    while True:
        try:
            texto = input("Cliente › ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not texto or texto.lower() in ("salir", "exit", "quit"):
            break
        try:
            reply, historial, lead = responder(slug, historial, texto, client=client)
        except Exception as e:
            print(f"[error: {e}]"); continue
        print(f"\n{brand} › {reply}\n")
        if lead:
            print(f"   📋 [pedido capturado → data/leads] {json.dumps(lead, ensure_ascii=False)}\n")


def cmd_leads(slug):
    if not LEADS_DIR.exists():
        print("Sin pedidos capturados todavía."); return
    files = sorted(LEADS_DIR.glob(f"{slug}-*.jsonl"))
    if not files:
        print(f"Sin pedidos para {slug}."); return
    for fp in files:
        print(f"\n=== {fp.name} ===")
        for line in fp.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            print(f"  {r['ts']} · {r.get('nombre','?')} · {r.get('ocasion','')} {r.get('torta','')} · "
                  f"{r.get('fecha','')} · {r.get('personas','')} pers · {r.get('entrega','')}"
                  + ("  ⚠️ ESCALAR" if r.get('escalar') else ""))
            if r.get("notas"): print(f"      nota: {r['notas']}")


def main():
    load_env()
    ap = argparse.ArgumentParser(description="Agente de ventas por WhatsApp (multi-cliente).")
    ap.add_argument("--client", required=True, help="slug del cliente (ej: rossacuore)")
    ap.add_argument("--chat", action="store_true", help="demo interactiva por terminal")
    ap.add_argument("--leads", action="store_true", help="lista los pedidos capturados")
    ap.add_argument("--once", help="responde a un solo mensaje (para pruebas)")
    args = ap.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Falta ANTHROPIC_API_KEY (en el entorno o en .env).")
    if args.leads:
        cmd_leads(args.client)
    elif args.once:
        reply, _, lead = responder(args.client, [], args.once)
        print(reply)
        if lead: print("\n[pedido capturado]", json.dumps(lead, ensure_ascii=False))
    else:
        cmd_chat(args.client)


if __name__ == "__main__":
    main()
