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
/* Barras horizontales, una sola serie (ranking o magnitud). `perBar` = array de colores o un color fijo. */
function hbar(id, categories, data, perBar, { labelFmt } = {}) {
  chart(id, {
    chart: { type: "bar", height: "100%" },
    series: [{ data }], xaxis: { categories, labels: { style: { colors: MUTED } } },
    plotOptions: { bar: { horizontal: true, borderRadius: 4, distributed: Array.isArray(perBar), barHeight: "62%" } },
    colors: Array.isArray(perBar) ? perBar : [perBar],
    dataLabels: { enabled: true, formatter: labelFmt || ((v) => v), style: { colors: [INK], fontWeight: 600 }, offsetX: 6 },
    legend: { show: false },
  });
}
/* Barras horizontales apiladas al 100% (positivo/neutral/negativo, ya como % 0-100). */
function hbar100(id, categories, series) {
  chart(id, {
    chart: { type: "bar", stacked: true, height: "100%" },
    series, xaxis: { categories, max: 100, labels: { formatter: (v) => Math.round(v) + "%" } },
    plotOptions: { bar: { horizontal: true, borderRadius: 3, barHeight: "62%" } },
    colors: [GOOD, NEUTRAL_TONE, CRITICAL],
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

  const sel = $("#f-candidate"); const cur = sel.value;
  sel.innerHTML = `<option value="">Todos los candidatos</option>` + rows.map((r) => `<option value="${r.candidate_id}">${esc(r.name)}</option>`).join("");
  sel.value = cur;

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
    { name: "Negativas", data: scored.map((r) => share(r, "negative")) }]);
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

/* ---------- feed (reutilizable: pestaña Publicaciones y vista de Perfil) ---------- */
function srcName(m) { return m.platform ? (SRC_LABEL[m.platform] || m.platform) : (SRC[m.source_type] || esc(m.source)); }
function sentTag(m) {
  if (!m.label) return `<span class="tag pending">pendiente</span>`;
  return `<span class="tag ${m.label}">${LABEL[m.label]} ${m.score}</span>${m.topic ? `<div class="topic">${esc(m.topic)}</div>` : ""}`;
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
async function loadFeed() {
  if (!$("#f-candidate")) return;
  const p = new URLSearchParams({ days: days(), limit: 80 });
  if ($("#f-candidate").value) p.set("candidate_id", $("#f-candidate").value);
  if ($("#f-source").value) p.set("source_type", $("#f-source").value);
  if ($("#f-label").value) p.set("label", $("#f-label").value);
  renderFeedList("#feed", await j(`/api/feed?${p}`), { showCandidate: true });
}

/* ---------- tema por tema (genérico: se usa en el perfil de cualquier candidato) ---------- */
function topicCard(t, i, prefix) {
  return `<div class="topic-card">
      <div class="head"><h3>${esc(t.topic)}</h3><div>${t.count} menciones · <span class="tag ${t.positive_pct >= 60 ? "positive" : t.positive_pct <= 30 ? "negative" : ""}">${t.positive_pct}% a favor</span></div></div>
      <div class="subs"><span class="tag positive">${t.positive} positivas</span><span class="tag">${t.neutral} neutrales</span><span class="tag negative">${t.negative} negativas</span>
        ${Object.entries(t.sources).map(([src, n]) => `<span class="tag">${esc(SRC_LABEL[src] || SRC[src] || src)} · ${n}</span>`).join("")}</div>
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
  $(containerSel).querySelectorAll(`[data-topic-prefix="${prefix}"]`).forEach((btn) => btn.addEventListener("click", () => {
    const i = Number(btn.dataset.topicIdx); const t = topicStore[prefix][i];
    if (btn.nextElementSibling?.classList.contains("thread")) { btn.nextElementSibling.remove(); btn.textContent = btn.textContent.replace("▾", "▸"); return; }
    const div = document.createElement("div"); div.className = "thread";
    div.innerHTML = t.samples.map(quote).join("");
    btn.after(div);
    btn.textContent = btn.textContent.replace("▸", "▾");
  }));
  const top = rows[0];
  if ($(readSel)) $(readSel).innerHTML = top
    ? `El tema del que más se habla es <b>${esc(top.topic)}</b> (${top.count} menciones, ${top.positive_pct}% a favor).` +
      (rows[1] ? ` Le siguen <b>${esc(rows[1].topic)}</b>${rows[2] ? ` y <b>${esc(rows[2].topic)}</b>` : ""}.` : "")
    : "Sin temas identificados todavía en el período.";
}

/* ---------- perfil de candidato: se abre al tocar la tarjeta de Carlos o de un rival ---------- */
async function openProfile(candidateId, name) {
  document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("active", p.id === "tab-perfil"));
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
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === "resumen"));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("active", p.id === "tab-resumen"));
  window.scrollTo({ top: 0 });
}

async function loadStatus() {
  const s = await j("/health");
  $("#last-run").textContent = `Actualizado ${ago(s.last_run)}`;
  $("#status").innerHTML = `${s.total_mentions} menciones capturadas · ${s.scored} clasificadas · ${s.pending} pendientes · ${s.discarded} descartadas (homónimos / ajenas)<br>` +
    s.sources.map((x) => `${esc(x.name)}: ${x.total}${x.error ? ` <span style="color:var(--neg)" title="${esc(x.error)}">⚠</span>` : ""}`).join(" · ");
}

async function loadAll() {
  const rows = await loadSummary();
  loadQuadrant(rows);
  await Promise.all([loadTimeline(rows), loadSources(), loadTopics(), loadAlerts(), loadFeed(), loadStatus(), loadCity(), loadAgenda(), (typeof loadCouncil === "function" ? loadCouncil() : null)]);
}

document.querySelectorAll(".side-nav .tab").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("active", p.id === `tab-${b.dataset.tab}`));
  window.scrollTo({ top: 0 });
}));
$("#perfil-back")?.addEventListener("click", closeProfile);
document.addEventListener("click", (e) => {
  const card = e.target.closest("[data-candidate-id]");
  if (card) openProfile(Number(card.dataset.candidateId), card.dataset.name);
});
$("#days").addEventListener("change", loadAll);
["#f-candidate", "#f-source", "#f-label"].forEach((id) => $(id).addEventListener("change", loadFeed));
$("#refresh").addEventListener("click", async () => {
  const b = $("#refresh"); b.disabled = true; b.textContent = "Actualizando…";
  await fetch("/api/refresh", { method: "POST" });
  setTimeout(async () => { await loadAll(); b.disabled = false; b.textContent = "Actualizar ahora"; }, 25000);
});
loadAll();
setInterval(loadAll, 120000);

/* ---------- ciudad ---------- */
const CAT_COLOR = BLUE;
function trendTag(t) {
  if (t === null || t === undefined) return `<span class="trend flat">nuevo</span>`;
  if (t > 5) return `<span class="trend up">▲ ${t}%</span>`;
  if (t < -5) return `<span class="trend down">▼ ${Math.abs(t)}%</span>`;
  return `<span class="trend flat">= estable</span>`;
}
function cap(s) { return s ? s[0].toUpperCase() + s.slice(1) : s; }

async function loadCity() {
  if (!$("#city-kpis")) return;
  const d = days();
  const [topics, opps, kpis] = await Promise.all([j(`/api/city/topics?days=${d}`), j(`/api/city/opportunities?days=${d}`), j(`/api/city/kpis?days=${d}`)]);

  $("#city-kpis").innerHTML = `
    <div class="kpi"><div class="label">Menciones sobre la ciudad</div><div class="value">${kpis.total}</div><div class="foot">noticias, videos, posts y comentarios · ${periodLabel()}</div></div>
    <div class="kpi"><div class="label">Tema del que más se habla</div><div class="value" style="font-size:20px">${cap(kpis.top_category || "—")}</div><div class="foot">por número de menciones</div></div>
    <div class="kpi"><div class="label">Tema que más crece</div><div class="value" style="font-size:20px">${cap(kpis.rising_category || "—")}</div><div class="foot">${kpis.rising_pct !== null && kpis.rising_pct !== undefined ? `▲ ${kpis.rising_pct}% vs período anterior` : "sin período anterior"}</div></div>
    <div class="kpi"><div class="label">Molestia ciudadana</div><div class="value ${kpis.negative_pct >= 40 ? "neg" : ""}">${kpis.total ? kpis.negative_pct + "%" : "—"}</div><div class="foot">menciones con queja, miedo o indignación</div></div>`;

  hbar("#chart-city-topics", topics.map((t) => cap(t.category)), topics.map((t) => t.count), CAT_COLOR,
    { labelFmt: (v, o) => { const t = topics[o.dataPointIndex]; const tr = t.trend_pct; return tr === null || tr === undefined ? `${v}` : `${v}  ${tr > 5 ? "▲" : tr < -5 ? "▼" : "="} ${Math.abs(tr)}%`; } });
  const rising = topics.filter((t) => t.trend_pct !== null).sort((a, b) => b.trend_pct - a.trend_pct)[0];
  $("#read-city-topics").innerHTML = topics.length
    ? `En ${periodLabel()}, Cali habló sobre todo de <b>${topics[0].category}</b> (${topics[0].count} menciones)` + (topics[1] ? `, luego de <b>${topics[1].category}</b> (${topics[1].count})` : "") + (topics[2] ? ` y <b>${topics[2].category}</b> (${topics[2].count})` : "") + ". " +
      (rising && rising.trend_pct > 5 ? `El tema que más crece es <b>${rising.category}</b> (▲ ${rising.trend_pct}% frente al período anterior).` : "Ningún tema muestra un crecimiento marcado frente al período anterior.")
    : "Aún no hay menciones de ciudad clasificadas en el período.";

  const scored = topics.filter((t) => t.count > 0);
  hbar100("#chart-city-perception", scored.map((t) => `${cap(t.category)} (${t.count})`), [
    { name: "Molestia", data: scored.map((t) => pct(t.negative, t.count)) },
    { name: "Informativa", data: scored.map((t) => pct(t.neutral, t.count)) },
    { name: "A favor", data: scored.map((t) => pct(t.positive, t.count)) }]);
  const angriest = [...scored].sort((a, b) => pct(b.negative, b.count) - pct(a.negative, a.count))[0];
  const happiest = [...scored].sort((a, b) => pct(b.positive, b.count) - pct(a.positive, a.count))[0];
  $("#read-city-perception").innerHTML = scored.length
    ? `Donde más molestia hay es en <b>${angriest.category}</b> (${pct(angriest.negative, angriest.count)}% de las menciones son quejas o denuncias). ` +
      `El tema mejor recibido es <b>${happiest.category}</b> (${pct(happiest.positive, happiest.count)}% a favor).`
    : "Sin datos en el período.";

  const hot = opps.hot_without_carlos, strong = opps.carlos_strong;
  $("#city-opps").innerHTML = `
    <div class="opp hot"><h3>La ciudad está molesta y Carlos no está hablando de esto</h3>
      ${hot.length ? `<ul>${hot.map((t) => `<li><b>${cap(t.category)}</b>: ${t.count} menciones, ${t.negative_pct}% de molestia · Carlos: ${t.carlos_mentions} menciones${t.subtopics.length ? ` · ej. ${t.subtopics.map((s) => s.topic).slice(0, 2).join(", ")}` : ""}</li>`).join("")}</ul>` : `<div class="empty">No hay temas calientes sin presencia de Carlos en el período.</div>`}</div>
    <div class="opp strong"><h3>Temas donde Carlos ya suma</h3>
      ${strong.length ? `<ul>${strong.map((t) => `<li><b>${cap(t.category)}</b>: ${t.carlos_mentions} menciones de Carlos, ${t.carlos_positive_pct}% positivas · la ciudad habló ${t.city_count} veces del tema</li>`).join("")}</ul>` : `<div class="empty">Aún no hay temas con presencia positiva sostenida de Carlos en el período.</div>`}</div>`;

  $("#city-detail").innerHTML = topics.map((t) => `<div class="topic-card">
      <div class="head"><h3>${t.category}</h3><div>${trendTag(t.trend_pct)} · ${t.count} menciones · <span class="tag negative">${pct(t.negative, t.count)}% molestia</span></div></div>
      <div class="subs">${t.subtopics.map((s) => `<span class="tag">${esc(s.topic)} · ${s.count}</span>`).join("") || `<span class="hint">sin subtemas identificados</span>`}</div>
      ${t.samples.map((m) => `<div class="comment"><div>${esc(m.text).slice(0, 240)}<div class="who">${srcName(m)} · ${esc(m.author || "")} · ${fmtDate(m.published_at)}${m.url ? ` · <a href="${m.url}" target="_blank" rel="noopener">ver</a>` : ""}</div></div><div>${sentTag(m)}</div></div>`).join("")}
    </div>`).join("") || `<div class="empty">Sin temas en el período.</div>`;
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
    { name: "En contra", data: withComments.map((r) => r.negative_pct) }]);
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
