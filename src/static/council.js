/* ---------- Concejo de Cali ---------- */
async function loadCouncil() {
  if (!$("#council-kpis")) return;
  const o = await j(`/api/council?days=${days()}`);
  const withM = o.members.filter((m) => m.mentions > 0);
  const total = o.members.reduce((a, m) => a + m.mentions, 0);
  const carlosIdx = withM.findIndex((m) => m.name === CARLOS);
  const carlos = carlosIdx >= 0 ? withM[carlosIdx] : null;
  const topParty = o.parties.find((p) => p.mentions > 0);

  $("#council-kpis").innerHTML = `
    <div class="kpi"><div class="label">Concejales monitoreados</div><div class="value">${o.members.length}</div><div class="foot">${withM.length} con menciones en ${periodLabel()}</div></div>
    <div class="kpi"><div class="label">Menciones del Concejo</div><div class="value">${total}</div><div class="foot">prensa y redes · ${periodLabel()}</div></div>
    <div class="kpi"><div class="label">Carlos Arias entre sus colegas</div><div class="value">${carlos ? carlos.mentions : 0}</div><div class="foot">${carlos ? `${ordinal(carlosIdx)} de ${withM.length} concejales con menciones` : "sin menciones en el período"}</div></div>
    <div class="kpi"><div class="label">Bancada más visible</div><div class="value" style="font-size:18px">${topParty ? esc(topParty.party) : "—"}</div><div class="foot">${topParty ? `${topParty.mentions} menciones · ${topParty.members} concejales` : ""}</div></div>`;

  chart("#chart-council", {
    type: "bar",
    data: { labels: withM.map((m) => m.name), datasets: [{ data: withM.map((m) => m.mentions),
      backgroundColor: withM.map((m) => m.name === CARLOS ? "#1f4fa3" : "#b8c4d9"), borderRadius: 5, barThickness: 16 }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false },
        datalabels: { display: true, anchor: "end", align: "end", color: "#172033", font: { weight: 600 } },
        tooltip: { callbacks: { afterBody: (it) => { const m = withM[it[0].dataIndex]; return [`${m.party || "sin partido"}${m.is_candidate ? " · también candidato a la Alcaldía" : ""}`]; } } } },
      scales: { x: { beginAtZero: true, grid: { color: "#eef1f5" }, ticks: { precision: 0 }, grace: "15%", title: { display: true, text: "menciones" } }, y: { grid: { display: false } } } },
  });
  $("#read-council").innerHTML = withM.length
    ? `De los ${o.members.length} concejales, ${withM.length} tuvieron menciones en ${periodLabel()}. El más mencionado es <b>${esc(withM[0].name)}</b> (${withM[0].mentions}, ${esc(withM[0].party || "sin partido")})` +
      (carlos ? `; <b>Carlos Arias</b> ocupa el ${ordinal(carlosIdx)} lugar con ${carlos.mentions}.` : "; <b>Carlos Arias</b> no registra menciones en el período.")
    : "Ningún concejal registra menciones en el período.";

  const parties = o.parties.filter((p) => p.mentions > 0);
  chart("#chart-council-parties", {
    type: "bar",
    data: { labels: parties.map((p) => `${p.party} (${p.members})`), datasets: [
      { label: "Positivas", data: parties.map((p) => p.positive), backgroundColor: "#22a06b" },
      { label: "Neutrales", data: parties.map((p) => p.neutral), backgroundColor: "#c3cad6" },
      { label: "Negativas", data: parties.map((p) => p.negative), backgroundColor: "#d9483b" }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" },
        datalabels: { display: (c) => c.dataset.data[c.dataIndex] >= 2, color: (c) => c.datasetIndex === 1 ? "#334155" : "#fff", font: { weight: 600, size: 11 } } },
      scales: { x: { stacked: true, beginAtZero: true, grid: { color: "#eef1f5" }, ticks: { precision: 0 }, title: { display: true, text: "menciones" } }, y: { stacked: true, grid: { display: false } } } },
  });

  $("#council-detail").innerHTML = o.members.map((m) => `<div class="pcard">
      ${avatar(m, "sm")}
      <div>
        <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap"><b>${esc(m.name)}</b>
          <span class="hint">${esc(m.party || "sin partido")}${m.is_candidate ? " · candidato a la Alcaldía" : ""} · ${m.mentions} menciones${m.comments ? ` · ${m.comments} comentarios (${m.comments_positive_pct}% a favor)` : ""}</span></div>
        ${m.mentions
          ? `<div class="subs">${m.categories.map((c) => `<span class="tag">${esc(c.category)} · ${c.count}</span>`).join("")}${m.topics.map((t) => `<span class="tag">${esc(t.topic)} · ${t.count}</span>`).join("")}</div>`
          : `<div class="hint">Sin menciones en el período.</div>`}
        ${m.samples.map(quote).join("")}
      </div></div>`).join("");
}
