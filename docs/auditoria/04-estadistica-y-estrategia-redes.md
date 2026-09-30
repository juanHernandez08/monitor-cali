# Revisión estadística y estrategia de redes para Carlos Arias (2026-09-29)

Datos analizados: copia de `monitor.db` del 29 de septiembre de 2026 (4.860 menciones, 733 publicaciones de redes de candidatos y concejales, 23 de julio a 28 de septiembre de 2026).

## 1. Errores encontrados en las cifras

| # | Problema | Efecto real en el tablero | Corrección |
|---|---|---|---|
| E1 | Las 17 publicaciones de Instagram traídas por Bright Data guardan los likes en `likes`, pero el código solo leía `likesCount` (Apify) | Contaban 0 likes. Entre ellas, los reels de Carlos de septiembre: su "tendencia" aparecía en −84% y sus semanas 36 a 38 con 16 a 33 interacciones, cuando fueron 113 a 264 | `_social_metrics()` lee ambos esquemas |
| E2 | Instagram devuelve `likesCount = -1` cuando la cuenta oculta los likes (53 publicaciones: Mabel Lara 15, Juan Felipe Murgueitio 34) | Se sumaban como dato real; su alcance quedaba subestimado casi a cero | Se marcan `likes_hidden` y se excluyen de promedios, medianas y alertas |
| E3 | En X nunca se leían los likes (`likeCount`) | El alcance de X era solo respuestas | Corregido; también retuits y vistas |
| E4 | Alcance comparado por **promedio** | Un reel viral (11.321 interacciones) triplicaba el promedio de Carlos: 1.240 de promedio contra 353 de mediana | Mediana con intervalo de confianza (bootstrap) y promedio al lado |
| E5 | Alerta de "actividad fuerte" contra el **promedio de todo el historial** | Un viral inflaba la base y escondía los picos siguientes | Mediana de las últimas 10 publicaciones + z robusto |
| E6 | Porcentajes sin tamaño de muestra | "100% positivo" con 3 comentarios se veía igual que con 300 | Intervalos de Wilson en positividad y reacción |
| E7 | Variaciones entre períodos sin prueba | "+300%" pasando de 1 a 4 menciones se mostraba como tendencia | Prueba binomial condicional; con menos de 10 menciones, "muestra chica"; si p ≥ 0,05, "no concluyente" |
| E8 | Tendencia por mitades del **número** de publicaciones y por promedio | Muy sensible a un solo post | Tendencia de la mediana, solo para cuentas con 6 o más publicaciones |

Pruebas nuevas: `tests/test_stats.py` (12).

### Sesgos que siguen presentes (no se pueden corregir con código)
* **Comentarios recortados**: se guardan hasta 30 comentarios por publicación (`SOCIAL_MAX_COMMENTS`) y en las publicaciones grandes suelen ser los más relevantes o recientes, no una muestra aleatoria.
* **Audiencia autoseleccionada**: el 95% de comentarios positivos en las publicaciones de Carlos (82 comentarios, IC 95%: 88% a 98%) mide a sus seguidores, no a la ciudad.
* **Clasificador sin validar**: el sentimiento lo pone un LLM y nunca se comparó contra etiquetas humanas. Recomendación: que dos personas del equipo etiqueten 200 menciones al azar y calcular el acuerdo (kappa de Cohen); si baja de 0,6, revisar el prompt.
* **Menciones ≠ opinión pública**: prensa, comentarios y posts pesan igual en los conteos; un video con 300 comentarios domina una semana.

## 2. Nuevas gráficas
* **Candidatos:** positividad con rango plausible al 95%. Hoy Carlos tiene 68% de menciones positivas (IC 60% a 76%, 132 menciones), el valor más alto; su rango se cruza levemente con los de Roberto Ortiz (47% a 62%) y Roger Mina (43% a 70%), por lo que frente a ellos la ventaja no es concluyente.
* **Análisis en gráficas:** participación semanal de Carlos en la conversación (promedio 13,4% de las menciones de candidatos) y sentimiento neto con su franja de confianza.
* **Meta y redes:** alcance relativo por formato, día y franja horaria; ritmo de publicación; mediana semanal de Carlos contra el resto.

