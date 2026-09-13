# Rossacuore — Plan de inauguración (Al Día, primer cliente)

**Cliente:** Rossacuore · @rossacuore_chile · Verónica Pagueguy (aprueba Verónica + Christian, el mismo día)
**Plan:** Crecimiento ($390.000/mes) — solo Instagram
**Voz:** elegante y premium, tuteo, emojis con moderación (🤎🍫🎂✨)
**Reglas duras:** ❌ nunca "promoción"/"descuento" · ❌ nunca precios · ❌ nada barato/rasca
**Foto = del cliente** (tienen material, entrega semanal). Nosotros ponemos la voz + la estrategia; ellos aprueban antes de publicar.

---

## 0. Antes de publicar — checklist de accesos (lo que falta)
- [ ] **Instagram → cuenta Empresa/Creador** y **conectada a una Página de Facebook** (la creamos nosotros; hoy no tienen FB). Necesario para publicar por API y ver métricas.
- [ ] **Token de acceso** de esa cuenta → lo guardamos como `ROSSACUORE_TOKEN` / `ROSSACUORE_IG_USER_ID`.
- [ ] **WhatsApp Business** confirmado → link corto para la bio (CTA de pedidos).
- [ ] **Carpeta de fotos/videos** compartida con nosotros (hoy está en un Dropbox local; pídeles un link de Drive/Dropbox compartido).
- [ ] **Logo en PNG/vector** + confirmar paleta (ya la tenemos).

> Mientras no esté el acceso técnico, publicamos con el modo "cliente aprueba → sube el equipo del cliente" y en paralelo dejamos el pipeline listo.

## Cadencia
Pidieron **diaria**. El plan Crecimiento cubre **20 posts/mes** (~5/semana) con reels + stories diarias. Propuesta: **5-6 feed posts/semana + stories diarias** (la story diaria es la señal de "cuenta activa" y no satura el feed premium). Si quieren feed 100% diario, subimos al plan siguiente. **A confirmar con Verónica.**

---

## Semana de lanzamiento (post inaugural + 7 días)

> Para cada post: **[FOTO]** = qué imagen suya usar · **caption** en su voz · **gancho** para comentar/guardar · **CTA** WhatsApp. Ninguno menciona precio ni "promo/descuento".

### 🎬 DÍA 0 — Post inaugural (reel o carrusel)
**[FOTO]** Su mejor toma: una torta insignia (Cuore della Dolcezza) girando / plano cenital + un plano del sello de chocolate. Cierra con el packaging.
**Caption:**
> Bienvenido a Rossacuore. 🤎
> Tortas de autor, hechas a mano en pequeños lotes. Nace en Italia, se hace en Santiago.
> Cada creación lleva un sello de chocolate que la firma como única.
> Esto es pastelería para celebrar de verdad.
> Encarga la tuya por WhatsApp (link en la bio) ✨
**Gancho:** "¿Para qué celebración imaginas la primera? Cuéntanos 🤎"

### DÍA 1 — Producto insignia (imagen)
**[FOTO]** Cuore della Dolcezza, primer plano con textura/capas.
**Caption:**
> Cuore della Dolcezza: capas hechas a mano, chocolate de autor y un final que se recuerda.
> El lujo está en el detalle.
**Gancho:** "Guarda esta idea para tu próximo cumpleaños ✨"

### DÍA 2 — Detrás de escena (reel)
**[FOTO/VIDEO]** El proceso: manos trabajando, el sello de chocolate, el emplatado.
**Caption:**
> Así nace una Rossacuore: pequeños lotes, tiempo y dedicación. La misma en la primera torta de la semana que en la última. 🍫
**Gancho:** "Etiqueta a quien merece una torta hecha así."

### DÍA 3 — La italiana (imagen)
**[FOTO]** Torta con estética italiana / mesa elegante.
**Caption:**
> Nace en Italia, se hace en Santiago. Inspiración de la pastelería italiana, en cada capa.
**Gancho:** "¿Chocolate o frutos rojos? Cuéntanos tu favorita 🤎"

### DÍA 4 — Dolce Vita (imagen/carrusel)
**[FOTO]** Línea Dolce Vita, varios ángulos.
**Caption:**
> Dolce Vita. Para los días que merecen algo memorable.
> Diseño de autor, ingredientes selectos, hecho a mano.
**Gancho:** "Guárdala para tu próxima celebración ✨"

### DÍA 5 — El regalo / packaging (imagen)
**[FOTO]** Packaging elegante, lista para regalar.
**Caption:**
> El detalle también está en cómo llega: packaging pensado para regalar.
> Una Rossacuore no se entrega, se regala. 🎁
**Gancho:** "¿A quién le regalarías una?"

### DÍA 6 — Ocasión / cliente ideal (reel)
**[FOTO/VIDEO]** Torta en una mesa de celebración real.
**Caption:**
> Cumpleaños, aniversarios, los días que importan. Rossacuore es la torta que se vuelve parte del recuerdo.
> Reserva la tuya por WhatsApp ✨
**Gancho:** "Cuéntanos qué estás celebrando este mes 🤎"

### DÍA 7 — Adelanto Serie Keto (teaser, imagen)
**[FOTO]** Una toma sugerente de la nueva colección (sin revelar todo).
**Caption:**
> Se viene algo nuevo: una colección de autor, keto, con la misma dedicación de siempre.
> Muy pronto. 🤎
**Gancho:** "¿Te avisamos cuando salga? Déjanos un 🤎 en los comentarios."

---

## Notas de estrategia (para Al Día)
- **Fechas fuertes ya cargadas** (`data/occasions/rossacuore.json`): San Valentín, Día de la Madre, Navidad, etc. — el sistema anticipará contenido temático. Para esta marca, el mayor motor son **cumpleaños/aniversarios** (todo el año) → contenido "regalo memorable" constante.
- **Sin lenguaje de promo/precio.** Los lanzamientos (Serie Keto) se comunican como **colección/edición**, nunca "oferta".
- **Interacción sin sonar comercial:** ganchos de "guarda/etiqueta/cuéntanos" — suben guardados y comentarios, que es lo que mueve alcance, manteniendo el tono premium.
- **Stories diarias:** detrás de escena, encuestas ("¿esta o esta?"), cuenta regresiva a la Serie Keto.
- **Pendiente de sistema:** el generador automático (`generate_content.py`) hoy tiene pilares de aviación (Epic.Plane); para automatizar el mes de Rossacuore hay que hacer los pilares/briefs configurables por nicho (persona + facts ya están creados). Este plan de lanzamiento es escrito a mano para arrancar YA con calidad.
