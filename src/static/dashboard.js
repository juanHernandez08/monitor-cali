const $ = (s) => document.querySelector(s);
const CARLOS = "Carlos Arias";

/* Paleta validada (skill de dataviz): orden categórico fijo, seguro para daltonismo en pares
   adyacentes (node scripts/validate_palette.js). Nunca reasignar por candidato/canal al filtrar. */
const BLUE = "#2a78d6", ORANGE = "#eb6834", AQUA = "#1baf7a", YELLOW = "#eda100",
      MAGENTA = "#e87ba4", GREEN = "#008300", VIOLET = "#4a3aa7", RED = "#e34948";
const GOOD = "#0ca30c", CRITICAL = "#d03b3b", NEUTRAL_TONE = "#b7b6ad";
const INK = "#14140f", INK_SOFT = "#52514e", MUTED = "#84837c", GRID = "#e7e6e0";
const CARLOS_GRAY = "#c7cbd6"; // candidatos que no son Carlos, en las gráficas que solo lo resaltan a él

const COLORS = [BLUE, RED, AQUA, YELLOW, MAGENTA, VIOLET, ORANGE, GREEN, MUTED]; // hasta 9 candidatos
const SRC = { google_news: "Prensa", rss: "Prensa", reddit: "Reddit", youtube: "YouTube", social: "Instagram / Facebook", google_cse: "Redes", serp: "Redes" };
const SRC_LABEL = { google_news: "Prensa", rss: "Prensa", reddit: "Reddit", youtube: "YouTube", social: "Instagram / Facebook", instagram: "Instagram", facebook: "Facebook", x: "X", google_cse: "Redes (búsqueda)", serp: "Redes (búsqueda)" };
const SRC_COLOR = { Prensa: BLUE, YouTube: ORANGE, Reddit: AQUA, "Redes (búsqueda)": YELLOW, Instagram: MAGENTA, Facebook: GREEN, X: VIOLET };
const LABEL = { negative: "Negativo", positive: "Positivo", neutral: "Neutral" };
const KIND = { post: "Post", video: "Video", comments: "Publicación", news: "Nota" };
const charts = {};
let summaryRows = [];

/* ---------- ApexCharts: helper genérico + estilo base compartido ---------- */
function chart(id, opts) {
  if (charts[id]) charts[id].destroy();
  const base = { chart: { fontFamily: "Inter, system-ui, sans-serif", foreColor: MUTED, toolbar: { show: false }, animations: { speed: 300 } },
    grid: { borderColor: GRID, strokeDashArray: 0 }, tooltip: { theme: "light" } };
  charts[id] = new ApexCharts($(id), deepMerge(base, opts));
  charts[id].render();
}
function deepMerge(a, b) {
  const out = { ...a };
  for (const k in b) out[k] = (a[k] && typeof a[k] === "object" && !Array.isArray(a[k]) && typeof b[k] === "object" && !Array.isArray(b[k])) ? deepMerge(a[k], b[k]) : b[k];
  return out;
}
/* Barras horizontales, una sola serie (ranking o magnitud). `perBar` = array de colores o un color fijo.
   `onClick(categoryIndex)` es opcional: si se da, la barra se ve y se comporta como un botón. */
/* Alto dinámico según cuántas barras hay -- una lista de 20+ candidatos/concejales en un cuadro
   fijo queda ilegible (etiquetas cortadas, barras finísimas). Nunca más chico que el mínimo de
   siempre (260px), solo más grande cuando hace falta. No lee el alto por CSS: la mayoría de las
   pestañas están ocultas (display:none) al cargar todo de una, y ahí getComputedStyle da 0. */
function barsHeight(id, n) {
  const h = Math.max(260, 30 + n * 28);
  $(id).style.height = `${h}px`;
  return h;
}
function hbar(id, categories, data, perBar, { labelFmt, onClick } = {}) {
  const h = barsHeight(id, categories.length);
  chart(id, {
    chart: { type: "bar", height: h, events: onClick ? { dataPointSelection: (e, ctx, cfg) => onClick(cfg.dataPointIndex) } : {} },
    series: [{ data }], xaxis: { categories, labels: { style: { colors: MUTED } } },
    plotOptions: { bar: { horizontal: true, borderRadius: 4, distributed: Array.isArray(perBar), barHeight: "62%" } },
    colors: Array.isArray(perBar) ? perBar : [perBar],
    dataLabels: { enabled: true, formatter: labelFmt || ((v) => v), style: { colors: [INK], fontWeight: 600 }, offsetX: 6 },
    legend: { show: false },
  });
  if (onClick) $(id).style.cursor = "pointer";
}
/* Barras horizontales apiladas al 100% (ya como % 0-100). `colors` sigue el mismo orden que `series`
   -- nunca asumir positivo/neutral/negativo: cada llamada dice explícitamente su propio orden. */
function hbar100(id, categories, series, colors) {
  const h = barsHeight(id, categories.length);
  chart(id, {
    chart: { type: "bar", stacked: true, height: h },
    series, xaxis: { categories, max: 100, labels: { formatter: (v) => Math.round(v) + "%" } },
    plotOptions: { bar: { horizontal: true, borderRadius: 3, barHeight: "62%" } },
    colors,
    dataLabels: { enabled: true, formatter: (v) => (v >= 8 ? Math.round(v) + "%" : ""), style: { colors: ["#fff"], fontWeight: 600 } },
    legend: { position: "bottom" }, tooltip: { y: { formatter: (v) => v + "%" } },
  });
}

function initials(name) { return name.split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase(); }
function avatar(r, cls = "") {
  return r.avatar
    ? `<img class="avatar ${cls}" src="${r.avatar}" alt="" referrerpolicy="no-referrer" onerror="this.outerHTML='<div class=&quot;avatar ${cls}&quot;>${initials(r.name)}</div>'">`
    : `<div class="avatar ${cls}">${initials(r.name)}</div>`;
}
function pct(n, t) { return t ? Math.round(n / t * 100) : 0; }
function bar(r) {
  const t = r.positive + r.negative + r.neutral || 1;
  return `<div class="bar"><i class="p" style="width:${r.positive / t * 100}%"></i><i class="u" style="width:${r.neutral / t * 100}%"></i><i class="g" style="width:${r.negative / t * 100}%"></i></div>`;
}
const share = (r, k) => pct(r[k], r.positive + r.negative + r.neutral);