## 3. Qué dicen los datos de redes

| Hallazgo | Evidencia |
|---|---|
| **El reel es el formato que rinde**; el carrusel es el más flojo | Alcance relativo mediano: reel 1,04×, imagen 0,90×, carrusel 0,74× (449, 112 y 87 publicaciones) |
| **El día y la hora casi no importan** | Entre días, la mediana va de 0,88× a 1,19×; entre franjas, de 0,99× a 1,01×. Pesa qué se publica, no cuándo |
| **Carlos publica poco** | 2,2 publicaciones por semana, solo en Instagram. Clara Luz Roldán, 5,5 por red en Instagram y Facebook; Mondragón, 3,2 |
| **Su contenido engancha más que el promedio** | 7,8 de cada 100 personas que ven un video suyo interactúan; la mediana de los rivales es 5,7 |
| **Su alcance cayó después de agosto** | Mediana semanal de 1.651 (semana 33) a 113 a 264 (semanas 36 a 39); el resto de cuentas se mantuvo entre 185 y 265 |
| **Lo que funcionó** | Contraste directo con un rival (11.321 interacciones, 73.918 vistas), animales rescatados tras el terremoto (3.447), una propuesta concreta de alivio tributario (2.130), ayuda a damnificados (1.541) |
| **Lo que no** | Conmemoraciones, visitas a eventos y mensajes genéricos (92 a 196 interacciones) |
| **Poco volumen en la conversación** | 132 menciones en 90 días frente a 363 de Clara Luz Roldán y 270 de Alfredo Mondragón |

## 4. Estrategia recomendada para la actividad en redes de Carlos

Principio: Carlos es académico y decide con datos. La estrategia convierte eso en su sello: **menos protocolo, más problema concreto con cifra y propuesta**.

1. **Subir el ritmo a 4 publicaciones por semana, todas en reel** (hoy 2,2). Es el cambio con más evidencia: el formato rinde y la frecuencia es la brecha más grande frente a sus rivales. Meta a 8 semanas: mediana semanal de interacción por encima de la del resto de cuentas (hoy 185 a 265).
2. **Estructura fija de 45 a 90 segundos: problema, dato, propuesta.** Usar las cifras de la pestaña Histórico (por ejemplo: "326 personas murieron en las vías de Cali en 2025, lo mismo que en 2008. Propongo Visión Cero..."). Los tres reels que mejor le fueron tenían un tema concreto y una postura clara.
3. **Dos pilares propios que ya probaron funcionar:** bienestar animal (su reel de animales tras el terremoto es el segundo mejor) y propuestas económicas concretas. Sumar un tercero de la agenda de ciudad con mayor molestia (pestaña Agenda).
4. **Contraste con argumentos, no con insultos.** El contraste con Mondragón fue su mejor publicación, pero la regla del equipo es no fomentar polarización: contrastar propuestas y cifras, nunca personas.
5. **Reducir publicaciones protocolarias** (conmemoraciones, visitas) a historias efímeras, no al feed.
6. **Abrir Facebook y medirlo.** Hoy el monitor solo tiene su Instagram; Clara Luz Roldán obtiene casi la mitad de su actividad en Facebook. Agregar sus cuentas de Facebook, X y TikTok a `SOCIAL_ACCOUNTS` (con URL verificada) para poder comparar.
7. **Responder comentarios en la primera hora** y fijar el comentario con la propuesta: su audiencia ya es 95% favorable; el objetivo es que comparta, no solo que aplauda.
8. **Salir de la burbuja:** 1 de cada 4 piezas pensada para no seguidores (colaboraciones con cuentas de barrio, medios locales, líderes de comuna), porque la reacción positiva actual viene de quienes ya lo siguen.
9. **Medir cada lunes** en Meta y redes: mediana semanal (no promedio), ritmo, y formato. Ajustar solo con diferencias que el tablero marque como concluyentes.

Nada de lo anterior implica cuentas falsas, compra de interacción ni mensajes que no firme Carlos: además de ser contrario a las reglas de las plataformas y a la normativa electoral, contaminaría los propios datos del monitor.
