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
let feedRows = [];

Chart.register(ChartDataLabels);
Chart.defaults.font.family = "Inter, system-ui, sans-serif";
Chart.defaults.color = MUTED;
Chart.defaults.plugins.datalabels.display = false;

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
function chart(id, cfg) { if (charts[id]) charts[id].destroy(); charts[id] = new Chart($(id), cfg); }
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

/* ---------- KPIs + panel de Carlos + tarjetas + gráficas de candidatos ---------- */
async function loadSummary() {
  const rows = await j(`/api/summary?days=${days()}`);
  const alerts = await j(`/api/alerts?days=${days()}`);
  const carlos = rows.find((r) => r.name === CARLOS) || rows[0];
  const rivals = rows.filter((r) => r !== carlos);
  const total = rows.reduce((a, r) => a + r.mentions, 0);
  const cScored = carlos.positive + carlos.negative + carlos.neutral;
  const rivalsPos = rivals.reduce((a, r) => a + r.positive, 0), rivalsScored = rivals.reduce((a, r) => a + r.positive + r.negative + r.neutral, 0);
  const cPct = pct(carlos.positive, cScored), rPct = pct(rivalsPos, rivalsScored);

  $("#kpis").innerHTML = `
    <div class="kpi"><div class="label">Menciones en el período</div><div class="value">${total}</div><div class="foot">notas, posts y comentarios · ${rows.length} candidatos</div></div>
    <div class="kpi"><div class="label">Menciones de Carlos Arias</div><div class="value">${carlos.mentions}</div><div class="foot">${carlos.previous ? `${carlos.mentions >= carlos.previous ? "▲" : "▼"} ${Math.abs(Math.round((carlos.mentions - carlos.previous) / carlos.previous * 100))}% vs período anterior` : "sin período anterior"}</div></div>
    <div class="kpi"><div class="label">Positividad de Carlos Arias</div><div class="value ${cPct >= 50 ? "pos" : ""}">${cScored ? cPct + "%" : "—"}</div><div class="foot">rivales: ${rivalsScored ? rPct + "%" : "—"} en promedio</div></div>
    <div class="kpi"><div class="label">Alertas activas</div><div class="value ${alerts.length ? "neg" : ""}">${alerts.length}</div><div class="foot">menciones negativas (≤ −0.5) sobre Carlos</div></div>`;

  const diff = cScored && rivalsScored ? cPct - rPct : null;
  $("#hero").innerHTML = `
    ${avatar(carlos)}
    <div>
      <div class="name">${esc(carlos.name)}</div><div class="party">${esc(carlos.party || "")}</div>
      <div class="stats">
        <div class="stat"><div class="n">${carlos.mentions}</div><div class="l">menciones</div></div>
        <div class="stat"><div class="n" style="color:var(--pos)">${carlos.positive}</div><div class="l">positivas</div></div>
        <div class="stat"><div class="n" style="color:var(--neu)">${carlos.neutral}</div><div class="l">neutrales</div></div>
        <div class="stat"><div class="n" style="color:var(--neg)">${carlos.negative}</div><div class="l">negativas</div></div>
        ${carlos.pending ? `<div class="stat"><div class="n" style="color:var(--muted)">${carlos.pending}</div><div class="l">pendientes de análisis</div></div>` : ""}
      </div>
      <div style="margin-top:10px">${bar(carlos)}</div>
      <div class="legend"><span><i style="background:var(--pos)"></i>positivo</span><span><i style="background:var(--neu)"></i>neutral</span><span><i style="background:var(--neg)"></i>negativo</span></div>
    </div>
    <div class="compare">
      <div class="hint">frente al promedio de rivales</div>
      <div class="big ${diff === null ? "" : diff >= 0 ? "pos" : "neg"}">${diff === null ? "—" : `${diff >= 0 ? "+" : ""}${diff} pts`}</div>
      <div class="hint">de positividad (${cScored ? cPct : "—"}% vs ${rivalsScored ? rPct : "—"}%)</div>
    </div>`;

  $("#cards").innerHTML = rivals.map((r) => `<div class="card">
      ${avatar(r, "sm")}
      <div>
        <div class="name">${esc(r.name)}</div><div class="party">${esc(r.party || "")}</div>
        <div class="n">${r.mentions}<small>menciones${r.pending ? ` · ${r.pending} pend.` : ""}</small></div>
        ${bar(r)}
      </div></div>`).join("");

  const sel = $("#f-candidate"); const cur = sel.value;
  sel.innerHTML = `<option value="">Todos los candidatos</option>` + rows.map((r) => `<option value="${r.candidate_id}">${esc(r.name)}</option>`).join("");
  sel.value = cur;

  // ¿De quién se habla más?
  const byVol = [...rows].sort((a, b) => b.mentions - a.mentions);
  chart("#chart-volume", {
    type: "bar",
    data: { labels: byVol.map((r) => r.name), datasets: [{ data: byVol.map((r) => r.mentions), backgroundColor: byVol.map((r) => r.name === CARLOS ? BLUE : CARLOS_GRAY), borderRadius: 6, barThickness: 22 }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, datalabels: { display: true, anchor: "end", align: "end", color: INK, font: { weight: 600 }, formatter: (v) => v } },
      scales: { x: { beginAtZero: true, grid: { color: GRID }, ticks: { precision: 0 }, grace: "12%", title: { display: true, text: "menciones en el período" } }, y: { grid: { display: false } } } },
  });
  const vRank = byVol.findIndex((r) => r.name === CARLOS);
  const tied = byVol.filter((r) => r.mentions === carlos.mentions && r.name !== CARLOS);
  $("#read-volume").innerHTML = `En ${periodLabel()} se registraron <b>${total} menciones</b> de los ${rows.length} candidatos. ` +
    (vRank === 0
      ? `<b>Carlos Arias</b> es de quien más se habla, con ${carlos.mentions} menciones${tied.length ? ` (empatado con ${tied.map((r) => esc(r.name)).join(" y ")})` : ""}; le sigue ${esc((byVol.find((r) => r.mentions < carlos.mentions) || {}).name || "")}.`
      : `<b>${esc(byVol[0].name)}</b> es de quien más se habla (${byVol[0].mentions}). <b>Carlos Arias</b> ocupa el ${ordinal(vRank)} lugar con ${carlos.mentions} menciones, ${byVol[0].mentions - carlos.mentions} menos.`);

  // ¿Cómo se habla de cada candidato?
  const scored = rows.filter((r) => r.positive + r.negative + r.neutral > 0);
  chart("#chart-sentiment", {
    type: "bar",
    data: { labels: scored.map((r) => `${r.name} (${r.positive + r.negative + r.neutral})`), datasets: [
      { label: "Positivas", data: scored.map((r) => share(r, "positive")), backgroundColor: GOOD },
      { label: "Neutrales", data: scored.map((r) => share(r, "neutral")), backgroundColor: NEUTRAL_TONE },
      { label: "Negativas", data: scored.map((r) => share(r, "negative")), backgroundColor: CRITICAL }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw}%` } },
        datalabels: { display: (c) => c.dataset.data[c.dataIndex] >= 8, color: (c) => c.datasetIndex === 1 ? INK_SOFT : "#fff", font: { weight: 600, size: 12 }, formatter: (v) => v + "%" } },
      scales: { x: { stacked: true, max: 100, ticks: { callback: (v) => v + "%" }, grid: { color: GRID }, title: { display: true, text: "de cada 100 menciones clasificadas" } }, y: { stacked: true, grid: { display: false } } } },
  });
  const byPos = [...scored].sort((a, b) => share(b, "positive") - share(a, "positive"));
  const byNeg = [...scored].sort((a, b) => share(b, "negative") - share(a, "negative"));
  const cRank = byPos.findIndex((r) => r.name === CARLOS);
  $("#read-sentiment").innerHTML = scored.length ? `<b>${esc(byPos[0].name)}</b> tiene la mejor imagen: ${share(byPos[0], "positive")}% de sus menciones son positivas. ` +
    `<b>${esc(byNeg[0].name)}</b> concentra la mayor carga negativa (${share(byNeg[0], "negative")}% negativas). ` +
    (cRank >= 0 ? `<b>Carlos Arias</b> es ${ordinal(cRank)} en positividad, con ${share(carlos, "positive")}% positivas y ${share(carlos, "negative")}% negativas sobre ${cScored} menciones clasificadas.` : "")
    : "Aún no hay menciones clasificadas en el período.";
  return rows;
}

let timelineMeta = { labels: [], details: {}, rows: [] };
async function loadTimeline(rows) {
  const span = Math.max(days(), 7);
  const [d, details] = await Promise.all([j(`/api/timeline?days=${span}`), j(`/api/timeline/details?days=${span}`)]);
  timelineMeta = { labels: d.labels, details, rows };
  const top = [CARLOS, ...rows.filter((r) => r.name !== CARLOS).sort((a, b) => b.mentions - a.mentions).slice(0, 4).map((r) => r.name)];
  const series = d.series.filter((s) => top.includes(s.name));
  const pubOf = (name, i) => (details[name] || {})[d.labels[i]];
  chart("#chart-timeline", {
    type: "line",
    data: { labels: d.labels.map((l) => l.slice(5).replace("-", "/")), datasets: series.map((s, i) => ({
      label: s.name, data: s.data, borderColor: COLORS[i % COLORS.length], backgroundColor: COLORS[i % COLORS.length],
      tension: .35, borderWidth: s.name === CARLOS ? 3.5 : 1.5, pointRadius: s.name === CARLOS ? 3 : 2, pointHoverRadius: 6 })) },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "nearest", intersect: true },
      onClick: (evt, els) => { if (els.length) showDay(series[els[0].datasetIndex].name, d.labels[els[0].index]); },
      onHover: (evt, els) => { evt.native.target.style.cursor = els.length ? "pointer" : "default"; },
      plugins: { legend: { position: "bottom" }, tooltip: { callbacks: {
        afterBody: (items) => items.flatMap((it) => {
          const p = pubOf(it.dataset.label, it.dataIndex);
          if (!p) return [];
          return [`${p.count} de ${p.total} por: "${p.text.slice(0, 80)}${p.text.length > 80 ? "…" : ""}" (${srcName(p)})`, "clic para ver todas las publicaciones del día"];
        }) } } },
      scales: { y: { beginAtZero: true, grid: { color: GRID }, ticks: { precision: 0 }, title: { display: true, text: "menciones por día" } }, x: { ticks: { maxTicksLimit: 10, maxRotation: 0 }, grid: { display: false } } } },
  });
  const cs = series.find((s) => s.name === CARLOS);
  if (cs) {
    const peakIdx = cs.data.reduce((best, v, i) => (v > cs.data[best] ? i : best), 0);
    const peakDate = new Date(d.labels[peakIdx] + "T12:00:00").toLocaleDateString("es-CO", { day: "numeric", month: "long" });
    const active = cs.data.filter((v) => v > 0).length;
    const pk = pubOf(CARLOS, peakIdx);
    const cause = pk ? ` ${pk.count} de ellas vinieron de ${pk.kind === "news" ? "la nota" : pk.kind === "video" ? "el video" : "la publicación"} <b>«${esc(pk.text).slice(0, 90)}»</b> (${srcName(pk)})${pk.url ? ` — <a href="${pk.url}" target="_blank" rel="noopener">ver ↗</a>` : ""}.` : "";
    const others = series.filter((s) => s.name !== CARLOS).map((s) => {
      const i = s.data.reduce((best, v, k) => (v > s.data[best] ? k : best), 0); const p = pubOf(s.name, i);
      return p ? `${s.name}: ${s.data[i]} el ${new Date(d.labels[i] + "T12:00:00").toLocaleDateString("es-CO", { day: "numeric", month: "short" })} por «${esc(p.text).slice(0, 50)}»` : null;
    }).filter(Boolean);
    $("#read-timeline").innerHTML = `<b>Carlos Arias</b> tuvo su pico el <b>${peakDate}</b> con ${cs.data[peakIdx]} menciones en un día, y apareció en ${active} de los ${d.labels.length} días mostrados.${cause}` +
      (others.length ? `<br><span class="hint">Picos de los rivales — ${others.join(" · ")}.</span>` : "") +
      `<br><span class="hint">Pasa el mouse por cualquier punto para ver qué publicación pesó ese día; haz clic para ver todas.</span>`;
  }
}

async function showDay(name, day) {
  const row = timelineMeta.rows.find((r) => r.name === name);
  if (!row) return;
  const box = $("#day-detail");
  const nice = new Date(day + "T12:00:00").toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" });
  box.innerHTML = `<div class="panel-head"><h2>${esc(name)} · ${nice}</h2><button class="toggle" id="day-close">cerrar ✕</button></div><div class="feed"><div class="empty">Cargando…</div></div>`;
  box.style.display = "block";
  box.scrollIntoView({ behavior: "smooth", block: "start" });
  $("#day-close").addEventListener("click", () => { box.style.display = "none"; });
  const rows = await j(`/api/feed?candidate_id=${row.candidate_id}&days=${Math.max(days(), 7) + 1}&day=${day}&limit=100`);
  box.querySelector(".feed").innerHTML = rows.map((r, i) => `<article class="item">
    ${thumb(r)}
    <div class="body">
      <div class="meta"><span class="tag src">${srcName(r)} · ${KIND[r.kind] || ""}</span><span>${fmtDate(r.published_at)}</span>${r.url ? `<a href="${r.url}" target="_blank" rel="noopener">ver original ↗</a>` : ""}</div>
      <div class="text">${esc(r.text)}</div>
      ${r.summary ? `<div class="summary">📝 ${esc(r.summary)}</div>` : ""}
      ${r.author ? `<div class="author">${esc(r.author)}</div>` : ""}
      ${r.comments.length ? `<div class="thread">${r.comments.slice(0, 8).map((c) => `<div class="comment"><div>${esc(c.text).slice(0, 200)}<div class="who">${esc(c.author || "")}</div></div><div>${sentTag(c)}</div></div>`).join("")}${r.comments.length > 8 ? `<div class="hint">… y ${r.comments.length - 8} comentarios más</div>` : ""}</div>` : ""}
    </div>
    <div class="side">${r.kind === "comments" ? `<span class="hint">solo comentarios</span>` : sentTag(r)}${r.comments_summary.total ? `<div class="counts">${r.comments_summary.total} comentarios · ${r.comments_summary.positive} ▲ ${r.comments_summary.neutral} ● ${r.comments_summary.negative} ▼</div>` : ""}</div>
  </article>`).join("") || `<div class="empty">Sin publicaciones ese día.</div>`;
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
    type: "bar",
    data: { labels: d.candidates, datasets: labels.map((l) => ({ label: l, data: groups[l], backgroundColor: SRC_COLOR[l] || MUTED, borderRadius: 3 })) },
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" }, datalabels: { display: (c) => c.dataset.data[c.dataIndex] >= 6, color: "#fff", font: { weight: 600, size: 11 } } },
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, grid: { color: GRID }, ticks: { precision: 0 }, title: { display: true, text: "menciones" } } } },
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
  const cfg = (t, thick, color) => ({
    type: "bar",
    data: { labels: t.map((x) => x.topic), datasets: [{ data: t.map((x) => x.count), backgroundColor: color, borderRadius: 4, barThickness: thick }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, datalabels: { display: true, anchor: "end", align: "end", color: INK, font: { weight: 600 } } },
      scales: { x: { beginAtZero: true, grid: { color: GRID }, ticks: { precision: 0 }, grace: "12%", title: { display: true, text: "menciones" } }, y: { grid: { display: false } } } },
  });
  chart("#chart-topics", cfg(com, 14, VIOLET));
  chart("#chart-topics-pub", cfg(pub, 20, BLUE));
  chart("#chart-topics-com", cfg(com, 20, VIOLET));
  const reading = (t, what) => t.length
    ? `El asunto más frecuente en ${what} es <b>${esc(t[0].topic)}</b> (${t[0].count})` + (t[1] ? `, seguido de <b>${esc(t[1].topic)}</b> (${t[1].count})` : "") + (t[2] ? ` y <b>${esc(t[2].topic)}</b> (${t[2].count})` : "") + "."
    : `Sin asuntos identificados en ${what} para el período.`;
  $("#read-topics-pub").innerHTML = reading(pub, "las noticias y publicaciones");
  $("#read-topics-com").innerHTML = reading(com, "los comentarios de la gente");
}

async function loadAlerts() {
  const a = await j(`/api/alerts?days=${days()}`);
  $("#alerts").innerHTML = a.length ? a.map((m) => `<li>
    <span class="tag negative">${m.score}</span> ${esc(m.text).slice(0, 200)}
    <div class="meta">${srcName(m)} · ${esc(m.author || "")} · ${ago(m.published_at)}${m.url ? ` · <a href="${m.url}" target="_blank" rel="noopener">ver</a>` : ""}</div>
  </li>`).join("") : `<li class="empty">Sin menciones negativas fuertes sobre Carlos Arias en el período.</li>`;
}

/* ---------- feed ---------- */
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
async function loadFeed() {
  const p = new URLSearchParams({ days: days(), limit: 80 });
  if ($("#f-candidate").value) p.set("candidate_id", $("#f-candidate").value);
  if ($("#f-source").value) p.set("source_type", $("#f-source").value);
  if ($("#f-label").value) p.set("label", $("#f-label").value);
  feedRows = await j(`/api/feed?${p}`);
  $("#feed").innerHTML = feedRows.map((r, i) => `<article class="item" data-row="${i}">
    ${thumb(r)}
    <div class="body">
      <div class="meta"><span class="cand">${esc(r.candidate)}</span><span class="tag src">${srcName(r)} · ${KIND[r.kind] || ""}</span><span>${fmtDate(r.published_at)}</span>${r.url ? `<a href="${r.url}" target="_blank" rel="noopener">ver original ↗</a>` : ""}</div>
      <div class="text">${esc(r.text)}</div>
      ${r.summary ? `<div class="summary">📝 ${esc(r.summary)}</div>` : ""}
      ${r.author ? `<div class="author">${esc(r.author)}</div>` : ""}
    </div>
    <div class="side">
      ${r.kind === "comments" ? `<span class="hint">solo comentarios</span>` : sentTag(r)}
      ${commentsBlock(r, i)}
    </div>
  </article>`).join("") || `<div class="empty">Sin publicaciones con esos filtros.</div>`;
  $("#feed").querySelectorAll(".toggle").forEach((b) => b.addEventListener("click", () => toggleComments(Number(b.dataset.idx), b)));
}
function toggleComments(idx, btn) {
  const item = $(`#feed .item[data-row="${idx}"]`);
  const open = item.querySelector(".thread");
  if (open) { open.remove(); btn.textContent = btn.textContent.replace("▾", "▸"); return; }
  const r = feedRows[idx];
  const div = document.createElement("div"); div.className = "thread";
  div.innerHTML = r.comments.map((c) => `<div class="comment">
      <div>${esc(c.text)}<div class="who">${esc(c.author || "")} · ${fmtDate(c.published_at)}${(c.link || c.url) ? ` · <a href="${c.link || c.url}" target="_blank" rel="noopener">ver</a>` : ""}</div></div>
      <div>${sentTag(c)}</div></div>`).join("") || `<div class="empty">Sin comentarios que cumplan el filtro.</div>`;
  item.appendChild(div);
  btn.textContent = btn.textContent.replace("▸", "▾");
}

let carlosTopicRows = [];
const CARLOS_TOPICS_VISIBLE = 5;

function carlosTopicCard(t, i) {
  return `<div class="topic-card">
      <div class="head"><h3>${esc(t.topic)}</h3><div>${t.count} menciones · <span class="tag ${t.positive_pct >= 60 ? "positive" : t.positive_pct <= 30 ? "negative" : ""}">${t.positive_pct}% a favor</span></div></div>
      <div class="subs"><span class="tag positive">${t.positive} positivas</span><span class="tag">${t.neutral} neutrales</span><span class="tag negative">${t.negative} negativas</span>
        ${Object.entries(t.sources).map(([src, n]) => `<span class="tag">${esc(SRC_LABEL[src] || SRC[src] || src)} · ${n}</span>`).join("")}</div>
      <button class="toggle" data-ct-idx="${i}">▸ ver ${t.samples.length} comentario${t.samples.length === 1 ? "" : "s"} de ejemplo</button>
    </div>`;
}

async function loadCarlosTopics() {
  if (!$("#carlos-topics")) return;
  const rows = await j(`/api/candidate/topics?name=${encodeURIComponent(CARLOS)}&days=${days()}`);
  carlosTopicRows = rows;
  const visible = rows.slice(0, CARLOS_TOPICS_VISIBLE);
  const rest = rows.slice(CARLOS_TOPICS_VISIBLE);
  $("#carlos-topics").innerHTML = visible.map((t, i) => carlosTopicCard(t, i)).join("")
    + (rest.length ? `<button class="toggle" id="ct-more">▸ ver ${rest.length} tema${rest.length === 1 ? "" : "s"} más</button><div id="ct-rest" style="display:none">${rest.map((t, i) => carlosTopicCard(t, i + visible.length)).join("")}</div>` : "")
    || `<div class="empty">Aún no hay suficientes menciones de Carlos con tema identificado en el período.</div>`;
  $("#ct-more")?.addEventListener("click", (e) => { $("#ct-rest").style.display = "block"; e.target.remove(); });
  $("#carlos-topics").querySelectorAll("[data-ct-idx]").forEach((btn) => btn.addEventListener("click", () => {
    const i = Number(btn.dataset.ctIdx);
    const t = carlosTopicRows[i];
    if (btn.nextElementSibling?.classList.contains("thread")) { btn.nextElementSibling.remove(); btn.textContent = btn.textContent.replace("▾", "▸"); return; }
    const div = document.createElement("div"); div.className = "thread";
    div.innerHTML = t.samples.map(quote).join("");
    btn.after(div);
    btn.textContent = btn.textContent.replace("▸", "▾");
  }));
  const top = rows[0];
  $("#read-carlos-topics").innerHTML = top
    ? `El tema del que más se habla sobre Carlos es <b>${esc(top.topic)}</b> (${top.count} menciones, ${top.positive_pct}% a favor).` +
      (rows[1] ? ` Le siguen <b>${esc(rows[1].topic)}</b>${rows[2] ? ` y <b>${esc(rows[2].topic)}</b>` : ""}.` : "")
    : "Sin temas identificados todavía en el período.";
}

async function loadStatus() {
  const s = await j("/health");
  $("#last-run").textContent = `Actualizado ${ago(s.last_run)}`;
  $("#status").innerHTML = `${s.total_mentions} menciones capturadas · ${s.scored} clasificadas · ${s.pending} pendientes · ${s.discarded} descartadas (homónimos / ajenas)<br>` +
    s.sources.map((x) => `${esc(x.name)}: ${x.total}${x.error ? ` <span style="color:var(--neg)" title="${esc(x.error)}">⚠</span>` : ""}`).join(" · ");
}

async function loadAll() {
  const rows = await loadSummary();
  await Promise.all([loadTimeline(rows), loadSources(), loadTopics(), loadAlerts(), loadFeed(), loadStatus(), loadCity(), loadAgenda(), loadCarlosTopics(), (typeof loadCouncil === "function" ? loadCouncil() : null)]);
}

document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("active", p.id === `tab-${b.dataset.tab}`));
  Object.values(charts).forEach((c) => c.resize());  // los canvas ocultos no tienen tamaño hasta mostrarse
  window.scrollTo({ top: 0 });
}));
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

  chart("#chart-city-topics", {
    type: "bar",
    data: { labels: topics.map((t) => cap(t.category)), datasets: [{ data: topics.map((t) => t.count), backgroundColor: CAT_COLOR, borderRadius: 6, barThickness: 20 }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, datalabels: { display: true, anchor: "end", align: "end", color: INK, font: { weight: 600 },
        formatter: (v, c) => { const t = topics[c.dataIndex]; const tr = t.trend_pct; return tr === null ? `${v}` : `${v}  ${tr > 5 ? "▲" : tr < -5 ? "▼" : "="} ${Math.abs(tr)}%`; } } },
      scales: { x: { beginAtZero: true, grid: { color: GRID }, ticks: { precision: 0 }, grace: "25%", title: { display: true, text: "menciones" } }, y: { grid: { display: false } } } },
  });
  const rising = topics.filter((t) => t.trend_pct !== null).sort((a, b) => b.trend_pct - a.trend_pct)[0];
  $("#read-city-topics").innerHTML = topics.length
    ? `En ${periodLabel()}, Cali habló sobre todo de <b>${topics[0].category}</b> (${topics[0].count} menciones)` + (topics[1] ? `, luego de <b>${topics[1].category}</b> (${topics[1].count})` : "") + (topics[2] ? ` y <b>${topics[2].category}</b> (${topics[2].count})` : "") + ". " +
      (rising && rising.trend_pct > 5 ? `El tema que más crece es <b>${rising.category}</b> (▲ ${rising.trend_pct}% frente al período anterior).` : "Ningún tema muestra un crecimiento marcado frente al período anterior.")
    : "Aún no hay menciones de ciudad clasificadas en el período.";

  const scored = topics.filter((t) => t.count > 0);
  chart("#chart-city-perception", {
    type: "bar",
    data: { labels: scored.map((t) => `${cap(t.category)} (${t.count})`), datasets: [
      { label: "Molestia", data: scored.map((t) => pct(t.negative, t.count)), backgroundColor: CRITICAL },
      { label: "Informativa", data: scored.map((t) => pct(t.neutral, t.count)), backgroundColor: NEUTRAL_TONE },
      { label: "A favor", data: scored.map((t) => pct(t.positive, t.count)), backgroundColor: GOOD }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw}%` } },
        datalabels: { display: (c) => c.dataset.data[c.dataIndex] >= 8, color: (c) => c.datasetIndex === 1 ? INK_SOFT : "#fff", font: { weight: 600, size: 12 }, formatter: (v) => v + "%" } },
      scales: { x: { stacked: true, max: 100, ticks: { callback: (v) => v + "%" }, grid: { color: GRID } }, y: { stacked: true, grid: { display: false } } } },
  });
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
    ? `La prioridad es <b>${top.category}</b>: ${top.count} menciones con ${top.negative_pct}% de molestia y ${top.carlos_mentions === 0 ? "ninguna" : top.carlos_mentions} mención${top.carlos_mentions === 1 ? "" : "es"} de Carlos. ` +
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
  chart("#chart-perception", {
    type: "bar",
    data: { labels: withComments.map((r) => `${r.name} (${r.comments})`), datasets: [
      { label: "A favor", data: withComments.map((r) => r.positive_pct), backgroundColor: GOOD },
      { label: "Neutral", data: withComments.map((r) => pct(r.neutral, r.comments)), backgroundColor: NEUTRAL_TONE },
      { label: "En contra", data: withComments.map((r) => r.negative_pct), backgroundColor: CRITICAL }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw}%` } },
        datalabels: { display: (c) => c.dataset.data[c.dataIndex] >= 8, color: (c) => c.datasetIndex === 1 ? INK_SOFT : "#fff", font: { weight: 600, size: 12 }, formatter: (v) => v + "%" } },
      scales: { x: { stacked: true, max: 100, ticks: { callback: (v) => v + "%" }, grid: { color: GRID }, title: { display: true, text: "de cada 100 comentarios ciudadanos" } }, y: { stacked: true, grid: { display: false } } } },
  });
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
