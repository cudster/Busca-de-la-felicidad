# Diseño — Motor YouTube (Fase 2a: guiones + plan)

**Fecha:** 2026-08-30
**Estado:** Aprobado para escribir plan de implementación
**Proyecto padre:** agencia multi-canal. Fase 2 = YouTube; este spec cubre **solo la Fase 2a (motor de guiones + plan)**. Fuera: 2b (producción de video con IA) y 2c (subida automática por API).

---

## 1. Contexto y objetivo

Primer canal de YouTube de la agencia: **canal faceless de autos de lujo, estilo POV**, en **español**. Guiones narrados (sin cara), Shorts + long-form. El motor debe producir todo lo "de escritorio" de un video (guión + SEO + miniatura + plan de tomas + calendario), listo para que el CEO revise y que las fases 2b/2c produzcan y suban.

**Objetivo 2a:** dado un mes, generar un lote de **planes de video** (mezcla de Shorts y long-form) para el canal, cada uno con guión en español, metadatos de SEO, concepto de miniatura y plan de tomas; escribirlos a un JSON + un Markdown legible para revisión. Mismo patrón que el generador de Instagram (`generate_content.py` + `soul.py`), adaptado a video.

**Criterio de éxito:** correr `python3 youtube_generate.py --channel autos-pov --month 2026-10` produce N planes de video (Shorts + long-form) con guiones en español coherentes, títulos clickeables, y plan de tomas; el CEO los revisa en el `.md`. Cambiar de canal = crear otro `youtube/<canal>/`.

---

## 2. Alcance

**Dentro (2a):**
- Config del canal: `youtube/<canal>/config.json` (nicho, idioma, mezcla Shorts/long-form, líneas de CTA, estilo del referente).
- Voz del narrador: `youtube/<canal>/persona.md`.
- `youtube_generate.py`: arma el esqueleto determinístico del mes (mezcla de formatos + fechas) y usa la API (tool use forzado) para rellenar cada plan de video.
- Salida: `youtube/<canal>/plan-YYYY-MM.json` + `content/youtube-<canal>-YYYY-MM.md` legible.
- **Reutilización cross-formato:** cada plan long-form incluye `shortable_moments` (2-4 momentos que se pueden cortar como Shorts).

**Fuera (fases siguientes):**
- 2b: generar el video (voz IA + clips) — no en 2a.
- 2c: subir a YouTube por API — no en 2a.
- Búsqueda/descarga real de clips (el plan de tomas describe qué se necesita; la obtención se resuelve con el patrón de `media.py` en 2b).
- Aprobación por deck/Sheet (2a escribe el `.md`; el flujo de aprobación se reusa/extiende después).

**No tocar:** `generate_content.py`, `media.py`, `publish.py`, `sheets.py`, `daily_email.py`, `curate.py`, `soul.py`, `dashboard.py` ni sus workflows. Módulo nuevo e independiente.

---

## 3. Arquitectura

```
youtube/<canal>/config.json   ← canal (nicho, idioma, mezcla, CTAs)
youtube/<canal>/persona.md    ← voz del narrador
        │
        ▼
  youtube_generate.py
     ├── build_month(config, year, month) → esqueleto: lista de {id, format, date}
     │     (mezcla Shorts/long-form según config; fechas de publicación)
     ├── build_prompt(config, persona, skeleton) → prompt para la API
     ├── genera vía API (tool use forzado `submit_videos`)
     └── escribe plan-YYYY-MM.json + content/youtube-<canal>-YYYY-MM.md
```

Python + `anthropic` (ya presente), stdlib para lo demás. Sin dependencias nuevas.

---

## 4. Componentes (detalle)

### 4.1 Config del canal — `youtube/autos-pov/config.json`
```json
{
  "channel": "autos-pov",
  "name": "Autos POV (faceless, lujo)",
  "language": "es",
  "niche": "autos de lujo, POV, faceless",
  "videos_per_month": 12,
  "mix": { "short": 8, "long": 4 },
  "cta_lines": ["Suscríbete si amas los autos", "Dale like y activa la campana"],
  "reference_style": "narración inmersiva en primera persona, ritmo ágil, datos que sorprenden"
}
```

