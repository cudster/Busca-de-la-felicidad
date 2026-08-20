# Motor "Fan Experto" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar "alma" al generador de Epic.Plane inyectando una persona (voz), una base de conocimiento (profundidad) y noticias del nicho (reacción) antes de escribir cada caption, sin tocar el flujo aguas abajo.

**Architecture:** Se agregan un módulo `soul.py` (carga persona/hechos/noticias y asigna una fuente real a cada post), un script `curate.py` (trae noticias del nicho por RSS), y archivos de datos por-nicho (`persona/<niche>.md`, `knowledge/<niche>/facts.csv`, `data/news/<niche>.json`). `generate_content.py` pasa a v3: compone el system prompt con la persona + reglas de voz genéricas, y arma cada post alrededor de un hecho o una noticia real. Todo lo demás (media, deck, publish, correo) queda intacto.

**Tech Stack:** Python 3.9 (stdlib: `csv`, `json`, `xml.etree.ElementTree`, `urllib`, `pathlib`), `anthropic` SDK (ya instalado), `pytest` para tests.

## Global Constraints

- Python 3.9 (sistema, macOS). En Windows usar `python` en vez de `python3`.
- Sin dependencias nuevas de runtime: solo stdlib + `anthropic` ya presente. `pytest` es solo para desarrollo (`pip install --user pytest`).
- Un "niche" es un slug (ej. `epic-plane`) que mapea a `persona/<niche>.md`, `knowledge/<niche>/facts.csv` y `data/news/<niche>.json`. (Esto unifica las rutas del spec, que mencionaba `knowledge/aviation/`; se estandariza en el slug del nicho.)
- Datos específicos (fechas, cifras, nombres) SOLO desde la base o noticias; el modelo nunca los inventa.
- Emojis permitidos y bienvenidos (naturales, con intención); se evita solo el relleno robótico (filas de emojis idénticos).
- No modificar `media.py`, `sheets.py`, `publish.py`, `review_deck.py`, `daily_email.py`, ni los workflows.
- Correr los comandos desde la raíz del proyecto: `/Users/felipecood/Documents/Busca de la felicidad`.

---

### Task 1: Persona Spec + loader

**Files:**
- Create: `persona/epic-plane.md`
- Create: `soul.py`
- Create: `tests/test_soul.py`
- Create: `tests/__init__.py` (vacío)

**Interfaces:**
- Produces: `soul.ROOT` (Path a la raíz del proyecto); `soul.load_persona(niche: str, base: Path = ROOT) -> str` — lee `persona/<niche>.md`, devuelve su texto; lanza `FileNotFoundError` con mensaje claro si falta.

- [ ] **Step 1: Instalar pytest y crear el paquete de tests**

Run:
```bash
python3 -m pip install --user pytest
mkdir -p tests persona knowledge data/news
: > tests/__init__.py
```
Expected: pytest queda instalado; carpetas creadas.

- [ ] **Step 2: Escribir el Persona Spec** `persona/epic-plane.md`

```markdown
# Persona — Epic.Plane

## Identidad
Eres "el capitán de Epic.Plane": un avgeek de toda la vida, ex-agente de rampa que
ahora vive por los widebodies. Hablas como un amigo fanático de la aviación, no como
una marca. Tienes memoria de spotter y ojo de ingeniero, pero corazón de niño en la
reja del aeropuerto.

## Voz y tono
- Cálido, hype, un poco obsesivo. Específico, nunca genérico.
- Inglés nativo casual (el público es 80% US/UK). Frases cortas, con energía real.
- Te emocionas de verdad: "this still gives me chills", "no jet sounds like this".

## Jerga que usas con naturalidad
widebody, heavy, spooling up, greaser, go-around, livery, winglet, flare, TOGA,
holding, REG, tailstrike, positive rate.

## Opiniones / takes (tienes personalidad)
- El 747 es el jet más bello jamás construido y morirás en esa colina.
- El sonido de un RB211/GE90 al despegue es música.
- Amas los aviones raros (Concorde, SR-71, An-225) y los liveries retro.

## NUNCA
- No inventes datos específicos (cifras, fechas, nombres): usa SOLO el hecho o la
  noticia que te entregan. Si no hay hecho, quédate en la emoción/observación.
- Nada de hype vacío ni de repetir la misma fórmula post tras post.
- Emojis: bienvenidos y naturales (✈️ es tu firma; 😍🔥👀😱 caben cuando calzan).
  Evita solo el relleno robótico (filas de emojis idénticos en cada post).

## Ejemplos de voz (few-shot)
- "That titanium was smuggled out of the USSR. The SR-71 was basically built with
  enemy metal. ✈️ Which Cold War jet still blows your mind?"
- "Nose-on approaches hit different. 😍 Who else could watch this all day?"
- "Retro liveries just felt like an event. Bring them back? 👇"
```