async function j(url) { const r = await fetch(url); return r.json(); }
function days() { return Number($("#days").value); }
function periodLabel() { const d = days(); return d === 1 ? "las últimas 24 horas" : `los últimos ${d} días`; }
function ordinal(i) { return `${i + 1}.º`; }
function esc(s) { return (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function ago(iso) {
  if (!iso) return "sin datos";
  const m = Math.round((Date.now() - new Date(iso + "Z")) / 60000);
  if (m < 1) return "hace un momento";
  return m < 60 ? `hace ${m} min` : m < 1440 ? `hace ${Math.round(m / 60)} h` : `hace ${Math.round(m / 1440)} d`;
}
function fmtDate(iso) { return new Date(iso + "Z").toLocaleString("es-CO", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }
function fmtNum(x) { return (x || 0).toLocaleString("es-CO"); }

/* Medidor semicircular (0-100): verde si va bien, ámbar en zona media, rojo si va mal. */
function renderGauge(id, value) {
  if (!$(id)) return;
  const tone = value >= 60 ? GOOD : value >= 40 ? YELLOW : CRITICAL;
  chart(id, {
    chart: { type: "radialBar", height: "100%" },
    series: [value],
    colors: [tone],
    plotOptions: { radialBar: { startAngle: -90, endAngle: 90, hollow: { size: "68%" }, track: { background: "#eceae2" },
      dataLabels: { name: { show: false }, value: { offsetY: -2, fontSize: "26px", fontWeight: 700, color: INK, formatter: (v) => v + "%" } } } },
  });
}

/* ---------- panel de un candidato (usado en el resumen para Carlos y en el perfil para cualquiera) ---------- */
function heroHTML(r, rivals, gaugeId) {
  const cScored = r.positive + r.negative + r.neutral;
  const rivalsPos = rivals.reduce((a, x) => a + x.positive, 0), rivalsScored = rivals.reduce((a, x) => a + x.positive + x.negative + x.neutral, 0);
  const cPct = pct(r.positive, cScored), rPct = pct(rivalsPos, rivalsScored);
  const diff = cScored && rivalsScored ? cPct - rPct : null;
  return `
    ${avatar(r)}
    <div>
      <div class="name">${esc(r.name)}</div><div class="party">${esc(r.party || "")}</div>
      <div class="stats">
        <div class="stat"><div class="n">${r.mentions}</div><div class="l">menciones</div></div>
        <div class="stat"><div class="n" style="color:var(--pos)">${r.positive}</div><div class="l">positivas</div></div>
        <div class="stat"><div class="n" style="color:var(--neu)">${r.neutral}</div><div class="l">neutrales</div></div>
        <div class="stat"><div class="n" style="color:var(--neg)">${r.negative}</div><div class="l">negativas</div></div>
        ${r.pending ? `<div class="stat"><div class="n" style="color:var(--muted)">${r.pending}</div><div class="l">pendientes de análisis</div></div>` : ""}
      </div>
      <div style="margin-top:10px">${bar(r)}</div>
      <div class="legend"><span><i style="background:var(--pos)"></i>positivo</span><span><i style="background:var(--neu)"></i>neutral</span><span><i style="background:var(--neg)"></i>negativo</span></div>
    </div>
    <div class="compare">
      <div class="hint">Positividad${r.name === CARLOS ? " de Carlos" : ""}</div>
      <div class="gauge-box" id="${gaugeId}"></div>
      <div class="big ${diff === null ? "" : diff >= 0 ? "pos" : "neg"}" style="font-size:15px">${diff === null ? "sin comparación" : `${diff >= 0 ? "+" : ""}${diff} pts vs el resto`}</div>
      <div class="hint">(${cScored ? cPct : "—"}% vs ${rivalsScored ? rPct : "—"}%)</div>
    </div>`;
}

/* ---------- KPIs + panel de Carlos + tarjetas ---------- */
async function loadSummary() {
  const rows = await j(`/api/summary?days=${days()}`);
  summaryRows = rows;
  const alerts = await j(`/api/alerts?days=${days()}`);
  const carlos = rows.find((r) => r.name === CARLOS) || rows[0];
  const rivals = rows.filter((r) => r !== carlos);
  const total = rows.reduce((a, r) => a + r.mentions, 0);
  const cScored = carlos.positive + carlos.negative + carlos.neutral;
  const rivalsScored = rivals.reduce((a, r) => a + r.positive + r.negative + r.neutral, 0);
  const rivalsPos = rivals.reduce((a, r) => a + r.positive, 0);
  const cPct = pct(carlos.positive, cScored), rPct = pct(rivalsPos, rivalsScored);

  $("#kpis").innerHTML = `
    <div class="kpi"><div class="label">Menciones en el período</div><div class="value">${total}</div><div class="foot">notas, posts y comentarios · ${rows.length} candidatos</div></div>
    <div class="kpi"><div class="label">Menciones de Carlos Arias</div><div class="value">${carlos.mentions}</div><div class="foot">${carlos.previous ? `${carlos.mentions >= carlos.previous ? "▲" : "▼"} ${Math.abs(Math.round((carlos.mentions - carlos.previous) / carlos.previous * 100))}% vs período anterior` : "sin período anterior"}</div></div>
    <div class="kpi"><div class="label">Positividad de Carlos Arias</div><div class="value ${cPct >= 50 ? "pos" : ""}">${cScored ? cPct + "%" : "—"}</div><div class="foot">rivales: ${rivalsScored ? rPct + "%" : "—"} en promedio</div></div>
    <div class="kpi"><div class="label">Alertas activas</div><div class="value ${alerts.length ? "neg" : ""}">${alerts.length}</div><div class="foot">menciones negativas (≤ −0.5) sobre Carlos</div></div>`;

  $("#hero").innerHTML = heroHTML(carlos, rivals, "chart-gauge");
  $("#hero").dataset.candidateId = carlos.candidate_id; $("#hero").dataset.name = carlos.name;
  renderGauge("#chart-gauge", cScored ? cPct : 0);

  $("#cards").innerHTML = rivals.map((r) => `<button class="card" data-candidate-id="${r.candidate_id}" data-name="${esc(r.name)}">
      ${avatar(r, "sm")}
      <div>
        <div class="name">${esc(r.name)}</div><div class="party">${esc(r.party || "")}</div>
        <div class="n">${r.mentions}<small>menciones${r.pending ? ` · ${r.pending} pend.` : ""}</small></div>
        ${bar(r)}
      </div></button>`).join("");

  const candOptions = `<option value="">Todos los candidatos</option>` + rows.map((r) => `<option value="${r.candidate_id}">${esc(r.name)}</option>`).join("");
  for (const id of ["#f-candidate", "#yt-f-candidate", "#rd-f-candidate"]) {
    const s = $(id); if (!s) continue;
    const cur = s.value; s.innerHTML = candOptions; s.value = cur;
  }

  // ¿De quién se habla más?
  const byVol = [...rows].sort((a, b) => b.mentions - a.mentions);
  hbar("#chart-volume", byVol.map((r) => r.name), byVol.map((r) => r.mentions), byVol.map((r) => r.name === CARLOS ? BLUE : CARLOS_GRAY));
  const vRank = byVol.findIndex((r) => r.name === CARLOS);
  const tied = byVol.filter((r) => r.mentions === carlos.mentions && r.name !== CARLOS);
  $("#read-volume").innerHTML = `En ${periodLabel()} se registraron <b>${total} menciones</b> de los ${rows.length} candidatos. ` +
    (vRank === 0
      ? `<b>Carlos Arias</b> es de quien más se habla, con ${carlos.mentions} menciones${tied.length ? ` (empatado con ${tied.map((r) => esc(r.name)).join(" y ")})` : ""}; le sigue ${esc((byVol.find((r) => r.mentions < carlos.mentions) || {}).name || "")}.`
      : `<b>${esc(byVol[0].name)}</b> es de quien más se habla (${byVol[0].mentions}). <b>Carlos Arias</b> ocupa el ${ordinal(vRank)} lugar con ${carlos.mentions} menciones, ${byVol[0].mentions - carlos.mentions} menos.`);

  // ¿Cómo se habla de cada candidato?
  const scored = rows.filter((r) => r.positive + r.negative + r.neutral > 0);
  hbar100("#chart-sentiment", scored.map((r) => `${r.name} (${r.positive + r.negative + r.neutral})`), [
    { name: "Positivas", data: scored.map((r) => share(r, "positive")) },
    { name: "Neutrales", data: scored.map((r) => share(r, "neutral")) },
    { name: "Negativas", data: scored.map((r) => share(r, "negative")) }], [GOOD, NEUTRAL_TONE, CRITICAL]);
  const byPos = [...scored].sort((a, b) => share(b, "positive") - share(a, "positive"));
  const byNeg = [...scored].sort((a, b) => share(b, "negative") - share(a, "negative"));
  const cRank = byPos.findIndex((r) => r.name === CARLOS);
  $("#read-sentiment").innerHTML = scored.length ? `<b>${esc(byPos[0].name)}</b> tiene la mejor imagen: ${share(byPos[0], "positive")}% de sus menciones son positivas. ` +
    `<b>${esc(byNeg[0].name)}</b> concentra la mayor carga negativa (${share(byNeg[0], "negative")}% negativas). ` +
    (cRank >= 0 ? `<b>Carlos Arias</b> es ${ordinal(cRank)} en positividad, con ${share(carlos, "positive")}% positivas y ${share(carlos, "negative")}% negativas sobre ${cScored} menciones clasificadas.` : "")
    : "Aún no hay menciones clasificadas en el período.";
  return rows;
}

async function loadTimeline(rows) {
  const span = Math.max(days(), 7);
  const d = await j(`/api/timeline?days=${span}`);
  const top = [CARLOS, ...rows.filter((r) => r.name !== CARLOS).sort((a, b) => b.mentions - a.mentions).slice(0, 4).map((r) => r.name)];
  const series = d.series.filter((s) => top.includes(s.name));
  const niceLabels = d.labels.map((l) => l.slice(5).replace("-", "/"));
  $("#day-detail").style.display = "none";
  chart("#chart-timeline", {
    chart: { type: "line", height: "100%",
      events: { dataPointSelection: (e, ctx, cfg) => showPeak(series[cfg.seriesIndex].name, d.labels[cfg.dataPointIndex]) } },
    series: series.map((s) => ({ name: s.name, data: s.data })),
    xaxis: { categories: niceLabels, tickAmount: 10 },
    colors: series.map((s, i) => COLORS[i % COLORS.length]),
    stroke: { curve: "smooth", width: series.map((s) => s.name === CARLOS ? 3.5 : 1.5) },
    markers: { size: series.map((s) => s.name === CARLOS ? 4 : 3), hover: { size: 7 } },
    legend: { position: "bottom" },
    yaxis: { labels: { formatter: (v) => Math.round(v) }, title: { text: "menciones ese día" } },
    tooltip: { shared: false, intersect: true, y: { formatter: (v) => `${v} ${v === 1 ? "mención" : "menciones"} · clic para ver la publicación` } },
  });
  const cs = series.find((s) => s.name === CARLOS);
  if (cs) {
    const peakIdx = cs.data.reduce((best, v, i) => (v > cs.data[best] ? i : best), 0);
    if (cs.data[peakIdx] > 0) showPeak(CARLOS, d.labels[peakIdx]);
  }
}

async function showPeak(name, day) {
  const box = $("#day-detail");
  box.style.display = "block";
  box.innerHTML = `<div class="empty">Cargando…</div>`;
  const p = await j(`/api/peak?candidate=${encodeURIComponent(name)}&day=${day}`);
  const nice = new Date(day + "T12:00:00").toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" });
  if (!p || !p.text) { box.innerHTML = `<div class="panel-head"><h2>${esc(name)} · ${nice}</h2><button class="toggle" id="day-close">cerrar ✕</button></div><div class="empty">Sin publicaciones de ${esc(name)} ese día.</div>`; }
  else {
    box.innerHTML = `<div class="panel-head"><h2>${esc(name)} · ${nice}</h2><span class="hint">${p.mentions_that_day} ${p.mentions_that_day === 1 ? "mención" : "menciones"} ese día, la mayoría de esta publicación</span><button class="toggle" id="day-close">cerrar ✕</button></div>
    <article class="item">
      ${thumb(p)}
      <div class="body">
        <div class="meta"><span class="tag src">${srcName(p)} · ${KIND[p.kind] || ""}</span>${p.url ? `<a href="${p.url}" target="_blank" rel="noopener">ver original ↗</a>` : ""}</div>
        <div class="text">${esc(p.text)}</div>
      </div>
    </article>`;
  }
  $("#day-close").addEventListener("click", () => { box.style.display = "none"; });
}

/* Volumen (menciones) contra positividad (%): 4 cuadrantes clásicos de análisis de reputación. */
function loadQuadrant(rows) {
  if (!$("#chart-quadrant")) return;
  const scored = rows.filter((r) => r.positive + r.negative + r.neutral > 0);
  if (!scored.length) { $("#read-quadrant").innerHTML = "Aún no hay menciones clasificadas en el período."; return; }
  const sortedVol = [...scored].map((r) => r.mentions).sort((a, b) => a - b);
  const medVol = sortedVol[Math.floor(sortedVol.length / 2)];
  const withXY = scored.map((r) => ({ name: r.name, x: r.mentions, y: share(r, "positive") }));
  const carlos = withXY.find((p) => p.name === CARLOS);
  const rivals = withXY.filter((p) => p.name !== CARLOS);

  chart("#chart-quadrant", {
    chart: { type: "scatter", height: "100%", zoom: { enabled: false } },
    series: [{ name: "Rivales", data: rivals.map((p) => [p.x, p.y]) }, ...(carlos ? [{ name: "Carlos Arias", data: [[carlos.x, carlos.y]] }] : [])],
    colors: [CARLOS_GRAY, BLUE],
    markers: { size: 9, strokeWidth: 2, strokeColors: "#fff" },
    xaxis: { title: { text: "menciones en el período" }, tickAmount: 5 },
    yaxis: { title: { text: "% de menciones positivas" }, min: 0, max: 100, labels: { formatter: (v) => Math.round(v) + "%" } },
    legend: { show: false },
    annotations: {
      xaxis: [{ x: medVol, borderColor: GRID, strokeDashArray: 4, label: { text: "mediana de volumen", orientation: "horizontal", style: { color: MUTED, background: "#fff", fontSize: "10px" } } }],
      yaxis: [{ y: 50, borderColor: GRID, strokeDashArray: 4, label: { text: "50% positividad", style: { color: MUTED, background: "#fff", fontSize: "10px" } } }],
      points: withXY.map((p) => ({ x: p.x, y: p.y, marker: { size: 0 }, label: { text: p.name, offsetY: -14, borderWidth: 0, style: { color: INK, background: "transparent", fontSize: "11px", fontWeight: p.name === CARLOS ? 700 : 500 } } })),
    },
    tooltip: { custom: ({ seriesIndex, dataPointIndex, w }) => {
      const p = seriesIndex === 0 ? rivals[dataPointIndex] : carlos;
      return `<div style="padding:6px 10px"><b>${esc(p.name)}</b><br>${p.x} menciones · ${p.y}% positivas</div>`;
    } },
  });
  const quadName = (p) => (p.x >= medVol ? (p.y >= 50 ? "mucho volumen y buena imagen" : "mucho volumen pero imagen floja") : (p.y >= 50 ? "poco volumen pero buena imagen" : "poco volumen y sin destacar"));
  const loudBad = rivals.filter((p) => p.x >= medVol && p.y < 50).sort((a, b) => b.x - a.x)[0];
  $("#read-quadrant").innerHTML = carlos
    ? `<b>Carlos Arias</b> está en el cuadrante de <b>${quadName(carlos)}</b> (${carlos.x} menciones, ${carlos.y}% positivas).` +
      (loudBad ? ` El rival con más volumen e imagen floja es <b>${esc(loudBad.name)}</b> (${loudBad.x} menciones, ${loudBad.y}% positivas) — ese es terreno para diferenciarse.` : "")
    : "Sin datos de Carlos en el período.";
}

async function loadSources() {
  const d = await j(`/api/sources?days=${days()}`);
  const groups = {};
  for (const [type, counts] of Object.entries(d.series)) {
    const label = SRC_LABEL[type] || type;
    groups[label] = (groups[label] || Array(d.candidates.length).fill(0)).map((v, i) => v + counts[i]);
  }
  const labels = Object.keys(groups);
  chart("#chart-sources", {
    chart: { type: "bar", stacked: true, height: "100%" },
    series: labels.map((l) => ({ name: l, data: groups[l] })),
    xaxis: { categories: d.candidates },
    colors: labels.map((l) => SRC_COLOR[l] || MUTED),
    plotOptions: { bar: { borderRadius: 2, columnWidth: "55%" } },
    dataLabels: { enabled: true, formatter: (v) => (v >= 6 ? v : ""), style: { colors: ["#fff"], fontWeight: 600, fontSize: "11px" } },
    legend: { position: "bottom" },
  });
  const ci = d.candidates.indexOf(CARLOS);
  const totalsByChannel = labels.map((l) => [l, groups[l].reduce((a, b) => a + b, 0)]).sort((a, b) => b[1] - a[1]);
  const carlosByChannel = labels.map((l) => [l, groups[l][ci] || 0]).sort((a, b) => b[1] - a[1]);
  const cTotal = carlosByChannel.reduce((a, x) => a + x[1], 0);
  $("#read-sources").innerHTML = totalsByChannel.length ? `El canal con más conversación es <b>${totalsByChannel[0][0]}</b> (${totalsByChannel[0][1]} menciones en total). ` +
    (cTotal ? `Las menciones de <b>Carlos Arias</b> vienen sobre todo de <b>${carlosByChannel[0][0]}</b> (${pct(carlosByChannel[0][1], cTotal)}% de sus ${cTotal})` +
      (carlosByChannel[1] && carlosByChannel[1][1] ? `, seguido de ${carlosByChannel[1][0]} (${pct(carlosByChannel[1][1], cTotal)}%).` : ".") : "")
    : "Sin datos en el período.";
}

async function loadTopics() {
  const [pub, com] = await Promise.all([j(`/api/topics?days=${days()}&kind=publications`), j(`/api/topics?days=${days()}&kind=comments`)]);
  if ($("#chart-topics")) hbar("#chart-topics", com.map((x) => x.topic), com.map((x) => x.count), VIOLET);
  if ($("#chart-topics-pub")) hbar("#chart-topics-pub", pub.map((x) => x.topic), pub.map((x) => x.count), BLUE);
  if ($("#chart-topics-com")) hbar("#chart-topics-com", com.map((x) => x.topic), com.map((x) => x.count), VIOLET);
  const reading = (t, what) => t.length
    ? `El asunto más frecuente en ${what} es <b>${esc(t[0].topic)}</b> (${t[0].count})` + (t[1] ? `, seguido de <b>${esc(t[1].topic)}</b> (${t[1].count})` : "") + (t[2] ? ` y <b>${esc(t[2].topic)}</b> (${t[2].count})` : "") + "."
    : `Sin asuntos identificados en ${what} para el período.`;
  if ($("#read-topics-pub")) $("#read-topics-pub").innerHTML = reading(pub, "las noticias y publicaciones");
  if ($("#read-topics-com")) $("#read-topics-com").innerHTML = reading(com, "los comentarios de la gente");
}

async function loadAlerts() {
  const a = await j(`/api/alerts?days=${days()}`);
  $("#alerts").innerHTML = a.length ? a.map((m) => `<li>
    <span class="tag negative">${m.score}</span> ${esc(m.text).slice(0, 200)}
    <div class="meta">${srcName(m)} · ${esc(m.author || "")} · ${ago(m.published_at)}${m.url ? ` · <a href="${m.url}" target="_blank" rel="noopener">ver</a>` : ""}</div>
  </li>`).join("") : `<li class="empty">Sin menciones negativas fuertes sobre Carlos Arias en el período.</li>`;
}

async function loadSocialStrong() {
  if (!$("#social-strong")) return;
  const s = await j(`/api/social/strong?days=${Math.min(days(), 90)}`);
  $("#social-strong").innerHTML = s.length ? s.map((p) => `<li>
    <span class="tag positive">${p.multiplier}×</span> <b>${esc(p.candidate)}</b>: ${esc(p.text).slice(0, 160)}
    <div class="meta">${SRC_LABEL[p.platform] || p.platform} · ❤️ ${fmtNum(p.likes)} · 💬 ${fmtNum(p.comments)}${p.views ? ` · 👁 ${fmtNum(p.views)}` : ""} · habitual: ~${fmtNum(p.baseline)} · ${ago(p.published_at)}${p.url ? ` · <a href="${p.url}" target="_blank" rel="noopener">ver</a>` : ""}</div>
  </li>`).join("") : `<li class="empty">Sin publicaciones muy por encima de lo habitual en el período.</li>`;
}

/* ---------- feed (reutilizable: pestaña Publicaciones y vista de Perfil) ---------- */
function srcName(m) { return m.platform ? (SRC_LABEL[m.platform] || m.platform) : (SRC[m.source_type] || esc(m.source)); }
/* Google News y RSS son ambos "Prensa": sin esto salían como dos chips separados con el mismo nombre. */
function mergedSources(sources) {
  const out = {};
  for (const [src, n] of Object.entries(sources)) {
    const label = SRC_LABEL[src] || SRC[src] || src;
    out[label] = (out[label] || 0) + n;
  }
  return out;
}
function sentTag(m) {
  if (!m.label) return `<span class="tag pending">pendiente</span>`;
  const emotionText = m.emotion && m.emotion !== "sin emoción marcada"
    ? (m.emotion_nuance ? `${m.emotion} (${m.emotion_nuance})` : m.emotion) : "";
  const emotion = emotionText ? `<div class="topic">siente: ${esc(emotionText)}${m.apalancador ? ` — por: ${esc(m.apalancador)}` : ""}</div>` : "";
  return `<span class="tag ${m.label}">${LABEL[m.label]} ${m.score}</span>${m.topic ? `<div class="topic">${esc(m.topic)}</div>` : ""}${emotion}`;
}
function thumb(r) {
  let host = null;
  try { host = new URL(r.url).hostname; } catch (e) { host = null; }
  const favicon = host ? `https://www.google.com/s2/favicons?domain=${host}&sz=64` : "";
  if (r.thumbnail) return `<div class="thumb"><img src="${r.thumbnail}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null; this.parentNode.classList.add('logo'); this.src='${favicon}'"></div>`;
  if (host) return `<div class="thumb logo"><img src="${favicon}" alt="" loading="lazy"></div>`;
  return `<div class="thumb">${KIND[r.kind] || ""}</div>`;
}
function commentsBlock(r, idx) {
  const s = r.comments_summary;
  if (!s.total) return "";
  const t = s.total;
  return `<button class="toggle" data-idx="${idx}">▸ ${t} comentario${t === 1 ? "" : "s"}</button>
    <div class="cbar"><i class="p" style="width:${s.positive / t * 100}%"></i><i class="u" style="width:${s.neutral / t * 100}%"></i><i class="g" style="width:${s.negative / t * 100}%"></i></div>
    <div class="counts">${s.positive} positivos · ${s.neutral} neutrales · ${s.negative} negativos</div>`;
}
const feedStore = {}; // selector de contenedor -> filas, para el despliegue de comentarios
function renderFeedList(sel, rows, { showCandidate = false } = {}) {
  feedStore[sel] = rows;
  $(sel).innerHTML = rows.map((r, i) => `<article class="item" data-row="${i}">
    ${thumb(r)}
    <div class="body">
      <div class="meta">${showCandidate ? `<span class="cand">${esc(r.candidate)}</span>` : ""}<span class="tag src">${srcName(r)} · ${KIND[r.kind] || ""}</span><span>${fmtDate(r.published_at)}</span>${r.url ? `<a href="${r.url}" target="_blank" rel="noopener">ver original ↗</a>` : ""}</div>
      <div class="text">${esc(r.text)}</div>
      ${r.summary ? `<div class="summary">📝 ${esc(r.summary)}</div>` : ""}
      ${r.author ? `<div class="author">${esc(r.author)}</div>` : ""}
    </div>
    <div class="side">
      ${r.kind === "comments" ? `<span class="hint">solo comentarios</span>` : sentTag(r)}
      ${commentsBlock(r, i)}
    </div>
  </article>`).join("") || `<div class="empty">Sin publicaciones con esos filtros.</div>`;
  $(sel).querySelectorAll(".toggle[data-idx]").forEach((b) => b.addEventListener("click", () => toggleComments(sel, Number(b.dataset.idx), b)));
}
function toggleComments(sel, idx, btn) {
  const item = document.querySelector(`${sel} .item[data-row="${idx}"]`);
  const open = item.querySelector(".thread");
  if (open) { open.remove(); btn.textContent = btn.textContent.replace("▾", "▸"); return; }
  const r = feedStore[sel][idx];
  const div = document.createElement("div"); div.className = "thread";
  div.innerHTML = r.comments.map((c) => `<div class="comment">
      <div>${esc(c.text)}<div class="who">${esc(c.author || "")} · ${fmtDate(c.published_at)}${(c.link || c.url) ? ` · <a href="${c.link || c.url}" target="_blank" rel="noopener">ver</a>` : ""}</div></div>
      <div>${sentTag(c)}</div></div>`).join("") || `<div class="empty">Sin comentarios que cumplan el filtro.</div>`;
  item.appendChild(div);
  btn.textContent = btn.textContent.replace("▸", "▾");
}
/* ---------- Publicaciones: Prensa / YouTube / Reddit comparten esta misma función, cada una
   con su propio prefijo de filtros -- la sub-pestaña de Redes sociales usa social_posts() en
   vez de feed(), con su propio alcance (likes/comentarios/vistas), así que no pasa por aquí. */
async function loadFeedTab(feedSel, filterPrefix, sourceType) {
  if (!$(feedSel)) return;
  const p = new URLSearchParams({ days: days(), limit: 80, source_type: sourceType });
  if ($(`#${filterPrefix}-candidate`)?.value) p.set("candidate_id", $(`#${filterPrefix}-candidate`).value);
  if ($(`#${filterPrefix}-label`)?.value) p.set("label", $(`#${filterPrefix}-label`).value);
  if ($(`#${filterPrefix}-emotion`)?.value) p.set("emotion", $(`#${filterPrefix}-emotion`).value);
  if ($(`#${filterPrefix}-category`)?.value) p.set("category", $(`#${filterPrefix}-category`).value);
  renderFeedList(feedSel, await j(`/api/feed?${p}`), { showCandidate: true });
}
function loadFeed() { return loadFeedTab("#feed", "f", "prensa"); }
function loadFeedYoutube() { return loadFeedTab("#yt-feed", "yt-f", "youtube"); }
function loadFeedReddit() { return loadFeedTab("#rd-feed", "rd-f", "reddit"); }

/* ---------- Meta y redes: publicaciones de Instagram/Facebook/X por alcance ---------- */
/* Candidatos a la Alcaldía vs. concejales, en TODAS las gráficas de Meta y redes -- un concejal
   muy activo (p. ej. Clara Luz Roldán con 197 posts) aplastaba la escala y no se distinguía nada
   entre los candidatos, que es la comparación que importa. Carlos Arias y Roberto Ortiz son
   candidatos Y concejales a la vez, pero cuentan solo como candidatos (Candidate.kind =
   "candidate"): ya están en esa sección, no se repiten en la de concejales. Promesa compartida
   para que loadMeta() y loadMetaAnalytics() (corren en paralelo) no pidan la lista dos veces.*/
let peoplePromise = null;
function getPeople() { return peoplePromise ||= j("/api/social/candidates"); }
async function getCouncilorNames() {
  const people = await getPeople();
  return new Set(people.filter((r) => r.is_councilor).map((r) => r.name));
}
function splitByCouncil(rows, councilorNames, nameKey = "candidate") {
  return [rows.filter((r) => !councilorNames.has(r[nameKey])), rows.filter((r) => councilorNames.has(r[nameKey]))];
}

let metaCandidatesLoaded = false;
async function loadMeta() {
  if (!$("#meta-kpis")) return;
  const councilorNames = await getCouncilorNames();
  if (!metaCandidatesLoaded) {
    metaCandidatesLoaded = true;
    const metaSel = $("#meta-f-candidate");
    const people = await getPeople();
    metaSel.innerHTML = `<option value="">Todos (candidatos y concejales)</option>` +
      people.map((r) => `<option value="${r.candidate_id}">${esc(r.name)}${r.is_councilor ? " (concejal)" : ""}</option>`).join("");
  }
  const d = days();
  const p = new URLSearchParams({ days: d });
  if ($("#meta-f-candidate").value) p.set("candidate_id", $("#meta-f-candidate").value);
  if ($("#meta-f-platform").value) p.set("platform", $("#meta-f-platform").value);
  if ($("#meta-f-sort").value) p.set("sort", $("#meta-f-sort").value);
  const [kpis, posts] = await Promise.all([j(`/api/social/kpis?days=${d}`), j(`/api/social/posts?${p}`)]);
  const n = fmtNum;

  $("#meta-kpis").innerHTML = `
    <div class="kpi"><div class="label">Publicaciones</div><div class="value">${kpis.total_posts}</div><div class="foot">Instagram, Facebook y X · ${periodLabel()}</div></div>
    <div class="kpi"><div class="label">Likes</div><div class="value">${n(kpis.total_likes)}</div><div class="foot">suma de todas las publicaciones</div></div>
    <div class="kpi"><div class="label">Comentarios</div><div class="value">${n(kpis.total_comments)}</div><div class="foot">suma de todas las publicaciones</div></div>
    <div class="kpi"><div class="label">Publicación con más alcance</div><div class="value" style="font-size:15px;line-height:1.3">${kpis.top_post ? esc(kpis.top_post.text.slice(0, 46)) + (kpis.top_post.text.length > 46 ? "…" : "") : "—"}</div><div class="foot">${kpis.top_post ? `${esc(kpis.top_post.candidate)} · ${n(kpis.top_post.engagement)} de alcance` : "sin publicaciones en el período"}</div></div>`;

  const [byCand, byCouncil] = splitByCouncil(kpis.by_candidate, councilorNames);
  hbar("#chart-meta-candidate", byCand.map((c) => c.candidate), byCand.map((c) => c.count),
    byCand.map((c) => c.candidate === CARLOS ? BLUE : CARLOS_GRAY));
  hbar("#chart-meta-councilor", byCouncil.map((c) => c.candidate), byCouncil.map((c) => c.count),
    byCouncil.map(() => CARLOS_GRAY));

  $("#meta-feed").innerHTML = posts.length ? posts.map((r) => `<article class="item">
      ${thumb(r)}
      <div class="body">
        <div class="meta"><span class="cand">${esc(r.candidate)}</span><span class="tag src">${SRC_LABEL[r.platform] || r.platform}</span><span>${fmtDate(r.published_at)}</span>${r.url ? `<a href="${r.url}" target="_blank" rel="noopener">ver original ↗</a>` : ""}</div>
        <div class="text">${esc(r.text)}</div>
        ${r.summary ? `<div class="summary">📝 ${esc(r.summary)}</div>` : ""}
      </div>
      <div class="side">
        ${sentTag(r)}
        <div class="hint" style="margin-top:6px">❤️ ${n(r.likes)} · 💬 ${n(r.comments)}${r.views ? ` · 👁 ${n(r.views)}` : ""}</div>
      </div>
    </article>`).join("") : `<div class="empty">Sin publicaciones con esos filtros en el período.</div>`;
}

/* ---------- Meta y redes: alcance, reacción y la estrategia del reporte diario (sin recalcular
   nada -- reach/reaction usan las mismas queries.candidate_reach_comparison/comment_reaction que
   el reporte, y el análisis se lee del último reporte ya generado, no se le pide de nuevo al LLM
   cada vez que alguien abre esta pestaña). ---------- */
function renderReach(suffix, rows) {
  hbar(`#chart-meta-reach${suffix}`, rows.map((c) => c.candidate), rows.map((c) => c.avg_engagement),
    rows.map((c) => c.candidate === CARLOS ? BLUE : CARLOS_GRAY));
  const trendRows = rows.filter((c) => c.trend_pct !== null);
  $(`#meta-trend${suffix}-panel`).style.display = trendRows.length ? "" : "none";
  if (trendRows.length) {
    hbar(`#chart-meta-trend${suffix}`, trendRows.map((c) => c.candidate), trendRows.map((c) => c.trend_pct),
      trendRows.map((c) => c.trend_pct >= 0 ? GOOD : CRITICAL), { labelFmt: (v) => (v >= 0 ? "+" : "") + v + "%" });
  }
}
function renderReaction(suffix, rows) {
  const withReaction = rows.filter((c) => c.comments > 0);
  hbar100(`#chart-meta-reaction${suffix}`, withReaction.map((c) => `${cap(c.candidate)} (${c.comments})`), [
    { name: "Positivo", data: withReaction.map((c) => c.positive_pct) },
    { name: "Neutral", data: withReaction.map((c) => c.neutral_pct) },
    { name: "Negativo", data: withReaction.map((c) => c.negative_pct) }], [GOOD, NEUTRAL_TONE, CRITICAL]);
}
async function loadMetaAnalytics() {
  if (!$("#chart-meta-reach")) return;
  const d = days();
  const [reach, reaction, latest, councilorNames] = await Promise.all([
    j(`/api/social/reach?days=${d}`), j(`/api/social/reaction?days=${d}`),
    j("/api/reports/latest").catch(() => null), getCouncilorNames(),
  ]);

  const [reachCand, reachCouncil] = splitByCouncil(reach, councilorNames);
  renderReach("", reachCand);
  renderReach("-council", reachCouncil);

  const [reactionCand, reactionCouncil] = splitByCouncil(reaction, councilorNames);
  renderReaction("", reactionCand);
  renderReaction("-council", reactionCouncil);

  const n = latest?.narrative;
  $("#meta-narrative-panel").style.display = n ? "" : "none";
  if (n) {
    $("#meta-narrative-date").textContent = `del análisis diario del ${latest.date} — ver el reporte completo en la pestaña Reporte`;
    $("#meta-narrative").innerHTML = `
      <p class="reading">${esc(n.resumen_ejecutivo)}</p>
      <p>${esc(n.analisis)}</p>
      ${n.limitaciones ? `<div class="limitations"><span class="label">Qué NO se puede determinar con estos datos</span>${esc(n.limitaciones)}</div>` : ""}
      <h3 style="margin:14px 0 6px">Estrategia recomendada</h3>
      <div class="alerts"><ul>${n.estrategia.map((s) => `<li>${esc(s)}</li>`).join("") || `<li class="empty">Sin recomendaciones en este corte.</li>`}</ul></div>`;
  }
}

/* ---------- Investigar un perfil cualquiera, en vivo (no queda guardado) ---------- */
async function investigateProfile() {
  const url = $("#inv-url").value.trim();
  const platform = $("#inv-platform").value;
  if (!url) return;
  const btn = $("#inv-go"); btn.disabled = true; btn.textContent = "Investigando…";
  $("#inv-result").innerHTML = `<div class="empty">Consultando ${esc(url)}…</div>`;
  try {
    const r = await fetch(`/api/investigate?${new URLSearchParams({ url, platform })}`);
    const data = await r.json();
    if (!r.ok) { $("#inv-result").innerHTML = `<div class="empty">${esc(data.error || "No se pudo investigar ese perfil.")}</div>`; return; }
    if (!data.total_posts) { $("#inv-result").innerHTML = `<div class="empty">Sin publicaciones recientes encontradas para esa cuenta.</div>`; return; }
    $("#inv-result").innerHTML = `
      <div class="kpis" style="margin-bottom:10px">
        <div class="kpi"><div class="label">Publicaciones traídas</div><div class="value">${data.total_posts}</div></div>
        <div class="kpi"><div class="label">Likes totales</div><div class="value">${fmtNum(data.total_likes)}</div></div>
        <div class="kpi"><div class="label">Comentarios totales</div><div class="value">${fmtNum(data.total_comments)}</div></div>
        <div class="kpi"><div class="label">Alcance promedio</div><div class="value">${fmtNum(data.avg_engagement)}</div></div>
      </div>
      <div class="feed">${data.posts.map((p) => `<article class="item">
        <div class="body">
          <div class="meta"><span>${esc(p.author || "")}</span><span>${p.published_at ? fmtDate(p.published_at) : ""}</span>${p.url ? `<a href="${p.url}" target="_blank" rel="noopener">ver original ↗</a>` : ""}</div>
          <div class="text">${esc(p.text).slice(0, 200)}</div>
        </div>
        <div class="side"><div class="hint">❤️ ${fmtNum(p.likes)} · 💬 ${fmtNum(p.comments)}${p.views ? ` · 👁 ${fmtNum(p.views)}` : ""}</div></div>
      </article>`).join("")}</div>`;
  } catch (e) {
    $("#inv-result").innerHTML = `<div class="empty">Error consultando ese perfil.</div>`;
  } finally {
    btn.disabled = false; btn.textContent = "Investigar";
  }
}
$("#inv-go").addEventListener("click", investigateProfile);
$("#inv-url").addEventListener("keydown", (e) => { if (e.key === "Enter") investigateProfile(); });

/* ---------- tema por tema (genérico: perfil de candidato y detalle de ciudad) ---------- */
function topicCard(t, i, prefix) {
  const subtopics = (t.subtopics || []).filter((s) => s.topic !== t.topic.toLowerCase());
  return `<div class="topic-card" id="${prefix}-card-${i}">
      <div class="head"><h3>${esc(t.topic)}</h3><div>${t.count} menciones · <span class="tag ${t.positive_pct >= 60 ? "positive" : t.positive_pct <= 30 ? "negative" : ""}">${t.positive_pct}% a favor</span></div></div>
      <div class="subs"><span class="tag positive">${t.positive} positivas</span><span class="tag">${t.neutral} neutrales</span><span class="tag negative">${t.negative} negativas</span>
        ${Object.entries(mergedSources(t.sources)).map(([label, n]) => `<span class="tag">${esc(label)} · ${n}</span>`).join("")}</div>
      ${subtopics.length ? `<div class="subs">${subtopics.map((s) => `<span class="tag">${esc(s.topic)} · ${s.count}</span>`).join("")}</div>` : ""}
      <button class="toggle" data-topic-idx="${i}" data-topic-prefix="${prefix}">▸ ver ${t.samples.length} comentario${t.samples.length === 1 ? "" : "s"} de ejemplo</button>
    </div>`;
}
const topicStore = {};
function renderTopicCards(containerSel, readSel, rows, prefix, visibleCount = 5) {
  topicStore[prefix] = rows;
  const visible = rows.slice(0, visibleCount), rest = rows.slice(visibleCount);
  $(containerSel).innerHTML = visible.map((t, i) => topicCard(t, i, prefix)).join("")
    + (rest.length ? `<button class="toggle" id="${prefix}-more">▸ ver ${rest.length} tema${rest.length === 1 ? "" : "s"} más</button><div id="${prefix}-rest" style="display:none">${rest.map((t, i) => topicCard(t, i + visible.length, prefix)).join("")}</div>` : "")
    || `<div class="empty">Aún no hay suficientes menciones con tema identificado en el período.</div>`;
  $(`#${prefix}-more`)?.addEventListener("click", (e) => { $(`#${prefix}-rest`).style.display = "block"; e.target.remove(); });
  $(containerSel).querySelectorAll(`[data-topic-prefix="${prefix}"]`).forEach((btn) => btn.addEventListener("click", () => expandTopicCard(prefix, Number(btn.dataset.topicIdx))));
  const top = rows[0];
  if ($(readSel)) $(readSel).innerHTML = top
    ? `El tema del que más se habla es <b>${esc(top.topic)}</b> (${top.count} menciones, ${top.positive_pct}% a favor).` +
      (rows[1] ? ` Le siguen <b>${esc(rows[1].topic)}</b>${rows[2] ? ` y <b>${esc(rows[2].topic)}</b>` : ""}.` : "")
    : "Sin temas identificados todavía en el período.";
}
/* Abre (o cierra) los comentarios de ejemplo de una tarjeta de tema y la lleva a la vista —
   usable desde su propio botón o desde el clic en una barra del gráfico correspondiente. */
function expandTopicCard(prefix, i, { scroll = false } = {}) {
  const card = $(`#${prefix}-card-${i}`);
  if (!card) return;
  const rest = $(`#${prefix}-rest`);
  if (rest && rest.contains(card) && rest.style.display === "none") { rest.style.display = "block"; $(`#${prefix}-more`)?.remove(); }
  if (scroll) card.scrollIntoView({ behavior: "smooth", block: "center" });
  const btn = card.querySelector(`[data-topic-idx="${i}"]`);
  if (!btn) return;
  const open = btn.nextElementSibling?.classList.contains("thread") ? btn.nextElementSibling : null;
  if (open) {
    if (!scroll) { open.remove(); btn.textContent = btn.textContent.replace("▾", "▸"); }  // clic directo en el botón: cierra
    return;  // clic desde el gráfico: ya está abierto, solo hacer scroll (ya hecho arriba)
  }
  const t = topicStore[prefix][i];
  const div = document.createElement("div"); div.className = "thread";
  div.innerHTML = t.samples.map(quote).join("");
  btn.after(div);
  btn.textContent = btn.textContent.replace("▸", "▾");
}

/* ---------- perfil de candidato: se abre al tocar la tarjeta de Carlos o de un rival ---------- */
const TAB_LABELS = { resumen: "resumen", candidatos: "candidatos" };
let lastTab = "resumen";
async function openProfile(candidateId, name) {
  document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("active", p.id === "tab-perfil"));
  $("#perfil-back").textContent = `← Volver a ${TAB_LABELS[lastTab] || "resumen"}`;
  window.scrollTo({ top: 0 });
  $("#perfil-hero").innerHTML = `<div class="empty">Cargando…</div>`;
  $("#perfil-topics").innerHTML = ""; $("#perfil-feed").innerHTML = "";
  $("#perfil-topics-title").textContent = `${name}, tema por tema`;

  const rows = summaryRows.length ? summaryRows : await j(`/api/summary?days=${days()}`);
  const r = rows.find((x) => x.candidate_id === candidateId) || rows.find((x) => x.name === name);
  if (!r) { $("#perfil-hero").innerHTML = `<div class="empty">Sin datos de este candidato en el período.</div>`; return; }
  const rivals = rows.filter((x) => x !== r);
  $("#perfil-hero").innerHTML = heroHTML(r, rivals, "chart-gauge-perfil");
  renderGauge("#chart-gauge-perfil", (r.positive + r.negative + r.neutral) ? pct(r.positive, r.positive + r.negative + r.neutral) : 0);

  const [topics, feed] = await Promise.all([
    j(`/api/candidate/topics?name=${encodeURIComponent(r.name)}&days=${days()}`),
    j(`/api/feed?candidate_id=${r.candidate_id}&days=${days()}&limit=80`),
  ]);
  renderTopicCards("#perfil-topics", "#read-perfil-topics", topics, "perfil-t");
  renderFeedList("#perfil-feed", feed);
}
function closeProfile() {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === lastTab));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("active", p.id === `tab-${lastTab}`));
  window.scrollTo({ top: 0 });
}