### 4.2 Voz del narrador — `youtube/autos-pov/persona.md`
Markdown con: identidad del narrador (fan experto de autos de lujo, primera persona), tono (inmersivo, apasionado, español neutro latino), jerga que usa con naturalidad, qué NUNCA hace (inventar cifras; relleno), y 2-3 ejemplos de apertura de guión.

### 4.3 Generador — `youtube_generate.py`
Funciones:
- `load_channel(channel: str, base: Path = ROOT) -> dict` — lee `youtube/<channel>/config.json`; lanza `FileNotFoundError` claro si falta.
- `load_persona(channel: str, base: Path = ROOT) -> str` — lee `youtube/<channel>/persona.md`.
- `build_month(cfg: dict, year: int, month: int) -> list[dict]` — esqueleto determinístico: arma `mix.short` Shorts + `mix.long` long-form, con `id` (`YYYY-MM-S01`, `...-L01`), `format` (`"short"|"long"`) y `date` (distribuidas en días hábiles del mes). Puro y testeable.
- `build_prompt(cfg, persona, skeleton) -> str` — instrucciones + esqueleto, indicando por cada id el formato y las reglas (Short: ~150-200 palabras, gancho en 3s, 2 CTAs; Long: ~1200-1800 palabras, estructura gancho→segmentos→cierre+CTA, más `shortable_moments`).
- `VIDEO_TOOL` — schema `submit_videos` con, por video: `id, format, topic, hook_es, script_es, title, description, tags[], hashtags[], thumbnail_concept, shot_list[]`, y para long-form `shortable_moments[]`.
- `generate(skeleton, cfg, persona, model) -> dict[str, dict]` — llama la API (streaming + tool_choice forzado) y devuelve id→campos.
- `merge(skeleton, creative) -> list[dict]` + `write_json` + `write_markdown`.
- `main()` — flags `--channel` (requerido), `--month` (por defecto mes actual), `--model`, `--force`.

### 4.4 Salida
- `youtube/<canal>/plan-YYYY-MM.json` — lista de planes de video completos.
- `content/youtube-<canal>-YYYY-MM.md` — legible: por cada video, formato, título, gancho, guión, tags, miniatura, plan de tomas.

---

## 5. Flujo (una corrida)
1. `load_channel` + `load_persona`.
2. `build_month` → esqueleto (mezcla Shorts/long-form + fechas).
3. `build_prompt` + `generate` (API) → creativo por id.
4. `merge` → escribe JSON + Markdown.
5. El CEO revisa el `.md`.

---

## 6. Riesgos y mitigaciones
| Riesgo | Mitigación |
|---|---|
| Guiones que suenan a IA | Persona/voz definida + ejemplos few-shot (como en IG); revisión humana en el `.md` |
| Datos inventados de autos | Regla NUNCA-inventar en la persona; el plan de tomas y datos deben ser genéricos/verificables, no cifras falsas |
| Long-form muy largo para un solo prompt | `max_tokens` holgado + streaming; si hace falta, generar long-form y Shorts en llamadas separadas (iteración) |
| "Reutilización" ambigua | En 2a = cross-formato (long-form → `shortable_moments`); repurpose entre plataformas se ve en fases posteriores |

---

## 7. Entregables 2a
1. `youtube/autos-pov/config.json` + `youtube/autos-pov/persona.md`.
2. `youtube_generate.py` (load_channel, load_persona, build_month, build_prompt, VIDEO_TOOL, generate, merge, write_json, write_markdown, main).
3. `plan-YYYY-MM.json` + `content/youtube-autos-pov-YYYY-MM.md` de un mes de prueba.
4. Tests de las funciones puras (load_channel, build_month, merge).