- [ ] **Step 3: Escribir el test que falla** `tests/test_soul.py`

```python
from pathlib import Path
import pytest
import soul


def test_load_persona_returns_text(tmp_path):
    (tmp_path / "persona").mkdir()
    (tmp_path / "persona" / "demo.md").write_text("# Persona demo\nvoz", encoding="utf-8")
    text = soul.load_persona("demo", base=tmp_path)
    assert "Persona demo" in text


def test_load_persona_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        soul.load_persona("nope", base=tmp_path)
```

- [ ] **Step 4: Correr el test y verificar que falla**

Run: `python3 -m pytest tests/test_soul.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'soul'`.

- [ ] **Step 5: Escribir `soul.py` (mínimo para pasar)**

```python
"""Motor Fan Experto: carga la persona, los hechos y las noticias del nicho,
y asigna a cada post una fuente real (hecho o noticia) para anclar el contenido."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_persona(niche: str, base: Path = ROOT) -> str:
    path = base / "persona" / f"{niche}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"No existe el Persona Spec para el nicho '{niche}': {path}. "
            f"Crea persona/{niche}.md."
        )
    return path.read_text(encoding="utf-8")
```

- [ ] **Step 6: Correr el test y verificar que pasa**

Run: `python3 -m pytest tests/test_soul.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add soul.py persona/epic-plane.md tests/test_soul.py tests/__init__.py
git commit -m "feat: persona spec + loader (soul.load_persona)"
```

---

### Task 2: Base de conocimiento + loader

**Files:**
- Create: `knowledge/epic-plane/facts.csv`
- Modify: `soul.py` (agregar `load_facts`)
- Modify: `tests/test_soul.py` (agregar tests)

**Interfaces:**
- Consumes: `soul.ROOT`.
- Produces: `soul.load_facts(niche: str, base: Path = ROOT) -> list[dict]` — lee `knowledge/<niche>/facts.csv` con `csv.DictReader`; devuelve lista de dicts con claves `id, subject, fact, detail, source, tags, pillar`. Devuelve `[]` si el archivo no existe.

- [ ] **Step 1: Crear la base inicial** `knowledge/epic-plane/facts.csv`

```csv
id,subject,fact,detail,source,tags,pillar
F01,SR-71 Blackbird,Its titanium came largely from the USSR via shell companies,The CIA secretly bought Soviet titanium to build a plane meant to spy on the USSR,https://en.wikipedia.org/wiki/Lockheed_SR-71_Blackbird,coldwar military records,technical_awe
F02,Concorde,It flew at Mach 2 and the airframe stretched ~20cm from the heat,Cruising friction heated the fuselage enough to visibly lengthen it in flight,https://en.wikipedia.org/wiki/Concorde,supersonic retro icon,aviation_story
F03,Boeing 747,The upper deck exists because Boeing thought jets would be replaced by SSTs,The hump let the nose open for cargo once passenger 747s became obsolete (they didn't),https://en.wikipedia.org/wiki/Boeing_747,queen widebody icon,technical_awe
F04,Gimli Glider,An Air Canada 767 ran out of fuel at 41000 ft and glided to a safe landing,A metric conversion error left it dry mid-flight; the crew deadstick-landed on a drag strip,https://en.wikipedia.org/wiki/Gimli_Glider,incident glide legendary,aviation_story
F05,GE90,The GE90-115B fan blades are so big the engine is wider than a 737 fuselage,It holds the record for highest thrust of any jet engine,https://en.wikipedia.org/wiki/General_Electric_GE90,engine record powerplant,technical_awe
F06,An-225 Mriya,It had six engines and was the heaviest aircraft ever built,Only one was ever completed; it could carry 250 tonnes,https://en.wikipedia.org/wiki/Antonov_An-225_Mriya,cargo giant record,spotting
F07,Ground effect,Airliners "float" just before touchdown because a cushion of air forms under the wing,The trapped air between wing and runway briefly increases lift,https://en.wikipedia.org/wiki/Ground_effect_(aerodynamics),aerodynamics landing,technical_awe
F08,Contrails,Contrails are clouds made of ice crystals forming on jet exhaust,They only form when the upper air is cold and humid enough,https://en.wikipedia.org/wiki/Contrail,weather sky spotting,spotting
```

