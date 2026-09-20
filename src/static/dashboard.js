const $ = (s) => document.querySelector(s);
const COLORS = ["#1f5fbf", "#d64545", "#2e9e6b", "#e0a020", "#8b5cf6", "#0ea5a4", "#f97316", "#64748b", "#be185d"];
const SRC = { google_news: "Prensa", rss: "Prensa", reddit: "Reddit", youtube: "YouTube", google_cse: "IG/FB/X", serp: "IG/FB/X", social: "IG/FB" };
const LABEL = { negative: "Negativo", positive: "Positivo", neutral: "Neutral" };
const charts = {};

async function j(url) { const r = await fetch(url); return r.json(); }
function days() { return Number($("#days").value); }
function ago(iso) {
  if (!iso) return "sin datos";
  const m = Math.round((Date.now() - new Date(iso + "Z")) / 60000);
  if (m < 1) return "hace un momento";
  return m < 60 ? `hace ${m} min` : `hace ${Math.round(m / 60)} h`;
}
function esc(s) { return (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function chart(id, cfg) { if (charts[id]) charts[id].destroy(); charts[id] = new Chart($(id), cfg); }
function fmtDate(iso) { return new Date(iso + "Z").toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" }); }

async function loadCards() {
  const rows = await j(`/api/summary?days=${days()}`);
  $("#cards").innerHTML = rows.map((r) => {
    const t = r.positive + r.negative + r.neutral || 1;
    const d = r.previous ? Math.round((r.mentions - r.previous) / r.previous * 100) : null;
    const delta = d === null ? "sin período anterior" : `${d >= 0 ? "▲" : "▼"} ${Math.abs(d)}% vs período anterior`;
    return `<div class="card ${r.name === "Carlos Arias" ? "carlos" : ""}">
      <div class="name">${esc(r.name)}</div><div class="party">${esc(r.party || "")}</div>
      <div class="n">${r.mentions}</div>
      <div class="delta">${delta}${r.pending ? ` · ${r.pending} pendientes` : ""}</div>
      <div class="bar"><i class="p" style="width:${r.positive / t * 100}%"></i><i class="u" style="width:${r.neutral / t * 100}%"></i><i class="g" style="width:${r.negative / t * 100}%"></i></div>
    </div>`;
  }).join("");
  const sel = $("#f-candidate"); const cur = sel.value;
  sel.innerHTML = `<option value="">Todos los candidatos</option>` + rows.map((r) => `<option value="${r.candidate_id}">${esc(r.name)}</option>`).join("");
  sel.value = cur;
  chart("#chart-sentiment", {
    type: "bar",
    data: { labels: rows.map((r) => r.name), datasets: [
      { label: "Positivo", data: rows.map((r) => r.positive), backgroundColor: "#2e9e6b" },
      { label: "Neutral", data: rows.map((r) => r.neutral), backgroundColor: "#8b95a3" },
      { label: "Negativo", data: rows.map((r) => r.negative), backgroundColor: "#d64545" }] },
    options: { responsive: true, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } } },
  });
}

async function loadTimeline() {
  const d = await j(`/api/timeline?days=${Math.max(days(), 7)}`);
  chart("#chart-timeline", {
    type: "line",
    data: { labels: d.labels, datasets: d.series.map((s, i) => ({
      label: s.name, data: s.data, borderColor: COLORS[i % COLORS.length], backgroundColor: COLORS[i % COLORS.length],
      tension: .3, borderWidth: s.name === "Carlos Arias" ? 3 : 1.5, pointRadius: 2 })) },
    options: { responsive: true, scales: { y: { beginAtZero: true }, x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } } } },
  });
}

async function loadTopics() {
  const t = await j(`/api/topics?days=${days()}`);
  chart("#chart-topics", {
    type: "bar",
    data: { labels: t.map((x) => x.topic), datasets: [{ label: "menciones", data: t.map((x) => x.count), backgroundColor: "#1f5fbf" }] },
    options: { indexAxis: "y", responsive: true, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } },
  });
}

async function loadAlerts() {
  const a = await j(`/api/alerts?days=${days()}`);
  $("#alerts").innerHTML = a.length ? a.map((m) => `<li>
    <span class="tag negative">${m.score}</span> ${esc(m.text).slice(0, 220)}
    <div class="meta">${SRC[m.source_type] || esc(m.source)} · ${esc(m.author || "")} · ${ago(m.published_at)}${m.url ? ` · <a href="${m.url}" target="_blank" rel="noopener">ver</a>` : ""}</div>
  </li>`).join("") : "<li>Sin alertas en el período.</li>";
}

async function loadFeed() {
  const p = new URLSearchParams({ days: days(), limit: 150 });
  if ($("#f-candidate").value) p.set("candidate_id", $("#f-candidate").value);
  if ($("#f-source").value) p.set("source_type", $("#f-source").value);
  if ($("#f-label").value) p.set("label", $("#f-label").value);
  const rows = await j(`/api/mentions?${p}`);
  $("#feed tbody").innerHTML = rows.map((m) => `<tr>
    <td>${fmtDate(m.published_at)}</td>
    <td>${esc(m.candidate)}</td>
    <td><span class="tag">${SRC[m.source_type] || esc(m.source)}</span></td>
    <td class="text">${esc(m.text).slice(0, 260)}${m.author ? `<div class="meta">${esc(m.author)}</div>` : ""}</td>
    <td>${m.label ? `<span class="tag ${m.label}">${LABEL[m.label]} ${m.score}</span><div class="topic">${esc(m.topic || "")}</div>` : `<span class="tag pending">pendiente</span>`}</td>
    <td>${m.url ? `<a href="${m.url}" target="_blank" rel="noopener">ver</a>` : ""}</td>
  </tr>`).join("") || `<tr><td colspan="6">Sin menciones con esos filtros.</td></tr>`;
}

async function loadStatus() {
  const s = await j("/health");
  $("#last-run").textContent = `última actualización ${ago(s.last_run)}`;
  $("#status").innerHTML = `${s.total_mentions} menciones · ${s.scored} clasificadas · ${s.pending} pendientes de análisis · Google CSE hoy: ${s.cse_used_today}/100<br>` +
    s.sources.map((x) => `${esc(x.name)}: ${x.total}${x.error ? ` <span style="color:#d64545" title="${esc(x.error)}">⚠</span>` : ""}`).join(" · ");
}

async function loadAll() {
  await Promise.all([loadCards(), loadTimeline(), loadTopics(), loadAlerts(), loadFeed(), loadStatus()]);
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