async function loadStatus() {
  const s = await j("/health");
  $("#last-run").textContent = `Actualizado ${ago(s.last_run)}`;
  $("#status").innerHTML = `${s.total_mentions} menciones capturadas · ${s.scored} clasificadas · ${s.pending} pendientes · ${s.discarded} descartadas (homónimos / ajenas)<br>` +
    s.sources.map((x) => `${esc(x.name)}: ${x.total}${x.error ? ` <span style="color:var(--neg)" title="${esc(x.error)}">⚠</span>` : ""}`).join(" · ");
}

/* ---------- pestaña Candidatos: roster + comparación compacta ---------- */
function loadCandidatesTab(rows) {
  if (!$("#cand-kpis")) return;
  const byVol = [...rows].sort((a, b) => b.mentions - a.mentions);
  const scored = rows.filter((r) => r.positive + r.negative + r.neutral > 0);
  const byPos = [...scored].sort((a, b) => share(b, "positive") - share(a, "positive"));
  const totalMentions = rows.reduce((a, r) => a + r.mentions, 0);
  const totalPos = scored.reduce((a, r) => a + r.positive, 0);
  const totalScored = scored.reduce((a, r) => a + r.positive + r.negative + r.neutral, 0);

  $("#cand-kpis").innerHTML = `
    <div class="kpi"><div class="label">Candidatos monitoreados</div><div class="value">${rows.length}</div><div class="foot">${totalMentions} menciones · ${periodLabel()}</div></div>
    <div class="kpi"><div class="label">Más mencionado</div><div class="value" style="font-size:19px">${byVol[0] ? esc(byVol[0].name) : "—"}</div><div class="foot">${byVol[0] ? `${byVol[0].mentions} menciones` : ""}</div></div>
    <div class="kpi"><div class="label">Mejor imagen</div><div class="value pos" style="font-size:19px">${byPos[0] ? esc(byPos[0].name) : "—"}</div><div class="foot">${byPos[0] ? `${share(byPos[0], "positive")}% positivas` : ""}</div></div>
    <div class="kpi"><div class="label">Positividad promedio</div><div class="value">${totalScored ? pct(totalPos, totalScored) + "%" : "—"}</div><div class="foot">sobre ${totalScored} menciones clasificadas</div></div>`;

  hbar("#chart-cand-volume", byVol.map((r) => r.name), byVol.map((r) => r.mentions), byVol.map((r) => r.name === CARLOS ? BLUE : CARLOS_GRAY),
    { onClick: (i) => { const r = byVol[i]; openProfile(r.candidate_id, r.name); } });
  hbar100("#chart-cand-sentiment", scored.map((r) => r.name), [
    { name: "Positivas", data: scored.map((r) => share(r, "positive")) },
    { name: "Neutrales", data: scored.map((r) => share(r, "neutral")) },
    { name: "Negativas", data: scored.map((r) => share(r, "negative")) }], [GOOD, NEUTRAL_TONE, CRITICAL]);

  $("#cand-roster").innerHTML = rows.map((r) => `<button class="roster-card" data-candidate-id="${r.candidate_id}" data-name="${esc(r.name)}">
      ${avatar(r)}
      <div class="roster-body">
        <div class="name">${esc(r.name)}${r.name === CARLOS ? ` <span class="tag src">nuestro candidato</span>` : ""}</div>
        <div class="party">${esc(r.party || "sin partido")}</div>
        <div class="n">${r.mentions}<small>menciones${r.pending ? ` · ${r.pending} pend.` : ""}</small></div>
        ${bar(r)}
      </div>
    </button>`).join("");
}

