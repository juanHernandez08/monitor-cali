const $ = (s) => document.querySelector(s);
const CARLOS = "Carlos Arias";
const COLORS = ["#1f4fa3", "#d9483b", "#22a06b", "#e0a020", "#8b5cf6", "#0ea5a4", "#f97316", "#64748b", "#be185d"];
const SRC = { google_news: "Prensa", rss: "Prensa", reddit: "Reddit", youtube: "YouTube", social: "Instagram / Facebook", google_cse: "Redes", serp: "Redes" };
const LABEL = { negative: "Negativo", positive: "Positivo", neutral: "Neutral" };
const KIND = { post: "Post", video: "Video", comments: "Publicación", news: "Nota" };
const charts = {};
let feedRows = [];

Chart.defaults.font.family = "Inter, system-ui, sans-serif";
Chart.defaults.color = "#66718a";

async function j(url) { const r = await fetch(url); return r.json(); }
function days() { return Number($("#days").value); }
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

/* ---------- KPIs + panel de Carlos + tarjetas ---------- */
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

  const scored = rows.filter((r) => r.positive + r.negative + r.neutral > 0);
  chart("#chart-sentiment", {
    type: "bar",
    data: { labels: scored.map((r) => `${r.name} (${r.positive + r.negative + r.neutral})`), datasets: [
      { label: "Positivo", data: scored.map((r) => pct(r.positive, r.positive + r.negative + r.neutral)), backgroundColor: "#22a06b" },
      { label: "Neutral", data: scored.map((r) => pct(r.neutral, r.positive + r.negative + r.neutral)), backgroundColor: "#c3cad6" },
      { label: "Negativo", data: scored.map((r) => pct(r.negative, r.positive + r.negative + r.neutral)), backgroundColor: "#d9483b" }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw}%` } } },
      scales: { x: { stacked: true, max: 100, ticks: { callback: (v) => v + "%" }, grid: { color: "#eef1f5" } }, y: { stacked: true, grid: { display: false } } } },
  });
  return rows;
}

async function loadTimeline(rows) {
  const d = await j(`/api/timeline?days=${Math.max(days(), 7)}`);
  const top = [CARLOS, ...rows.filter((r) => r.name !== CARLOS).sort((a, b) => b.mentions - a.mentions).slice(0, 4).map((r) => r.name)];
  const series = d.series.filter((s) => top.includes(s.name));
  chart("#chart-timeline", {
    type: "line",
    data: { labels: d.labels.map((l) => l.slice(5).replace("-", "/")), datasets: series.map((s, i) => ({
      label: s.name, data: s.data, borderColor: COLORS[i % COLORS.length], backgroundColor: COLORS[i % COLORS.length],
      tension: .35, borderWidth: s.name === CARLOS ? 3 : 1.5, pointRadius: s.name === CARLOS ? 3 : 0, pointHoverRadius: 4 })) },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom" } },
      scales: { y: { beginAtZero: true, grid: { color: "#eef1f5" } }, x: { ticks: { maxTicksLimit: 8, maxRotation: 0 }, grid: { display: false } } } },
  });
}

async function loadTopics() {
  const t = await j(`/api/topics?days=${days()}`);
  chart("#chart-topics", {
    type: "bar",
    data: { labels: t.map((x) => x.topic), datasets: [{ data: t.map((x) => x.count), backgroundColor: "#1f4fa3", borderRadius: 4, barThickness: 14 }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, grid: { color: "#eef1f5" }, ticks: { precision: 0 } }, y: { grid: { display: false } } } },
  });
}

async function loadAlerts() {
  const a = await j(`/api/alerts?days=${days()}`);
  $("#alerts").innerHTML = a.length ? a.map((m) => `<li>
    <span class="tag negative">${m.score}</span> ${esc(m.text).slice(0, 200)}
    <div class="meta">${SRC[m.source_type] || esc(m.source)} · ${esc(m.author || "")} · ${ago(m.published_at)}${m.url ? ` · <a href="${m.url}" target="_blank" rel="noopener">ver</a>` : ""}</div>
  </li>`).join("") : `<li class="empty">Sin menciones negativas fuertes sobre Carlos Arias en el período.</li>`;
}

/* ---------- feed ---------- */
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
      <div class="meta"><span class="cand">${esc(r.candidate)}</span><span class="tag src">${SRC[r.source_type] || esc(r.source)} · ${KIND[r.kind] || ""}</span><span>${fmtDate(r.published_at)}</span>${r.url ? `<a href="${r.url}" target="_blank" rel="noopener">ver original ↗</a>` : ""}</div>
      <div class="text">${esc(r.text)}</div>
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
      <div>${esc(c.text)}<div class="who">${esc(c.author || "")} · ${fmtDate(c.published_at)}${c.url ? ` · <a href="${c.url}" target="_blank" rel="noopener">ver</a>` : ""}</div></div>
      <div>${sentTag(c)}</div></div>`).join("") || `<div class="empty">Sin comentarios que cumplan el filtro.</div>`;
  item.appendChild(div);
  btn.textContent = btn.textContent.replace("▸", "▾");
}

async function loadStatus() {
  const s = await j("/health");
  $("#last-run").textContent = `Actualizado ${ago(s.last_run)}`;
  $("#status").innerHTML = `${s.total_mentions} menciones capturadas · ${s.scored} clasificadas · ${s.pending} pendientes · ${s.discarded} descartadas (homónimos / ajenas)<br>` +
    s.sources.map((x) => `${esc(x.name)}: ${x.total}${x.error ? ` <span style="color:var(--neg)" title="${esc(x.error)}">⚠</span>` : ""}`).join(" · ");
}

async function loadAll() {
  const rows = await loadSummary();
  await Promise.all([loadTimeline(rows), loadTopics(), loadAlerts(), loadFeed(), loadStatus()]);
}

$("#days").addEventListener("change", loadAll);
["#f-candidate", "#f-source", "#f-label"].forEach((id) => $(id).addEventListener("change", loadFeed));
$("#refresh").addEventListener("click", async () => {
  const b = $("#refresh"); b.disabled = true; b.textContent = "Actualizando…";
  await fetch("/api/refresh", { method: "POST" });
  setTimeout(async () => { await loadAll(); b.disabled = false; b.textContent = "Actualizar ahora"; }, 25000);
});
loadAll();
setInterval(loadAll, 120000);