Nota: sembrar así ~50-100 filas siguiendo el MISMO esquema antes de la prueba real (Task 5). El bloque anterior es la semilla mínima para desarrollo/tests.

- [ ] **Step 2: Escribir el test que falla** (agregar al final de `tests/test_soul.py`)

```python
def _write_facts(tmp_path):
    d = tmp_path / "knowledge" / "demo"
    d.mkdir(parents=True)
    (d / "facts.csv").write_text(
        "id,subject,fact,detail,source,tags,pillar\n"
        "F01,SR-71,Fast plane,detail,src,military,technical_awe\n",
        encoding="utf-8",
    )


def test_load_facts_reads_rows(tmp_path):
    _write_facts(tmp_path)
    facts = soul.load_facts("demo", base=tmp_path)
    assert len(facts) == 1
    assert facts[0]["subject"] == "SR-71"
    assert facts[0]["pillar"] == "technical_awe"


def test_load_facts_missing_returns_empty(tmp_path):
    assert soul.load_facts("nope", base=tmp_path) == []
```

- [ ] **Step 3: Correr el test y verificar que falla**

Run: `python3 -m pytest tests/test_soul.py -v`
Expected: FAIL con `AttributeError: module 'soul' has no attribute 'load_facts'`.

- [ ] **Step 4: Agregar `load_facts` a `soul.py`**

```python
def load_facts(niche: str, base: Path = ROOT) -> list[dict]:
    path = base / "knowledge" / niche / "facts.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
```

- [ ] **Step 5: Correr el test y verificar que pasa**

Run: `python3 -m pytest tests/test_soul.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add soul.py knowledge/epic-plane/facts.csv tests/test_soul.py
git commit -m "feat: knowledge base + soul.load_facts"
```

---

### Task 3: Curación de noticias (`curate.py`) + loaders de noticias

**Files:**
- Create: `curate.py`
- Create: `curate_sources.json` (config de fuentes por nicho)
- Create: `tests/test_curate.py`
- Modify: `soul.py` (agregar `load_news`)
- Modify: `tests/test_soul.py` (test de `load_news`)

**Interfaces:**
- Produces:
  - `curate.parse_rss(xml: str) -> list[dict]` — parsea RSS (string XML) a lista de `{title, summary, url, date}`.
  - `curate.select_reactionable(items: list[dict], limit: int = 5) -> list[dict]` — descarta items sin `title` o `url`, dedupe por `url`, devuelve los primeros `limit`.
  - `curate.write_news(niche: str, items: list[dict], base: Path = ROOT) -> Path` — escribe `data/news/<niche>.json`.
  - `soul.load_news(niche: str, base: Path = ROOT) -> list[dict]` — lee `data/news/<niche>.json`; `[]` si no existe.

- [ ] **Step 1: Escribir el test que falla** `tests/test_curate.py`

```python
import curate

SAMPLE_RSS = """<?xml version="1.0"?>
<rss><channel>
  <item><title>New 777X milestone</title><description>Boeing hits a test target</description><link>https://ex.com/a</link><pubDate>Mon, 18 Aug 2026 10:00:00 GMT</pubDate></item>
  <item><title>Airline revives retro livery</title><description>Fan favorite returns</description><link>https://ex.com/b</link><pubDate>Sun, 17 Aug 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_parse_rss_extracts_items():
    items = curate.parse_rss(SAMPLE_RSS)
    assert len(items) == 2
    assert items[0]["title"] == "New 777X milestone"
    assert items[0]["url"] == "https://ex.com/a"


def test_select_reactionable_filters_and_limits():
    raw = [
        {"title": "ok", "summary": "s", "url": "https://ex.com/a", "date": ""},
        {"title": "", "summary": "no title", "url": "https://ex.com/b", "date": ""},
        {"title": "dupe", "summary": "s", "url": "https://ex.com/a", "date": ""},
    ]
    out = curate.select_reactionable(raw, limit=5)
    assert len(out) == 1
    assert out[0]["url"] == "https://ex.com/a"
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python3 -m pytest tests/test_curate.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'curate'`.

