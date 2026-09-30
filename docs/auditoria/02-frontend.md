# Revisión front-end (2026-09-29)

Se inspeccionó `templates/dashboard.html`, `static/dashboard.js`, `static/dashboard.css` y `static/council.js`, y se probó el tablero con datos reales en Chromium (escritorio 1400 px y móvil 390 px), revisando consola, errores de red y desbordes.

## Hallazgos y cambios

| Área | Antes | Ahora |
|---|---|---|
| Carga | `loadAll()` pedía unas 25 rutas y dibujaba ~40 gráficas al abrir, incluidas las de pestañas ocultas, y repetía todo cada 2 minutos aunque la ventana estuviera minimizada | Cada pestaña carga lo suyo al abrirse (`TAB_LOADERS`), recuerda con qué período se cargó, y la actualización automática solo refresca la pestaña visible si la ventana está a la vista |
| Gráficas en pestañas ocultas | ApexCharts medía 0 px y dibujaba `NaN` (decenas de errores SVG en consola) | Las gráficas de contenedores ocultos quedan pendientes y se dibujan al mostrarse; las de nodos reemplazados se destruyen |
| Errores | `fetch().json()` sin revisar el estado: un 401 o 500 dejaba la pestaña a medio pintar sin aviso | `j()` revisa el estado y muestra un aviso (`#toast`); 401 pide recargar |
| Seguridad | `innerHTML` con URLs y textos sin escapar, `onerror` en línea | Ver `01-seguridad.md` (S3): `esc()`, `safeUrl()`, `clip()`, CSP |
| Navegación | Sin URL por pestaña: recargar siempre volvía a Resumen, no se podía compartir un enlace a "Histórico" | `#hash` por pestaña (`/#historico`), botón atrás del navegador, período recordado en el navegador |
| HTML repetido | Las listas de 17 temas y 7 emociones estaban copiadas a mano 4 veces | Una sola lista en JS (`CATEGORY_OPTIONS`, `EMOTION_OPTIONS`) |
| Accesibilidad | Sin estilos de foco, selects sin etiqueta, pestañas sin estado, gráficas mudas para lectores de pantalla | `:focus-visible`, enlace "Saltar al contenido", `aria-label` en filtros, `aria-current` y `role="tab"`/`aria-selected`, `aria-busy` al cargar, gráficas con `role="img"` y el título de su panel, `aria-live` en avisos y estado |
| Movimiento | Animaciones siempre activas | Se respetan `prefers-reduced-motion` |
| Móvil | La pestaña Histórico desbordaba a 572 px en una pantalla de 390 px | `min-width: 0` en la columna principal y sub-pestañas con desplazamiento propio; tablas con scroll horizontal interno |
| CDN | ApexCharts sin `integrity` | SRI + `crossorigin` |
| Impresión | Se imprimían menú y botones | Hoja `@media print`: solo el contenido de la pestaña activa, enlaces con su URL |
| Imágenes | Las de prensa por `http://` las bloquea la CSP (y el navegador en HTTPS) | Caen al favicon del medio sin romper el diseño |

Resultado medido con la base real: 0 errores de JavaScript en las 9 pestañas y sin desborde horizontal en móvil.

## Nuevas vistas
* **Candidatos:** rango plausible (IC 95%) de la positividad de cada candidato.
* **Análisis en gráficas:** participación semanal de Carlos en la conversación y sentimiento neto con su margen.
* **Meta y redes:** formato, día, franja horaria, ritmo de publicación y evolución semanal (ver `04-estadistica-y-estrategia-redes.md`); alcance por mediana.
* **Histórico:** tres sub-pestañas; la nueva "Cali 2008 a hoy" con cinco frentes, comparación y conclusiones (ver `05-historico-2008-2026.md`).

## Recomendaciones (no aplicadas)
1. **Dividir `dashboard.js`** (≈1.400 líneas) en módulos ES por pestaña (`<script type="module">`), sin necesidad de un empaquetador. Hoy una variable declarada más abajo del archivo puede no estar lista si una pestaña carga antes (se evitó arrancando en `DOMContentLoaded`).
2. **Plantillas con escape automático**: la mayor parte del HTML se arma con cadenas. Una función `html\`\`` con escape por defecto evitaría depender de acordarse de `esc()`.
3. **Servir ApexCharts desde `/static`** (copia versionada) si se quiere funcionar sin depender de jsDelivr.
4. **Contraste**: el gris `#84837c` de ejes y leyendas queda en ~3,8:1 sobre blanco; subirlo a `#6e6d66` (el del CSS) para cumplir 4,5:1 en texto pequeño.
5. **Paginación** en los feeds (hoy 80 filas fijas).