async function loadAll() {
  const rows = await loadSummary();
  loadQuadrant(rows);
  loadCandidatesTab(rows);
  await Promise.all([loadTimeline(rows), loadSources(), loadTopics(), loadAlerts(), loadSocialStrong(),
    loadFeed(), loadFeedYoutube(), loadFeedReddit(), loadMeta(), loadMetaAnalytics(), loadStatus(), loadCity(),
    loadCityFeed(), loadHistorico(), loadInstitutionalHistory(), loadAgenda(), loadReporte(),
    (typeof loadCouncil === "function" ? loadCouncil() : null)]);
}

/* ---------- Reporte diario ---------- */
async function loadReporte() {
  if (!$("#rep-date")) return;
  const list = await j("/api/reports");
  const dates = list.map((r) => r.date);
  const sel = $("#rep-date");
  const cur = sel.value;
  sel.innerHTML = dates.length ? dates.map((d) => `<option value="${d}">${d}</option>`).join("")
    : `<option value="">Sin reportes todavía</option>`;
  sel.value = dates.includes(cur) ? cur : (dates[0] || "");
  if (sel.value) await showReport(sel.value);
  else $("#rep-body").innerHTML = `<div class="empty">Aún no se ha generado ningún reporte. Tocá "Generar el de hoy".</div>`;
}