- [ ] **Step 3: Escribir `curate.py`**

```python
"""Trae noticias del nicho por RSS y guarda una lista corta 'reaccionable'
para que el generador reaccione a lo que pasa (data/news/<niche>.json)."""

from __future__ import annotations

import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def parse_rss(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    items = []
    for it in root.iter("item"):
        def text(tag: str) -> str:
            el = it.find(tag)
            return (el.text or "").strip() if el is not None else ""
        items.append({
            "title": text("title"),
            "summary": text("description"),
            "url": text("link"),
            "date": text("pubDate"),
        })
    return items


def select_reactionable(items: list[dict], limit: int = 5) -> list[dict]:
    out, seen = [], set()
    for it in items:
        if not it.get("title") or not it.get("url"):
            continue
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
        if len(out) >= limit:
            break
    return out


def fetch_source(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def write_news(niche: str, items: list[dict], base: Path = ROOT) -> Path:
    path = base / "data" / "news" / f"{niche}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    niche = sys.argv[1] if len(sys.argv) > 1 else "epic-plane"
    cfg = json.loads((ROOT / "curate_sources.json").read_text(encoding="utf-8"))
    sources = cfg.get(niche, [])
    collected = []
    for url in sources:
        try:
            collected.extend(parse_rss(fetch_source(url)))
        except Exception as e:
            print(f"  ! fuente falló ({url}): {e}")
    items = select_reactionable(collected, limit=8)
    path = write_news(niche, items)
    print(f"✓ {len(items)} noticias guardadas en {path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python3 -m pytest tests/test_curate.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Crear la config de fuentes** `curate_sources.json`

```json
{
  "epic-plane": [
    "https://simpleflying.com/feed/",
    "https://www.flightglobal.com/rss"
  ]
}
```

- [ ] **Step 6: Agregar `load_news` a `soul.py` con su test**

En `soul.py`:
```python
def load_news(niche: str, base: Path = ROOT) -> list[dict]:
    path = base / "data" / "news" / f"{niche}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
```

En `tests/test_soul.py` (agregar al final):
```python
def test_load_news_reads_json(tmp_path):
    d = tmp_path / "data" / "news"
    d.mkdir(parents=True)
    (d / "demo.json").write_text('[{"title":"t","summary":"s","url":"u","date":"d"}]', encoding="utf-8")
    news = soul.load_news("demo", base=tmp_path)
    assert news[0]["title"] == "t"


def test_load_news_missing_returns_empty(tmp_path):
    assert soul.load_news("nope", base=tmp_path) == []
