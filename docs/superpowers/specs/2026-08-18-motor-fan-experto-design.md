# Diseño — Motor "Fan Experto" (Epic.Plane)

**Fecha:** 2026-08-18
**Estado:** Aprobado para escribir plan de implementación
**Sub-proyecto:** Pieza A del negocio "Community Manager Automatizado" (ver Contexto)

---

## 1. Contexto y objetivo

Estamos convirtiendo el sistema de Epic.Plane (generar → media → aprobar → publicar 24/7 → correo diario → métricas) en un **servicio comercial**: un "Community Manager Automatizado" que mantiene la marca de un cliente activa en Instagram todos los días.

El negocio completo se descompone en piezas independientes:

| Pieza | Qué es | Orden |
|---|---|---|
| **A. Motor "Fan Experto"** | Persona con voz + base de conocimiento + reacción/curación → captions con alma | **Este spec** |
| B. Capa de marca | `brand.py`: logo/colores/tipografía sobre cada post | Después |
| C. Infra multi-cliente | config por cliente, `--client`, onboarding | Después |
| D. Meta App Review | permiso para publicar en cuentas de clientes | En paralelo |
| E. Venta / paquete comercial | oferta, precios, página de venta | En paralelo |

**Este documento cubre solo la Pieza A.**

**Problema que resuelve:** el contenido actual se siente "IA" — captions genéricos, hype vacío, fórmulas repetidas ("guess the airline 👇"). Eso rinde ~12 likes y no se vende como servicio premium. Los datos históricos de la cuenta muestran que lo que funcionó fue contenido con **alma**: voz de fan real, profundidad de insider, y reacción a lo que pasa en el nicho.

**Objetivo:** que el contenido se sienta creado por un **fan experto y apasionado** del nicho — con voz propia, conocimiento profundo y reacción a lo actual — manteniéndolo 100% automatizado. Y que ese "motor de alma" sea **replicable a otros nichos** (autos, alimentos) cambiando solo unos archivos de configuración.

**Criterio de éxito medible:** al probarlo en Epic.Plane durante 2-3 semanas, sube el promedio de **comentarios + guardados por post** vs la línea base actual, y pasa el chequeo cualitativo ("se siente humano/experto") en el deck de aprobación.

---

## 2. Alcance

**Dentro:**
- Definir y construir la **persona** (voz) como archivo por-nicho.
- Construir la **base de conocimiento** curada (profundidad) como datos por-nicho.
- Construir `curate.py` (**reacción**): pull semanal de noticias verificadas del nicho.
- Actualizar `generate_content.py` a v3 para que arme el "contexto con alma" y escriba con voz + profundidad + reacción.
- Probar y medir en Epic.Plane.

**Fuera (otras piezas / specs futuros):**
- Capa visual de marca (`brand.py`).
- Infra multi-cliente / onboarding.
- Meta App Review.
- Respuesta automática a comentarios/DMs (decisión explícita del dueño: el corazón está en el contenido, no en un bot que conversa).
- Cualquier cambio a media.py, deck, publish.py, correo diario o la nube.

**Principio de diseño clave:** el "alma" entra **solo en el nacimiento del contenido** (el generador). Todo lo aguas abajo (media, aprobación, publicación, reportes) queda intacto.

---

## 3. Arquitectura

No se rehace el flujo; se le agregan 3 fuentes de "alma" antes de que el generador escriba.

```
Esqueleto (fecha/pilar/tipo/horario)  ← igual que hoy
        │
        ▼
  [ CONTEXTO CON ALMA ]  ← NUEVO
   ├── Persona Spec        (voz)        persona/<nicho>.md
   ├── Base de Conocimiento (profundidad) knowledge/<nicho>/*.csv
   └── Noticia verificada   (reacción)   data/news/<nicho>.json  ← de curate.py
        │
        ▼
  generate_content.py v3   ← escribe caption EN+ES con voz + hechos + (reacción)
        │
        ▼
  Hoja → media.py → deck → publish.py → correo/métricas   ← TODO IGUAL
```

**Componentes por-nicho (esto es lo que se cambia para cada cliente):**
- `persona/<nicho>.md`
- `knowledge/<nicho>/*.csv`
- fuentes RSS/noticias de ese nicho (config de `curate.py`)

Para un cliente nuevo (autos, comida): se crean esos 3 → nuevo "fan experto" de ese rubro, mismo motor.

---

## 4. Componentes (detalle)

### 4.1 Persona Spec — `persona/epic-plane.md`

Archivo Markdown legible que define el personaje. Se inyecta al generador como el alma del system prompt.

Secciones obligatorias:
- **Identidad:** quién es el personaje (ej: "ex-agente de rampa vuelto avgeek obsesionado con los widebodies").
- **Voz y tono:** cómo habla (cálido, ingenioso, un poco obsesivo, específico).
- **Jerga:** términos reales del nicho que usa con naturalidad.
- **Opiniones / takes:** qué ama y qué odia (ej: "moriré defendiendo que el 747 es el jet más bello").
- **NUNCA (anti-IA):**
  - Nada de datos inventados (los específicos salen solo de la base/noticias).
  - Nada de hype vacío ni fórmulas repetidas post-tras-post.
  - Emojis **permitidos** y bienvenidos, usados como los usa un fan real (naturales, con intención); se evita solo el relleno robótico (filas de emojis idénticos en cada post).