async function showReport(date) {
  const r = await j(`/api/reports/${date}`);
  if (r.error) { $("#rep-body").innerHTML = `<div class="empty">${esc(r.error)}</div>`; return; }
  const k = r.social_kpis;
  const n = r.narrative;
  const reach = r.reach_comparison || [];
  const reaction = r.comment_reaction || [];
  const gaps = r.topic_gaps || [];
  const trendRows = reach.filter((c) => c.trend_pct !== null);

  $("#rep-body").innerHTML = `
    <section class="kpis">
      <div class="kpi"><div class="label">Publicaciones (redes)</div><div class="value">${k.total_posts}</div><div class="foot">últimos ${r.social_window_days} días</div></div>
      <div class="kpi"><div class="label">Likes</div><div class="value">${fmtNum(k.total_likes)}</div></div>
      <div class="kpi"><div class="label">Comentarios</div><div class="value">${fmtNum(k.total_comments)}</div></div>
      <div class="kpi"><div class="label">Pendiente de análisis</div><div class="value ${r.pending_review.total ? "neg" : ""}">${r.pending_review.total}</div></div>
    </section>
    ${n ? `
    <section class="intro panel">
      <h2>Resumen ejecutivo</h2>
      <p>${esc(n.resumen_ejecutivo)}</p>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Por qué el alcance de Carlos es el que es</h2><span class="hint">análisis basado en las cifras de este corte, últimos ${r.comparison_window_days} días</span></div>
      <p class="reading">${esc(n.analisis)}</p>
      ${n.limitaciones ? `<div class="limitations"><span class="label">Qué NO se puede determinar con estos datos</span>${esc(n.limitaciones)}</div>` : ""}
    </section>` : `
    <section class="intro panel">
      <h2>Análisis narrativo no disponible en este corte</h2>
      <p>El motor de análisis no respondió al generar este reporte. Las cifras y gráficas de abajo son reales e íntegras igual.</p>
    </section>`}
    <section class="panel">
      <div class="panel-head"><div><h2>Alcance promedio por publicación</h2><div class="hint">likes + comentarios por publicación, candidatos y concejales con al menos 2 posts en ${r.comparison_window_days} días. Carlos en azul.</div></div></div>
      <div class="chart-box" id="chart-rep-reach"></div>
    </section>
    ${trendRows.length ? `
    <section class="panel">
      <div class="panel-head"><div><h2>Tendencia de alcance</h2><div class="hint">variación entre la primera y la segunda mitad del período -- verde sube, rojo baja</div></div></div>
      <div class="chart-box" id="chart-rep-trend"></div>
    </section>` : ""}
    <section class="panel">
      <div class="panel-head"><div><h2>Reacción ciudadana en comentarios propios</h2><div class="hint">solo comentarios dejados en la publicación de cada quien, mínimo 3 comentarios</div></div></div>
      <div class="chart-box" id="chart-rep-reaction"></div>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Publicaciones por candidato y concejal</h2><span class="hint">últimos ${r.social_window_days} días</span></div>
      <div class="chart-box" id="chart-rep-candidates"></div>
    </section>
    <section class="panel alerts">
      <div class="panel-head"><h2>Actividad fuerte en redes</h2></div>
      <ul>${r.strong_social.length ? r.strong_social.map((p) => `<li>
        <span class="tag positive">${p.multiplier}×</span> <b>${esc(p.candidate)}</b>: ${esc(p.text).slice(0, 160)}
        <div class="meta">${SRC_LABEL[p.platform] || p.platform} · ❤️ ${fmtNum(p.likes)} · 💬 ${fmtNum(p.comments)}${p.url ? ` · <a href="${p.url}" target="_blank" rel="noopener">ver</a>` : ""}</div>
      </li>`).join("") : `<li class="empty">Sin publicaciones fuera de lo habitual.</li>`}</ul>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Temas de ciudad — los más mencionados</h2><span class="hint">últimos ${r.city_window_days} días</span></div>
      <div class="chart-box" id="chart-rep-topics"></div>
    </section>
    <section class="panel alerts">
      <div class="panel-head"><h2>Temas de ciudad de los que Carlos no ha hablado</h2><span class="hint">categorías con conversación real en la ciudad, sin ninguna publicación de Carlos</span></div>
      <ul>${gaps.length ? gaps.map((g) => `<li><b>${cap(g.category)}</b>: ${g.count} menciones en la ciudad, 0 de Carlos</li>`).join("") : `<li class="empty">Carlos tiene al menos una mención en todas las categorías activas.</li>`}</ul>
    </section>
    <section class="panel alerts">
      <div class="panel-head"><h2>Novedades donde Carlos podría hablar</h2></div>
      <ul>${r.city_opportunities.novedades.length ? r.city_opportunities.novedades.map((t) => `<li><b>${cap(t.topic)}</b> <span class="hint">(${cap(t.category)})</span>: ${t.count} menciones · Carlos: ${t.carlos_mentions === 0 ? "sin presencia" : `${t.carlos_mentions} menciones`}</li>`).join("") : `<li class="empty">Sin novedades sin presencia de Carlos en el período.</li>`}</ul>
    </section>
    ${n ? `
    <section class="panel alerts">
      <div class="panel-head"><h2>Estrategia recomendada</h2></div>
      <ul>${n.estrategia.map((s) => `<li>${esc(s)}</li>`).join("") || `<li class="empty">Sin recomendaciones en este corte.</li>`}</ul>
    </section>` : ""}
    <section class="panel">
      <div class="panel-head"><h2>Pendiente de análisis</h2><span class="hint">${r.pending_review.total} menciones totales sin clasificar aún, algunas de muestra abajo</span></div>
      <div class="feed">${r.pending_review.samples.length ? r.pending_review.samples.map((s) => `<article class="item">
        <div class="body">
          <div class="meta"><span class="cand">${esc(s.candidate)}</span><span class="tag src">${esc(s.source)}</span>${s.url ? `<a href="${s.url}" target="_blank" rel="noopener">ver original ↗</a>` : ""}</div>
          <div class="text">${esc(s.text)}</div>
        </div>
      </article>`).join("") : `<div class="empty">Nada pendiente por ahora.</div>`}</div>
    </section>`;

  const byCand = k.by_candidate;
  hbar("#chart-rep-candidates", byCand.map((c) => c.candidate), byCand.map((c) => c.count),
    byCand.map((c) => c.candidate === CARLOS ? BLUE : CARLOS_GRAY));
  hbar("#chart-rep-topics", r.city_topics.map((t) => cap(t.category)), r.city_topics.map((t) => t.count), BLUE);
  hbar("#chart-rep-reach", reach.map((c) => c.candidate), reach.map((c) => c.avg_engagement),
    reach.map((c) => c.candidate === CARLOS ? BLUE : CARLOS_GRAY));
  if (trendRows.length) {
    hbar("#chart-rep-trend", trendRows.map((c) => c.candidate), trendRows.map((c) => c.trend_pct),
      trendRows.map((c) => c.trend_pct >= 0 ? GOOD : CRITICAL), { labelFmt: (v) => (v >= 0 ? "+" : "") + v + "%" });
  }
  const withReaction = reaction.filter((c) => c.comments > 0);
  hbar100("#chart-rep-reaction", withReaction.map((c) => `${cap(c.candidate)} (${c.comments})`), [
    { name: "Positivo", data: withReaction.map((c) => c.positive_pct) },
    { name: "Neutral", data: withReaction.map((c) => c.neutral_pct) },
    { name: "Negativo", data: withReaction.map((c) => c.negative_pct) }], [GOOD, NEUTRAL_TONE, CRITICAL]);
}