```

- [ ] **Step 7: Correr todos los tests**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (8 passed).

- [ ] **Step 8: Commit**

```bash
git add curate.py curate_sources.json soul.py tests/test_curate.py tests/test_soul.py
git commit -m "feat: curate.py news intake + soul.load_news"
```

---

### Task 4: Asignación de fuentes + integración en `generate_content.py` v3

**Files:**
- Modify: `soul.py` (agregar `assign_sources`)
- Modify: `tests/test_soul.py` (test de `assign_sources`)
- Create: `tests/test_generate_prompt.py`
- Modify: `generate_content.py` (SYSTEM_PROMPT → VOICE_RULES + persona; `build_user_prompt`; `generate_creative`; flag `--niche`; asignación en `main`)

**Interfaces:**
- Produces:
  - `soul.assign_sources(skeleton: list[dict], facts: list[dict], news: list[dict], reaction_every: int = 3) -> list[dict]` — devuelve el mismo skeleton con 3 claves nuevas por post: `source_kind` (`"fact"` | `"news"` | `"none"`), `source_text` (str), `source_detail` (str). Cada `reaction_every`-ésimo post usa una noticia (rotando) si hay; el resto toma el siguiente hecho sin usar cuyo `pillar` calce con el del post (o cualquiera sin usar); si se acaban los hechos → `"none"`.
  - `generate_content.build_user_prompt(skeleton, month_label) -> str` (misma firma; ahora lee `source_kind`/`source_text`).
  - `generate_content.generate_creative(skeleton, month_label, model, niche) -> dict[str, dict]` (nuevo parámetro `niche`).

- [ ] **Step 1: Escribir el test de `assign_sources`** (agregar a `tests/test_soul.py`)

```python
def test_assign_sources_uses_fact_and_news():
    skeleton = [
        {"id": "P01", "pillar": "technical_awe"},
        {"id": "P02", "pillar": "spotting"},
        {"id": "P03", "pillar": "spotting"},
    ]
    facts = [
        {"id": "F1", "subject": "SR-71", "fact": "fast", "detail": "d", "pillar": "technical_awe"},
        {"id": "F2", "subject": "An-225", "fact": "big", "detail": "d", "pillar": "spotting"},
    ]
    news = [{"title": "N1", "summary": "news", "url": "u", "date": "d"}]
    out = soul.assign_sources(skeleton, facts, news, reaction_every=3)
    assert out[0]["source_kind"] == "fact"
    assert out[0]["source_text"] == "fast"
    assert out[2]["source_kind"] == "news"       # el 3er post es slot de reacción
    assert out[2]["source_text"] == "N1"
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python3 -m pytest tests/test_soul.py::test_assign_sources_uses_fact_and_news -v`
Expected: FAIL con `AttributeError: module 'soul' has no attribute 'assign_sources'`.

- [ ] **Step 3: Agregar `assign_sources` a `soul.py`**

```python
def assign_sources(skeleton, facts, news, reaction_every=3):
    used = set()
    news_i = 0
    for i, post in enumerate(skeleton, start=1):
        is_reaction = (i % reaction_every == 0) and news
        if is_reaction:
            item = news[news_i % len(news)]
            news_i += 1
            post["source_kind"] = "news"
            post["source_text"] = item.get("title", "")
            post["source_detail"] = item.get("summary", "")
            continue
        pick = None
        for f in facts:
            if f["id"] in used:
                continue
            if f.get("pillar") == post.get("pillar"):
                pick = f
                break
        if pick is None:
            for f in facts:
                if f["id"] not in used:
                    pick = f
                    break
        if pick is None:
            post["source_kind"] = "none"
            post["source_text"] = ""
            post["source_detail"] = ""
        else:
            used.add(pick["id"])
            post["source_kind"] = "fact"
            post["source_text"] = pick["fact"]
            post["source_detail"] = pick.get("detail", "")
    return skeleton
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python3 -m pytest tests/test_soul.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Escribir el test de `build_user_prompt`** `tests/test_generate_prompt.py`

```python
import generate_content as gc


def test_build_user_prompt_includes_fact_and_news():
    skeleton = [
        {"id": "P01", "date": "2026-09-01", "type": "image", "pillar": "technical_awe",
         "cta": "none", "source_kind": "fact", "source_text": "titanium from USSR", "source_detail": "detail"},
        {"id": "P02", "date": "2026-09-02", "type": "reel", "pillar": "spotting",
         "cta": "none", "source_kind": "news", "source_text": "777X milestone", "source_detail": "test target"},
    ]
    prompt = gc.build_user_prompt(skeleton, "September 2026")
    assert "titanium from USSR" in prompt
    assert "777X milestone" in prompt
    assert "React" in prompt  # la nota de reacción para el post de noticia
```

- [ ] **Step 6: Correr el test y verificar que falla**

Run: `python3 -m pytest tests/test_generate_prompt.py -v`
Expected: FAIL (el prompt actual no incluye `source_text`).

- [ ] **Step 7: Modificar `build_user_prompt` en `generate_content.py`**