- **Ejemplos de voz:** 3-4 captions modelo (few-shot) que fijan el tono.

### 4.2 Base de Conocimiento — `knowledge/aviation/*.csv`

Datos reales, específicos, de insider, etiquetados por tema/avión, **con fuente**.

Esquema de columnas propuesto:
`id, topic, subject (avión/tema), fact (el dato), detail (contexto extra), source (URL/ref), tags`

Reglas:
- El generador **solo** usa hechos de aquí para afirmaciones específicas → cero invención.
- Cada caption debe apoyarse en **al menos 1 hecho** relevante recuperado por `topic`/`subject`.
- Si no hay hecho para un tema, el post se mantiene emocional/observacional (no inventa).
- Base inicial para la prueba: ~50-100 entradas.

### 4.3 Curación / Reacción — `curate.py`

Script (stdlib + urllib) que corre semanalmente (local y/o GitHub Actions).

- **Entrada:** lista de fuentes RSS del nicho (ej. Simple Flying, AVHerald) en un config.
- **Proceso:** trae items recientes → filtra a una lista corta "reaccionable" → guarda en `data/news/aviation.json` con `{title, summary, url, date}`.
- **Filtro de calidad:** solo items con título+fuente reales; descarta lo dudoso. (Sin verificación humana, los ítems solo alimentan la *reacción/opinión*, no se citan como dato duro salvo que también estén respaldados.)
- **Salida:** archivo JSON que el generador lee.

### 4.4 Generador v3 — `generate_content.py`

Cambios sobre el actual:
- **Carga** `persona/<nicho>.md`, recupera hechos relevantes de `knowledge/<nicho>/` por el `topic` de cada post, y (para slots de reacción) toma un item de `data/news/<nicho>.json`.
- **Arma el prompt** con: persona (voz) + hechos (profundidad) + noticia opcional (reacción).
- **Mezcla:** ~70% posts "evergreen" (anclados en la base) / ~30% "reacción" (anclados en noticia).
- **Escribe** caption EN + ES con voz consistente, apoyado en hecho(s), variando estructura.
- **Flag de nicho:** parámetro para elegir persona/base (ej. `--niche aviation`), preparando multi-cliente sin construirlo aún.
- Todo lo demás del generador (esqueleto determinístico, escritura a hoja, etc.) se conserva.

---

## 5. Flujo de datos (un post)

1. Esqueleto define fecha/pilar/tipo/horario (igual que hoy).
2. Se arma el "contexto con alma":
   - Persona (siempre).
   - Hechos recuperados de la base por tema (siempre; ≥1 hecho o el post se queda emocional).
   - Noticia verificada (solo en slots de reacción, ~30%).
3. El generador escribe caption EN+ES con voz + profundidad + (reacción).
4. Aguas abajo sin cambios: Hoja → media.py → deck → publish.py → correo/métricas.

---

## 6. Guardarraíles (el "corazón" / anti-IA)

- **Anclaje en hechos:** los datos específicos salen SOLO de la base o de noticias verificadas. Sin hecho → no inventa.
- **Voz consistente:** los ejemplos few-shot de la persona fuerzan el tono.
- **Variedad de estructura:** rota formatos (dato-bomba / opinión / pregunta real / asombro / historia). Regla anti-repetición: no repetir la misma fórmula de cierre en posts consecutivos.
- **Mesura:** no todo es hype; se permite asombro callado, opinión, pregunta genuina. Emojis naturales.
- **Filtro humano final:** el deck de aprobación (swipe) no se toca → el dueño ve todo antes de publicar.

---

## 7. Validación en Epic.Plane

**Construir para la prueba:** persona de aviación + base inicial (~50-100 hechos) + feed de noticias (2-3 RSS).

**Medición:**
- **Cualitativa:** comparar captions v3 vs actuales lado a lado en el deck. ¿Humano/experto?
- **Cuantitativa (2-3 semanas):** comentarios + guardados por post y tendencia de alcance, vs la línea base actual (metrics.py + correo diario ya existentes).
- **Éxito:** más comentarios/guardados por post + se siente humano.
- **Iteración:** si queda plano, se ajustan persona/base (son solo archivos).

**Rollback:** si empeora, persona y base son archivos → se vuelve al generador actual en un minuto. Riesgo casi cero.

---

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| El modelo inventa datos ("alucina") | Anclaje estricto: específicos solo desde la base; sin hecho → emocional |
| Sonar repetitivo/robótico igual | Regla anti-repetición + variedad de formatos + few-shot de voz |
| Noticias falsas/dudosas del RSS | Filtro de calidad; noticias alimentan opinión, no dato duro sin respaldo |
| Construir base es trabajo manual | Empezar con ~50-100 hechos; ampliar con el tiempo; se puede semi-automatizar después |
| No mejora el engagement | Prueba con métricas + rollback trivial (archivos) |

---

## 9. Entregables

1. `persona/epic-plane.md`
2. `knowledge/aviation/facts.csv` (~50-100 entradas iniciales)
3. `curate.py` + config de fuentes RSS + `data/news/aviation.json`
4. `generate_content.py` v3 (carga persona/base/noticia, mezcla 70/30, flag `--niche`)
5. Lote de prueba regenerado en Epic.Plane + comparación cualitativa
6. Seguimiento de métricas a 2-3 semanas