$("#rep-date")?.addEventListener("change", () => showReport($("#rep-date").value));
$("#rep-generate")?.addEventListener("click", async () => {
  const b = $("#rep-generate"); b.disabled = true; b.textContent = "Generando…";
  try { await fetch("/api/reports/generate", { method: "POST" }); await loadReporte(); }
  finally { b.disabled = false; b.textContent = "Generar el de hoy"; }
});
$("#rep-pdf")?.addEventListener("click", () => {
  const d = $("#rep-date").value;
  if (d) window.open(`/api/reports/${d}/pdf`, "_blank");
});

document.querySelectorAll(".side-nav .tab").forEach((b) => b.addEventListener("click", () => {
  lastTab = b.dataset.tab;
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("active", p.id === `tab-${b.dataset.tab}`));
  window.scrollTo({ top: 0 });
  $(".sidebar")?.classList.remove("open");
  $("#menu-toggle")?.setAttribute("aria-expanded", "false");
}));
$("#menu-toggle")?.addEventListener("click", () => {
  const open = $(".sidebar").classList.toggle("open");
  $("#menu-toggle").setAttribute("aria-expanded", String(open));
});
document.querySelectorAll(".sub-nav .subtab").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".sub-nav .subtab").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll(".subtabpane").forEach((p) => p.classList.toggle("active", p.id === `subtab-${b.dataset.subtab}`));
}));
$("#perfil-back")?.addEventListener("click", closeProfile);
document.addEventListener("click", (e) => {
  const card = e.target.closest("[data-candidate-id]");
  if (card) openProfile(Number(card.dataset.candidateId), card.dataset.name);
});
$("#days").addEventListener("change", loadAllSafely);
["#f-candidate", "#f-label", "#f-emotion", "#f-category"].forEach((id) => $(id).addEventListener("change", loadFeed));
["#yt-f-candidate", "#yt-f-label", "#yt-f-emotion", "#yt-f-category"].forEach((id) => $(id).addEventListener("change", loadFeedYoutube));
["#rd-f-candidate", "#rd-f-label", "#rd-f-emotion", "#rd-f-category"].forEach((id) => $(id).addEventListener("change", loadFeedReddit));
["#meta-f-candidate", "#meta-f-platform", "#meta-f-sort"].forEach((id) => $(id).addEventListener("change", loadMeta));
["#city-f-source", "#city-f-label", "#city-f-emotion", "#city-f-category"].forEach((id) => $(id).addEventListener("change", loadCityFeed));
$("#refresh").addEventListener("click", async () => {
  const b = $("#refresh"); b.disabled = true; b.textContent = "Actualizando…";
  const clickedAt = Date.now();
  // try/finally: si algo de esto falla (red caída, refresh que tarda más de la cuenta), el botón
  // NO debe quedar "Actualizando…" deshabilitado para siempre -- antes eso pasaba.
  try {
    await fetch("/api/refresh", { method: "POST" });
    // Antes esperaba 25s fijos sin importar cuánto tardara en realidad; ahora consulta /health
    // hasta ver una corrida terminada después del clic (las fuentes ya corren en paralelo, así
    // que normalmente termina mucho antes). 90s es solo un salvavidas por si algo se cuelga.
    const deadline = Date.now() + 90000;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 1500));
      const s = await j("/health");
      if (s.last_run && new Date(s.last_run + "Z").getTime() > clickedAt) break;
    }
    await loadAll();
  } catch (err) {
    console.error("actualizar ahora falló:", err);
  } finally {
    b.disabled = false; b.textContent = "Actualizar ahora";
  }
});
/* Si algo falla en loadAll() (red caída, sesión de Cloudflare Access vencida, un endpoint que
   tira error), antes quedaba en silencio total -- Promise.all revienta con la primera falla y
   nadie se entera. Ahora al menos se avisa en la cabecera en vez de dejar todo con datos viejos
   sin ninguna señal. setInterval igual reintenta solo cada 2 minutos. */