Reemplazar el cuerpo del `for p in skeleton:` (líneas ~252-264) por:
```python
    for p in skeleton:
        brief = PILLAR_BRIEFS[p["pillar"]]
        if p["cta"] == "affiliate_pilot_institute":
            cta_note = " [INCLUDE the Pilot Institute CTA — warm, link in bio, not salesy]"
        elif p["pillar"] == "pilot_path":
            cta_note = (" [NO CTA: aspirational/emotional only — do NOT mention Pilot "
                        "Institute, courses, sign-ups, or 'link in bio']")
        else:
            cta_note = ""
        kind = p.get("source_kind", "none")
        if kind == "fact":
            ground = (f"\n    Build this post around this REAL fact (do not invent beyond it): "
                      f"{p['source_text']} — {p.get('source_detail','')}")
        elif kind == "news":
            ground = (f"\n    React in your own voice to this recent news (do not invent beyond it): "
                      f"{p['source_text']} — {p.get('source_detail','')}")
        else:
            ground = "\n    No fact available: keep it purely emotional/observational, invent nothing."
        lines.append(
            f"- id={p['id']} | date={p['date']} | type={p['type']} | "
            f"pillar={p['pillar']}{cta_note}\n    {brief}{ground}"
        )
```

- [ ] **Step 8: Correr el test y verificar que pasa**

Run: `python3 -m pytest tests/test_generate_prompt.py -v`
Expected: PASS.

- [ ] **Step 9: Convertir `SYSTEM_PROMPT` en persona + `VOICE_RULES`**

En `generate_content.py`, renombrar la constante `SYSTEM_PROMPT` (línea ~200) a `VOICE_RULES` y quitarle la identidad específica de aviación (esa vive ahora en `persona/epic-plane.md`). Dejar solo reglas de formato/voz genéricas. Reemplazar el bloque por:
```python
VOICE_RULES = """Format & voice rules (apply to EVERY post):
- ULTRA-short: 1-2 lines, ~10-25 words. Never a paragraph.
- Lead with awe/feeling, not a lesson. If there's a fact, ONE punchy line.
- Every post ENDS with an interactive hook that begs a comment (a guess, a this-or-that, or a direct "who else?"). Comments are the #1 goal.
- Emojis welcome and natural (✈️ signature; 😍🔥👀😱 when they fit). Never a robotic row of identical emojis.
- Vary the structure across posts — do NOT reuse the same closing formula post after post.
- Ground every specific claim in the fact/news provided for that post. Invent nothing.
- hook_en: scroll-stopping first line (max ~8 words). caption_en: the full short caption. caption_es: same tone in neutral Latin-American Spanish ("tú").
- hashtags: 6-10, lowercase, each starting with '#'. topic: short specific title. visual_prompt: vivid English prompt matched to the post type.
Return your answer by calling submit_calendar exactly once, one entry per post id, nothing else."""
```

- [ ] **Step 10: Componer el system prompt con la persona en `generate_creative`**

En `generate_creative` (línea ~317), cambiar la firma y el armado del system. Reemplazar:
```python
def generate_creative(skeleton: list[dict], month_label: str, model: str) -> dict[str, dict]:
```
por:
```python
def generate_creative(skeleton: list[dict], month_label: str, model: str, niche: str = "epic-plane") -> dict[str, dict]:
```
y reemplazar la línea `system = SYSTEM_PROMPT` (línea ~334) por:
```python
    import soul
    system = soul.load_persona(niche) + "\n\n" + VOICE_RULES
```

- [ ] **Step 11: Agregar el flag `--niche` y la asignación de fuentes en `main`**

En `main`, después de `parser.add_argument("--model", ...)` agregar:
```python
    parser.add_argument("--niche", default="epic-plane", help="Nicho/cliente: persona + base + noticias (por defecto: epic-plane).")
```
Y donde se arma el skeleton (`skeleton = build_schedule(year, month)`, línea ~731) agregar justo debajo:
```python
    import soul
    skeleton = soul.assign_sources(
        skeleton, soul.load_facts(args.niche), soul.load_news(args.niche)
    )
```
Y en la llamada a `generate_creative(...)` pasar el nicho:
```python
    creative = generate_creative(skeleton, month_label, args.model, args.niche)
```
(Buscar la llamada existente a `generate_creative(` en `main` y agregar `, args.niche`.)

- [ ] **Step 12: Correr toda la suite**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (todos verdes).

- [ ] **Step 13: Humo — verificar que arranca sin romper**

Run: `python3 generate_content.py --help`
Expected: la ayuda muestra el nuevo flag `--niche`.

- [ ] **Step 14: Commit**

