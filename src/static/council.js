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

  hbar("#chart-council", withM.map((m) => m.name), withM.map((m) => m.mentions), withM.map((m) => m.name === CARLOS ? BLUE : CARLOS_GRAY));
  const councilTip = { custom: ({ dataPointIndex }) => {
    const m = withM[dataPointIndex];
    return `<div style="padding:6px 10px"><b>${esc(m.name)}</b><div class="hint">${esc(m.party || "sin partido")}${m.is_candidate ? " · también candidato a la Alcaldía" : ""}</div></div>`;
  } };
  if (charts["#chart-council"]) charts["#chart-council"].updateOptions({ tooltip: councilTip }, false, false);
  else if (pendingCharts["#chart-council"]) pendingCharts["#chart-council"].tooltip = { ...pendingCharts["#chart-council"].tooltip, ...councilTip };
  $("#read-council").innerHTML = withM.length
    ? `De los ${o.members.length} concejales, ${withM.length} tuvieron menciones en ${periodLabel()}. El más mencionado es <b>${esc(withM[0].name)}</b> (${withM[0].mentions}, ${esc(withM[0].party || "sin partido")})` +
      (!carlos ? `; <b>Carlos Arias</b> no registra menciones en el período.`
        : carlosIdx === 0 ? `.` // ya se dijo arriba que Carlos es el más mencionado; repetirlo suena redundante
        : `; <b>Carlos Arias</b> ocupa el ${ordinal(carlosIdx)} lugar con ${carlos.mentions}.`)
    : "Ningún concejal registra menciones en el período.";

  const parties = o.parties.filter((p) => p.mentions > 0);
  chart("#chart-council-parties", {
    chart: { type: "bar", stacked: true, height: "100%" },
    series: [
      { name: "Positivas", data: parties.map((p) => p.positive) },
      { name: "Neutrales", data: parties.map((p) => p.neutral) },
      { name: "Negativas", data: parties.map((p) => p.negative) }],
    xaxis: { categories: parties.map((p) => `${p.party} (${p.members})`) },
    colors: [GOOD, NEUTRAL_TONE, CRITICAL],
    plotOptions: { bar: { horizontal: true, borderRadius: 3, barHeight: "65%" } },
    dataLabels: { enabled: true, formatter: (v) => (v >= 2 ? v : ""), style: { colors: ["#fff"], fontWeight: 600, fontSize: "11px" } },
    legend: { position: "bottom" },
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