async function loadAllSafely() {
  try {
    await loadAll();
  } catch (err) {
    console.error("loadAll falló:", err);
    if ($("#last-run")) $("#last-run").textContent = "No se pudo actualizar -- reintentando…";
  }
}
loadAllSafely();
setInterval(loadAllSafely, 120000);

/* ---------- ciudad ---------- */
const CAT_COLOR = BLUE;
function cap(s) { return s ? s[0].toUpperCase() + s.slice(1) : s; }

// Colores calcados de la rueda de emociones del cliente (ira=rojo, miedo=gris, asco=verde azulado,
// tristeza=violeta, felicidad=naranja, sorpresa=amarillo), tomados de la paleta ya validada.
const EMOTION_COLOR = { "ira": CRITICAL, "miedo": NEUTRAL_TONE, "asco": AQUA, "tristeza": VIOLET,
  "felicidad": ORANGE, "sorpresa": YELLOW, "sin emoción marcada": MUTED };
const EMOTIONS_ORDER = ["ira", "miedo", "asco", "tristeza", "felicidad", "sorpresa", "sin emoción marcada"];

async function loadCity() {
  if (!$("#city-kpis")) return;
  const d = days();
  const [topics, opps, kpis, emotions, emoByTopic] = await Promise.all([
    j(`/api/city/topics?days=${d}`), j(`/api/city/opportunities?days=${d}`), j(`/api/city/kpis?days=${d}`), j(`/api/city/emotions?days=${d}`),
    j(`/api/city/emotion-by-topic?days=${d}`)]);
  const topEmotion = emotions.find((e) => e.emotion !== "sin emoción marcada") || emotions[0];

  $("#city-kpis").innerHTML = `
    <div class="kpi"><div class="label">Menciones sobre la ciudad</div><div class="value">${kpis.total}</div><div class="foot">noticias, videos, posts y comentarios · ${periodLabel()}</div></div>
    <div class="kpi"><div class="label">Tema del que más se habla</div><div class="value" style="font-size:20px">${cap(kpis.top_category || "—")}</div><div class="foot">por número de menciones</div></div>
    <div class="kpi"><div class="label">Emoción dominante</div><div class="value" style="font-size:20px">${topEmotion ? cap(topEmotion.emotion) : "—"}</div><div class="foot">${topEmotion ? `${topEmotion.count} menciones` : ""}</div></div>
    <div class="kpi"><div class="label">Molestia ciudadana</div><div class="value ${kpis.negative_pct >= 40 ? "neg" : ""}">${kpis.total ? kpis.negative_pct + "%" : "—"}</div><div class="foot">menciones con queja, miedo o indignación</div></div>`;

  hbar("#chart-city-topics", topics.map((t) => cap(t.category)), topics.map((t) => t.count), CAT_COLOR,
    { onClick: (idx) => expandTopicCard("city-t", idx, { scroll: true }) });

  const scored = topics.filter((t) => t.count > 0);
  hbar100("#chart-city-perception", scored.map((t) => `${cap(t.category)} (${t.count})`), [
    { name: "Molestia", data: scored.map((t) => pct(t.negative, t.count)) },
    { name: "Informativa", data: scored.map((t) => pct(t.neutral, t.count)) },
    { name: "A favor", data: scored.map((t) => pct(t.positive, t.count)) }], [CRITICAL, NEUTRAL_TONE, GOOD]);

  hbar("#chart-city-emotions", emotions.map((e) => cap(e.emotion)), emotions.map((e) => e.count),
    emotions.map((e) => EMOTION_COLOR[e.emotion] || MUTED),
    { onClick: (idx) => {
      const e = emotions[idx];
      $("#city-emotion-detail").innerHTML = `<div class="topic-card"><div class="head"><h3>${cap(e.emotion)}</h3><div>${e.count} menciones</div></div>` +
        (e.samples.length ? e.samples.map(quote).join("") : `<div class="empty">Sin ejemplos de muestra para esta emoción.</div>`) + `</div>`;
      $("#city-emotion-detail").scrollIntoView({ behavior: "smooth", block: "nearest" });
    } });

  const novedades = opps.novedades, strong = opps.carlos_strong;
  $("#city-opps").innerHTML = `
    <div class="opp hot"><h3>Novedades donde Carlos podría hablar</h3>
      ${novedades.length ? `<ul>${novedades.map((t) => `<li><b>${cap(t.topic)}</b> <span class="hint">(${cap(t.category)})</span>: ${t.count} menciones${t.is_new ? " · tema nuevo" : ` · ${t.trend_pct}% más que el período anterior`} · ${pct(t.positive, t.count)}% a favor, ${pct(t.negative, t.count)}% molestia · Carlos: ${t.carlos_mentions === 0 ? "sin presencia" : `${t.carlos_mentions} menciones`}</li>`).join("")}</ul>` : `<div class="empty">No hay temas nuevos ni en alza sin presencia de Carlos en el período.</div>`}</div>
    <div class="opp strong"><h3>Temas donde Carlos ya suma</h3>
      ${strong.length ? `<ul>${strong.map((t) => `<li><b>${cap(t.category)}</b>: ${t.carlos_mentions} menciones de Carlos, ${t.carlos_positive_pct}% positivas · la ciudad habló ${t.city_count} veces del tema</li>`).join("")}</ul>` : `<div class="empty">Aún no hay temas con presencia positiva sostenida de Carlos en el período.</div>`}</div>`;

  const normalized = topics.map((t) => ({ topic: cap(t.category), count: t.count, positive: t.positive, neutral: t.neutral,
    negative: t.negative, positive_pct: pct(t.positive, t.count), sources: t.sources, samples: t.samples, subtopics: t.subtopics }));
  renderTopicCards("#city-detail", null, normalized, "city-t", 6);

  if ($("#chart-city-heatmap")) {
    const rows = emoByTopic.slice(0, 12);
    chart("#chart-city-heatmap", {
      chart: { type: "heatmap", height: Math.max(220, rows.length * 34) },
      series: rows.map((r) => ({ name: cap(r.category), data: EMOTIONS_ORDER.map((e) => ({ x: cap(e), y: r.emotions[e] || 0 })) })),
      colors: [BLUE],
      plotOptions: { heatmap: { colorScale: { ranges: [{ from: 0, to: 0, color: GRID }] } } },
      dataLabels: { enabled: true, style: { colors: [INK] } },
      xaxis: { labels: { style: { colors: MUTED } } },
      legend: { show: false },
    });
  }
}

/* ---------- Ciudad: feed completo de todo lo que pasa en Cali ---------- */
async function loadCityFeed() {
  if (!$("#city-feed")) return;
  const p = new URLSearchParams({ days: days(), limit: 80, city: true });
  if ($("#city-f-source").value) p.set("source_type", $("#city-f-source").value);
  if ($("#city-f-label").value) p.set("label", $("#city-f-label").value);
  if ($("#city-f-emotion").value) p.set("emotion", $("#city-f-emotion").value);
  if ($("#city-f-category").value) p.set("category", $("#city-f-category").value);
  renderFeedList("#city-feed", await j(`/api/feed?${p}`), { showCandidate: false });
}

