# Epic.Plane — Repost con crédito (curación con permiso)

Estrategia de crecimiento por curación: repostear lo **ya viral** de aviación, con
**permiso** y **crédito**, agregando tu gancho. Reposts = alcance; reels originales
"spot-the-aircraft" = identidad. Mezcla objetivo: **1 repost + 2 originales** por
semana (de tus 3 reels/semana).

---

## 1) El DM de permiso (listo para enviar)

**Inglés (por defecto — el 80% de los creadores):**
```
python3 repost.py --dm @creator --about "that low pass over the runway"
```
→ *"Hey @creator 👋 this is the team behind @epic.plane. We absolutely LOVED your shot
"that low pass over the runway" — it's exactly the kind of thing our aviation community
goes crazy for. Would you give us permission to share it on our feed with full credit
to you (@creator tagged in the video and in the caption)? Of course we'll take it down
right away if you'd rather we didn't. Amazing work! ✈️"*

**Español (si el creador es hispano):** `--lang es`.

**El DM lo mandas TÚ** desde @epic.plane (la mensajería IG automática está bloqueada por
App Review). Guarda el "sí" antes de agendar.

---

## 2) A quién contactar (perfil que más dice que SÍ)

- **Micro-spotters (1k–50k):** fotógrafos/spotters de aeropuerto. **Son los que más
  aceptan** — quieren exposición. Tu mejor cantera.
- **Cómo encontrarlos:** Explore + hashtags **#planespotting #avgeek #aviationphotography
  #megaplane #spotting**; ubica los reels con muchos likes/guardados y revisa el autor.
  También r/aviation "top of week" y avgeek en TikTok/YouTube Shorts (pide permiso igual).
- **Qué clip elegir:** avión **raro/icónico** (A380, An-124/225, Concorde, cazas), o
  **maniobra impactante** (low pass, despegue vertical, aterrizaje con viento cruzado),
  vertical (9:16), y **ya viral**. Evita SIEMPRE accidentes, tragedias o polémica.
- **Grandes (aspiracional):** @samchui y similares rara vez dan permiso a cuentas
  chicas — no gastes ahí al principio; enfócate en micro-spotters.
- **Arma tu roster:** guarda los 5-10 que dijeron que sí = flujo constante sin re-pedir.

---

## 3) El loop (con repost.py)

```
# 1. Pedir permiso (mándalo tú desde la cuenta)
python3 repost.py --dm @creator --about "<qué muestra la toma>"

# 2. Con el "sí" + la URL pública que te autorizó, agendar (crédito ya incluido)
python3 repost.py --add --date 2026-10-11 --creator @creator \
  --credit-name "Nombre Real" --media-url https://... \
  --topic "Low pass brutal" --hook "Wait for the pass 👀" \
  --type reel --permission-confirmed --to-sheet
```
- Sin `--permission-confirmed` se niega (recordatorio de pedir permiso).
- El caption sale con: tu gancho + "double tap 👇 + follow @creator" + "📷 @creator
  (reposted with permission)". El crédito va SIEMPRE.
- Cae en el calendario/Sheet como un post más → aprobación → publica por el pipeline.

---

## 4) Cadencia (1 repost/semana, sin tocar código)

El motor genera 3 reels/semana. Para meter 1 repost:
1. Genera el mes normal (`generate_content.py`).
2. **Aprueba 2 de los 3 reels** de esa semana (deja 1 sin aprobar).
3. Agenda **1 repost** con `repost.py --add` en el día del reel que no aprobaste.
Así la semana queda: 1 repost + 2 originales + 2 fotos, sin huecos ni dobles.

**Regla de oro:** nunca 100% repost. Los reposts traen alcance; tus reels originales
"spot-the-aircraft" construyen la marca y son los que monetizas.