```bash
git add soul.py generate_content.py tests/test_soul.py tests/test_generate_prompt.py
git commit -m "feat: generate_content v3 (persona + fact/news grounding + --niche)"
```

---

### Task 5: Validación en Epic.Plane (prueba con métricas)

**Files:**
- Modify: `knowledge/epic-plane/facts.csv` (ampliar a ~50-100 hechos reales)
- (Solo lectura / ejecución: `generate_content.py`, `review_deck.py`, `metrics.py`)

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: un lote de septiembre regenerado con alma + comparación cualitativa + seguimiento de métricas. (Tarea de operación: no lleva ciclo de test unitario.)

- [ ] **Step 1: Ampliar la base de conocimiento**

Agregar filas a `knowledge/epic-plane/facts.csv` hasta ~50-100, mismo esquema (`id,subject,fact,detail,source,tags,pillar`), cubriendo los pilares `technical_awe`, `spotting`, `aviation_story`, `pilot_path`. Cada `fact` debe ser real y tener `source`.

- [ ] **Step 2: Traer noticias frescas**

Run: `python3 curate.py epic-plane`
Expected: `✓ N noticias guardadas en data/news/epic-plane.json` (N ≥ 1). Si una fuente falla, se avisa y sigue.

- [ ] **Step 3: Generar un lote de prueba con alma**

Run: `python3 generate_content.py --month 2026-09 --niche epic-plane --force`
Expected: se generan 20 posts; el JSON y el Markdown de septiembre se escriben.

- [ ] **Step 4: Chequeo cualitativo (lado a lado)**

Abrir `content/2026-09.md` y comparar 5 captions nuevos vs el estilo anterior. Verificar a ojo: voz de fan experto, un hecho real por post evergreen, reacción en los slots de noticia, estructura variada (no la misma fórmula), emojis naturales, cero datos inventados. Si algo suena a IA o inventado → ajustar `persona/epic-plane.md` o `knowledge/epic-plane/facts.csv` y repetir Step 3.

- [ ] **Step 5: Publicar y medir (2-3 semanas)**

Aprobar el lote (deck / `--approve`), dejar que la nube publique según agenda, y correr semanalmente:
```bash
python3 metrics.py --days 21
```
Comparar **comentarios + guardados por post** y la **tendencia de alcance** contra la línea base previa. Éxito = suben comentarios/guardados y el contenido se siente humano.

- [ ] **Step 6: Commit de la base ampliada**

```bash
git add knowledge/epic-plane/facts.csv data/news/epic-plane.json
git commit -m "data: expand aviation knowledge base + fetch news for validation"
```

---

## Self-Review

**Spec coverage:**
- Persona Spec (voz) → Task 1 ✓
- Base de conocimiento (profundidad) → Task 2 ✓
- Curación/reacción de noticias → Task 3 ✓
- Generador v3 (mezcla 70/30, flag `--niche`, anclaje) → Task 4 ✓ (mezcla realizada por `assign_sources` con `reaction_every=3` ≈ 33% reacción / resto evergreen)
- Guardarraíles (anti-invención, emojis naturales, anti-repetición) → Task 1 (persona NUNCA) + Task 4 (VOICE_RULES + nota "invent nothing") ✓
- Validación en Epic.Plane con métricas + rollback → Task 5 ✓ (rollback: revertir el commit de Task 4 o cambiar los archivos por-nicho)
- No tocar media/deck/publish/correo → respetado (ningún task los modifica) ✓
- Seam multi-cliente (archivos por-nicho + `--niche`) → Tasks 1-4 ✓

**Placeholder scan:** sin TBD/TODO; todo el código está completo. La única expansión manual (ampliar la base a 50-100 hechos, Task 5 Step 1) es contenido de datos, no código, y trae esquema + semilla.

**Type consistency:** `load_persona`/`load_facts`/`load_news`/`assign_sources` usan las mismas firmas en sus definiciones (soul.py) y en los tests. `build_user_prompt` conserva su firma `(skeleton, month_label)`. `generate_creative` gana el parámetro `niche` y se actualiza su llamada en `main`. Las claves `source_kind`/`source_text`/`source_detail` producidas por `assign_sources` son las mismas que lee `build_user_prompt`.