/* ---------- Histórico: período actual vs. período anterior ---------- */
async function loadHistorico() {
  if (!$("#hist-kpis")) return;
  const topics = await j(`/api/city/topics?days=${days()}`);
  const totalNow = topics.reduce((a, t) => a + t.count, 0);
  const totalPrev = topics.reduce((a, t) => a + t.previous, 0);
  const totalTrend = totalPrev ? Math.round((totalNow - totalPrev) / totalPrev * 100) : null;
  const withTrend = topics.filter((t) => t.trend_pct !== null).sort((a, b) => b.trend_pct - a.trend_pct);
  const rising = withTrend[0];

  $("#hist-kpis").innerHTML = `
    <div class="kpi"><div class="label">Menciones ahora</div><div class="value">${totalNow}</div><div class="foot">${periodLabel()}</div></div>
    <div class="kpi"><div class="label">Menciones período anterior</div><div class="value">${totalPrev}</div><div class="foot">misma duración, inmediatamente antes</div></div>
    <div class="kpi"><div class="label">Variación total</div><div class="value ${totalTrend === null ? "" : totalTrend >= 0 ? "pos" : "neg"}">${totalTrend === null ? "—" : (totalTrend >= 0 ? "+" : "") + totalTrend + "%"}</div><div class="foot">vs el período anterior</div></div>
    <div class="kpi"><div class="label">Más creció</div><div class="value" style="font-size:18px">${rising ? cap(rising.category) : "—"}</div><div class="foot">${rising ? `+${rising.trend_pct}% vs antes` : "sin comparación disponible"}</div></div>`;

  hbar("#chart-hist-trend", withTrend.map((t) => cap(t.category)), withTrend.map((t) => t.trend_pct),
    withTrend.map((t) => t.trend_pct >= 0 ? GOOD : CRITICAL), { labelFmt: (v) => (v >= 0 ? "+" : "") + v + "%" });

  const sorted = [...topics].sort((a, b) => b.count - a.count);
  $("#hist-table").innerHTML = sorted.map((t) => {
    const badge = t.previous === 0 && t.count > 0 ? `<span class="tag positive">nuevo</span>`
      : t.trend_pct === null ? `<span class="hint">sin datos previos</span>`
      : `<span class="tag ${t.trend_pct >= 0 ? "positive" : "negative"}">${t.trend_pct >= 0 ? "+" : ""}${t.trend_pct}%</span>`;
    return `<div class="pcard"><div style="width:100%">
        <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap"><b>${cap(t.category)}</b>
          <span class="hint">${t.count} ahora · ${t.previous} antes · ${badge}</span></div>
      </div></div>`;
  }).join("") || `<div class="empty">Sin datos suficientes en el período.</div>`;
}

/* ---------- histórico institucional: proyectos y deuda por alcaldía ---------- */
const STATUS_TAG = { "completado": "positive", "en curso": "pending", "incompleto": "negative" };
let institutionalHistoryLoaded = false;
async function loadInstitutionalHistory() {
  if (!$("#hist-admins") || institutionalHistoryLoaded) return;
  institutionalHistoryLoaded = true;
  const data = await j("/api/institutional-history");
  const { administrations, debt_timeline } = data;

  hbar("#chart-hist-debt", debt_timeline.map((d) => `${d.mayor} (${d.period})`), debt_timeline.map((d) => d.value_billones_cop),
    RED, { labelFmt: (v) => `$${v} billones` });

  $("#hist-admins").innerHTML = administrations.map((a) => {
    const counts = a.status_counts;
    const debtLine = a.debt && a.debt.value_billones_cop != null
      ? `<div class="subs"><span class="tag negative">Deuda: ~$${a.debt.value_billones_cop} billones</span></div>
         <p class="hint" style="margin:4px 0 0">${esc(a.debt.note)} — <a href="${a.debt.source.url}" target="_blank" rel="noopener">fuente: ${esc(a.debt.source.name)}</a></p>`
      : a.debt ? `<p class="hint" style="margin:6px 0 0">${esc(a.debt.note)} — <a href="${a.debt.source.url}" target="_blank" rel="noopener">fuente: ${esc(a.debt.source.name)}</a></p>` : "";
    const metrics = (a.metrics || []).map((m) => `<div class="pcard" style="margin-top:8px"><div>
        <b>${esc(m.label)}</b>${m.change_pct != null ? ` <span class="tag ${m.change_pct <= 0 ? "positive" : "negative"}">${m.change_pct > 0 ? "+" : ""}${m.change_pct}%</span>` : ""}
        <div class="hint">${esc(m.note)}</div>
        <div class="hint">Fuente: <a href="${m.source.url}" target="_blank" rel="noopener">${esc(m.source.name)}</a></div>
      </div></div>`).join("");
    const projects = a.projects.map((p) => `<div class="pcard" style="margin-top:8px"><div>
        <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap"><b>${esc(p.name)}</b><span class="tag ${STATUS_TAG[p.status]}">${esc(p.status)}</span></div>
        <div class="hint">${esc(p.category)}</div>
        <p style="margin:6px 0">${esc(p.description)}</p>
        <div class="hint">Fuente: <a href="${p.source.url}" target="_blank" rel="noopener">${esc(p.source.name)}</a></div>
      </div></div>`).join("");
    return `<div class="panel">
      <div class="panel-head"><div><h2>${esc(a.mayor)}</h2><span class="hint">${esc(a.period)} · ${esc(a.party)} · <span class="tag ${a.status === "en curso" ? "pending" : "neutral"}">${esc(a.status)}</span></span></div></div>
      <p>${esc(a.summary)}</p>
      <div class="subs">
        <span class="tag positive">${counts.completado} completados</span>
        <span class="tag pending">${counts["en curso"]} en curso</span>
        <span class="tag negative">${counts.incompleto} incompletos</span>
      </div>
      ${debtLine}
      ${metrics}
      ${projects}
    </div>`;
  }).join("");
}

/* ---------- agenda ---------- */
function quote(m) {
  return `<div class="quote">“${esc(m.text).slice(0, 220)}”<div class="who">${srcName(m)} · ${esc(m.author || "")} · ${fmtDate(m.published_at)}${(m.link || m.url) ? ` · <a href="${m.link || m.url}" target="_blank" rel="noopener">ver ↗</a>` : ""}</div></div>`;
}

async function loadAgenda() {
  if (!$("#agenda-speak")) return;
  const d = days();
  const [a, perception] = await Promise.all([j(`/api/agenda?days=${d}`), j(`/api/perception?days=${d}`)]);

  $("#agenda-speak").innerHTML = a.speak.map((t, i) => `<div class="agenda-card speak">
      <div class="head"><h3><span class="rank">${i + 1}</span> ${t.category}</h3>
        <div><span class="tag negative">${t.negative_pct}% molestia</span> <span class="tag">${t.count} menciones</span> ${t.carlos_mentions === 0 ? `<span class="tag">Carlos: sin presencia</span>` : `<span class="tag positive">Carlos: ${t.carlos_mentions} menciones</span>`}</div></div>
      <div class="why">La ciudad habló ${t.count} veces de este tema y ${t.negative_pct}% de esas menciones son quejas o denuncias. ${t.carlos_mentions === 0 ? "<b>Carlos no ha aparecido en la conversación.</b>" : `Carlos ya tiene ${t.carlos_mentions} menciones aquí; hay espacio para reforzar.`}</div>
      ${t.subtopics.length ? `<div class="subs">${t.subtopics.map((x) => `<span class="tag">${esc(x.topic)} · ${x.count}</span>`).join("")}</div>` : ""}
      ${t.samples.slice(0, 2).map(quote).join("")}
    </div>`).join("") || `<div class="empty">No hay temas con molestia alta sin presencia de Carlos en el período.</div>`;
  const top = a.speak[0];
  $("#read-agenda-speak").innerHTML = top
    ? `La prioridad es <b>${top.category}</b>: ${top.count} menciones con ${top.negative_pct}% de molestia y ${top.carlos_mentions === 0 ? "ninguna mención" : `${top.carlos_mentions} ${top.carlos_mentions === 1 ? "mención" : "menciones"}`} de Carlos. ` +
      (a.speak[1] ? `Le siguen <b>${a.speak[1].category}</b>${a.speak[2] ? ` y <b>${a.speak[2].category}</b>` : ""}.` : "")
    : "Sin temas prioritarios en el período seleccionado.";

  $("#agenda-avoid").innerHTML = a.avoid.map((t) => `<div class="agenda-card avoid">
      <div class="head"><h3>${t.category}</h3><div><span class="tag negative">${t.candidate_negative_pct}% de rechazo</span> <span class="tag">${t.candidate_comments} reacciones</span></div></div>
      <div class="why">Cuando ${t.candidates.length === 1 ? "<b>" + esc(t.candidates[0]) + "</b> habló" : "<b>" + t.candidates.map(esc).join(", ") + "</b> hablaron"} de este tema, ${t.candidate_negative_pct}% de las reacciones ciudadanas fueron en contra. La ciudad lo menciona ${t.city_count} veces con ${t.city_negative_pct}% de molestia.</div>
      ${t.subtopics.length ? `<div class="subs">${t.subtopics.map((x) => `<span class="tag">${esc(x.topic)} · ${x.count}</span>`).join("")}</div>` : ""}
      ${t.samples.slice(0, 1).map(quote).join("")}
    </div>`).join("") || `<div class="empty">Ningún tema muestra rechazo mayoritario hacia los candidatos que lo tocaron.</div>`;
  $("#read-agenda-avoid").innerHTML = a.avoid.length
    ? `<b>${a.avoid[0].category}</b> es el terreno más hostil: ${a.avoid[0].candidate_negative_pct}% de las reacciones a quienes lo tocaron fueron negativas. Entrar ahí exige ángulo propio y propuesta concreta, no opinión general.`
    : "Ningún tema resultó hostil para los candidatos en el período.";

  const withComments = perception.filter((r) => r.comments > 0);
  hbar100("#chart-perception", withComments.map((r) => `${r.name} (${r.comments})`), [
    { name: "A favor", data: withComments.map((r) => r.positive_pct) },
    { name: "Neutral", data: withComments.map((r) => pct(r.neutral, r.comments)) },
    { name: "En contra", data: withComments.map((r) => r.negative_pct) }], [GOOD, NEUTRAL_TONE, CRITICAL]);
  const carlos = withComments.find((r) => r.name === CARLOS);
  const worst = [...withComments].sort((a, b) => b.negative_pct - a.negative_pct)[0];
  $("#read-perception").innerHTML = carlos
    ? `A <b>Carlos Arias</b> la gente le responde ${carlos.positive_pct}% a favor y ${carlos.negative_pct}% en contra sobre ${carlos.comments} comentarios. ` +
      (worst && worst.name !== CARLOS ? `El más golpeado es <b>${worst.name}</b>, con ${worst.negative_pct}% de reacciones en contra (${worst.comments} comentarios).` : "")
    : "Aún no hay comentarios ciudadanos sobre las publicaciones de Carlos en el período.";

  $("#perception-detail").innerHTML = withComments.map((r) => `<div class="pcard">
      ${avatar(r, "sm")}
      <div>
        <div class="head" style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap"><b>${esc(r.name)}</b><span class="hint">${r.comments} comentarios · ${r.positive_pct}% a favor · ${r.negative_pct}% en contra</span></div>
        ${r.topics.length ? `<div class="subs">${r.topics.map((t) => `<span class="tag">${esc(t.topic)} · ${t.count}</span>`).join("")}</div>` : ""}
        ${r.samples.slice(0, 2).map(quote).join("")}
      </div></div>`).join("") || `<div class="empty">Sin comentarios ciudadanos en el período.</div>`;
}
