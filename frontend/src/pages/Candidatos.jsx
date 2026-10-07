import { useState } from "react";
import { BarChart2, Crown, Gauge as GaugeIcon, HeartPulse, Landmark, Percent, Smile, Sparkles, Star, Users, UsersRound, Vote, MessagesSquare } from "lucide-react";
import { periodLabel, useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { CARLOS, esc, ordinal, pct, scored, share } from "../lib/format";
import { BLUE, CARLOS_GRAY, INK, VIOLET } from "../lib/palette";
import { Avatar, Empty, Kpi, KpiGrid, Panel, PanelSkeleton, Reading, Reveal, Segmented, Skeleton, Tag } from "../components/ui";
import { Chart, HBar, HBar100, SENT_COLORS } from "../charts/Chart";
import { EmotionHeatmap, SamplesDetail } from "../charts/Heatmap";
import { Quotes } from "../components/Feed";
import { RivalCard } from "./Resumen";

/* Positividad con su intervalo de confianza del 95% (Wilson): con 5 menciones, "80% positivas"
   puede ser cualquier cosa entre 38% y 96%; con 300, casi no se mueve. Barras = rango plausible. */
function PositivityCI({ rows }) {
  const list = rows.filter((r) => r.positive_ci).map((r) => ({ ...r, n: scored(r) })).sort((a, b) => share(b, "positive") - share(a, "positive"));
  const c = list.find((r) => r.name === CARLOS);
  const overlap = c ? list.filter((r) => r !== c && r.positive_ci[0] <= c.positive_ci[1] && c.positive_ci[0] <= r.positive_ci[1]).map((r) => r.name) : [];
  const options = {
    chart: { type: "rangeBar" },
    plotOptions: { bar: { horizontal: true, barHeight: "46%", borderRadius: 4 } },
    series: [{ name: "Intervalo 95%", data: list.map((r) => ({ x: `${r.name} (n=${r.n})`, y: r.positive_ci, fillColor: r.name === CARLOS ? BLUE : CARLOS_GRAY })) }],
    xaxis: { min: 0, max: 100, labels: { formatter: (v) => Math.round(v) + "%" } },
    dataLabels: { enabled: true, formatter: (_v, { dataPointIndex }) => `${share(list[dataPointIndex], "positive")}%`, style: { colors: [INK], fontWeight: 600 } },
    tooltip: { custom: ({ dataPointIndex }) => {
      const r = list[dataPointIndex];
      return `<div style="padding:8px 12px"><b>${esc(r.name)}</b><br>${share(r, "positive")}% positivas de ${r.n}<br>rango plausible: ${r.positive_ci[0]}% a ${r.positive_ci[1]}%</div>`;
    } },
    legend: { show: false },
  };
  return (
    <Panel icon={GaugeIcon} tone="violet" title="¿Qué tan seguro es ese porcentaje de positividad?"
      hint="Rango plausible (intervalo de confianza del 95%) del % de menciones positivas de cada candidato. Con pocas menciones el rango es ancho; si dos rangos se cruzan, los datos no permiten decir que uno está mejor que el otro. Entre paréntesis, menciones clasificadas.">
      <Reading>
        {c ? <><b>Carlos Arias</b>: {share(c, "positive")}% positivas sobre {c.n} menciones clasificadas; el valor real está, con 95% de confianza, entre <b>{c.positive_ci[0]}% y {c.positive_ci[1]}%</b>.{" "}
          {overlap.length ? `Sus rangos se cruzan con los de ${overlap.join(", ")}: con estos datos no se puede afirmar que uno tenga mejor imagen que el otro.` : "Su rango no se cruza con el de ningún rival: la diferencia es estadísticamente clara."}</>
          : "Sin menciones clasificadas de Carlos en el período."}
      </Reading>
      <Chart options={options} height={Math.max(300, 40 + list.length * 32)} label="Intervalo de confianza de positividad" />
    </Panel>
  );
}

function ListaCandidatos() {
  const { days, openProfile } = useApp();
  const summary = useApi(`/api/summary?days=${days}`);
  const topicsCom = useApi(`/api/topics?days=${days}&kind=comments`);
  const emo = useApi(`/api/candidate/emotions?days=${days}&kind=candidate`);
  const [cell, setCell] = useState(null);
  const rows = summary.data;
  if (!rows) return <div className="grid gap-5"><Skeleton className="h-28" /><PanelSkeleton h="h-80" /></div>;

  const byVol = [...rows].sort((a, b) => b.mentions - a.mentions);
  const sc = rows.filter((r) => scored(r) > 0);
  const byPos = [...sc].sort((a, b) => share(b, "positive") - share(a, "positive"));
  const totalMentions = rows.reduce((a, r) => a + r.mentions, 0);
  const totalPos = sc.reduce((a, r) => a + r.positive, 0);
  const totalScored = sc.reduce((a, r) => a + scored(r), 0);
  const heat = (emo.data || []).slice(0, 21).map((r) => ({ name: r.candidate, emotions: r.emotions }));

  return (
    <div className="grid gap-5">
      <KpiGrid>
        <Kpi icon={Users} label="Candidatos monitoreados" value={rows.length} foot={`${totalMentions} menciones · ${periodLabel(days)}`} />
        <Kpi delay={60} icon={Crown} iconTone="amber" small label="Más mencionado" value={byVol[0]?.name || "—"} foot={byVol[0] ? `${byVol[0].mentions} menciones` : ""} />
        <Kpi delay={120} icon={Star} iconTone="green" small tone="pos" label="Mejor imagen" value={byPos[0]?.name || "—"} foot={byPos[0] ? `${share(byPos[0], "positive")}% positivas` : ""} />
        <Kpi delay={180} icon={Percent} label="Positividad promedio" value={totalScored ? `${pct(totalPos, totalScored)}%` : "—"} foot={`sobre ${totalScored} menciones clasificadas`} />
      </KpiGrid>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel icon={BarChart2} title="¿Quién habla más?" hint="menciones en el período. Toca una barra para ver el perfil.">
          <HBar categories={byVol.map((r) => r.name)} data={byVol.map((r) => r.mentions)} colors={byVol.map((r) => (r.name === CARLOS ? BLUE : CARLOS_GRAY))}
            onClick={(i) => openProfile(byVol[i].candidate_id)} label="¿Quién habla más?" />
        </Panel>
        <Panel icon={HeartPulse} tone="green" title="¿Cómo les está yendo?" hint="positivo / neutral / negativo">
          <HBar100 categories={sc.map((r) => r.name)} colors={SENT_COLORS} label="Cómo les está yendo"
            series={[{ name: "Positivas", data: sc.map((r) => share(r, "positive")) }, { name: "Neutrales", data: sc.map((r) => share(r, "neutral")) }, { name: "Negativas", data: sc.map((r) => share(r, "negative")) }]} />
        </Panel>
      </div>

      <PositivityCI rows={rows} />

      <Panel icon={Smile} tone="amber" title="¿Qué emoción transmite la cobertura de cada candidato?"
        hint="Más allá de positivo/negativo: qué siente concretamente quien escribe sobre cada candidato — miedo, ira, felicidad, sorpresa y demás. Más oscuro = más menciones con esa emoción. Toca una celda para ver qué está generando concretamente esa emoción (el apalancador).">
        {!emo.data ? <Skeleton className="h-72" /> : heat.length ? <EmotionHeatmap rows={heat} label="Emoción por candidato" onCell={(r, e) => setCell({ name: r.name, emo: e })} /> : <Empty>Sin emociones clasificadas en el período.</Empty>}
        <SamplesDetail title={cell ? `${cell.name} · ${cell.emo[0].toUpperCase() + cell.emo.slice(1)}` : ""}
          url={cell ? `/api/candidate/emotion-samples?name=${encodeURIComponent(cell.name)}&emotion=${encodeURIComponent(cell.emo)}&days=${days}` : null} />
      </Panel>

      <Panel icon={MessagesSquare} tone="violet" title="Qué piden o reclaman los ciudadanos" hint="asuntos más mencionados en los comentarios a los candidatos">
        {!topicsCom.data ? <Skeleton className="h-64" /> : <HBar categories={topicsCom.data.map((x) => x.topic)} data={topicsCom.data.map((x) => x.count)} colors={VIOLET} label="Qué piden los ciudadanos" />}
      </Panel>

      <Panel icon={Vote} title="Los 9 candidatos" hint="toca a cualquiera para ver todo lo recopilado de esa persona: temas, publicaciones y comentarios">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((r, i) => <Reveal key={r.candidate_id} delay={i * 30}><RivalCard big r={r} onOpen={() => openProfile(r.candidate_id)} /></Reveal>)}
        </div>
      </Panel>
    </div>
  );
}

function Concejales() {
  const { days } = useApp();
  const council = useApi(`/api/council?days=${days}`);
  const emo = useApi(`/api/candidate/emotions?days=${days}&kind=councilor`);
  const [cell, setCell] = useState(null);
  const o = council.data;
  if (!o) return <div className="grid gap-5"><Skeleton className="h-28" /><PanelSkeleton h="h-80" /></div>;

  const withM = o.members.filter((m) => m.mentions > 0);
  const total = o.members.reduce((a, m) => a + m.mentions, 0);
  const carlosIdx = withM.findIndex((m) => m.name === CARLOS);
  const carlos = carlosIdx >= 0 ? withM[carlosIdx] : null;
  const topParty = o.parties.find((p) => p.mentions > 0);
  const parties = o.parties.filter((p) => p.mentions > 0);
  const heat = (emo.data || []).slice(0, 21).map((r) => ({ name: r.candidate, emotions: r.emotions }));

  const tipOptions = {
    custom: ({ dataPointIndex }) => {
      const m = withM[dataPointIndex];
      return `<div style="padding:8px 12px"><b>${esc(m.name)}</b><div style="color:#64748b;font-size:12px">${esc(m.party || "sin partido")}${m.is_candidate ? " · también candidato a la Alcaldía" : ""}</div></div>`;
    },
  };
  const councilOptions = {
    chart: { type: "bar" },
    series: [{ data: withM.map((m) => m.mentions) }],
    xaxis: { categories: withM.map((m) => m.name) },
    plotOptions: { bar: { horizontal: true, borderRadius: 5, borderRadiusApplication: "end", distributed: true, barHeight: "62%" } },
    colors: withM.map((m) => (m.name === CARLOS ? BLUE : CARLOS_GRAY)),
    dataLabels: { enabled: true, style: { colors: [INK], fontWeight: 600 }, offsetX: 6 },
    legend: { show: false }, tooltip: tipOptions,
  };
  const partyOptions = {
    chart: { type: "bar", stacked: true },
    series: [{ name: "Positivas", data: parties.map((p) => p.positive) }, { name: "Neutrales", data: parties.map((p) => p.neutral) }, { name: "Negativas", data: parties.map((p) => p.negative) }],
    xaxis: { categories: parties.map((p) => `${p.party} (${p.members})`) },
    colors: SENT_COLORS,
    plotOptions: { bar: { horizontal: true, borderRadius: 3, barHeight: "65%" } },
    dataLabels: { enabled: true, formatter: (v) => (v >= 2 ? v : ""), style: { colors: ["#fff"], fontWeight: 600, fontSize: "11px" } },
    legend: { position: "bottom" },
  };

  return (
    <div className="grid gap-5">
      <p className="px-1 text-[13px] leading-relaxed text-slate-500">Qué se dice de cada concejal y cómo le responde la gente, agrupado también por partido. Carlos Arias y Roberto Ortiz aparecen aquí y en la lista de candidatos, porque son ambas cosas. La cobertura de los concejales viene de prensa; sus redes se agregan cuando se configuren sus cuentas.</p>
      <KpiGrid>
        <Kpi icon={Landmark} label="Concejales monitoreados" value={o.members.length} foot={`${withM.length} con menciones en ${periodLabel(days)}`} />
        <Kpi delay={60} icon={MessagesSquare} label="Menciones del Concejo" value={total} foot={`prensa y redes · ${periodLabel(days)}`} />
        <Kpi delay={120} icon={UsersRound} label="Carlos Arias entre sus colegas" value={carlos ? carlos.mentions : 0} foot={carlos ? `${ordinal(carlosIdx)} de ${withM.length} concejales con menciones` : "sin menciones en el período"} />
        <Kpi delay={180} icon={Sparkles} iconTone="amber" small label="Bancada más visible" value={topParty ? topParty.party : "—"} foot={topParty ? `${topParty.mentions} menciones · ${topParty.members} concejales` : ""} />
      </KpiGrid>

      <Panel icon={BarChart2} title="¿De qué concejales se habla?" hint="Menciones en el período. Carlos Arias en azul.">
        <Reading>
          {withM.length ? <>De los {o.members.length} concejales, {withM.length} tuvieron menciones en {periodLabel(days)}. El más mencionado es <b>{withM[0].name}</b> ({withM[0].mentions}, {withM[0].party || "sin partido"})
            {!carlos ? <>; <b>Carlos Arias</b> no registra menciones en el período.</> : carlosIdx === 0 ? "." : <>; <b>Carlos Arias</b> ocupa el {ordinal(carlosIdx)} lugar con {carlos.mentions}.</>}</>
            : "Ningún concejal registra menciones en el período."}
        </Reading>
        <Chart options={councilOptions} height={Math.max(320, 40 + withM.length * 32)} label="Menciones por concejal" />
      </Panel>

      <Panel icon={Landmark} tone="violet" title="Por partido" hint="Suma de menciones de los concejales de cada bancada y cómo se reparte su sentimiento.">
        <Chart options={partyOptions} height={Math.max(320, 40 + parties.length * 40)} label="Sentimiento por partido" />
      </Panel>

      <Panel icon={Smile} tone="amber" title="¿Qué emoción transmite la cobertura de cada concejal?"
        hint="Más allá de positivo/negativo: qué siente concretamente quien escribe sobre cada concejal. Toca una celda para ver el apalancador — qué está generando concretamente esa emoción.">
        {!emo.data ? <Skeleton className="h-72" /> : heat.length ? <EmotionHeatmap rows={heat} label="Emoción por concejal" onCell={(r, e) => setCell({ name: r.name, emo: e })} /> : <Empty>Sin emociones clasificadas en el período.</Empty>}
        <SamplesDetail title={cell ? `${cell.name} · ${cell.emo[0].toUpperCase() + cell.emo.slice(1)}` : ""}
          url={cell ? `/api/candidate/emotion-samples?name=${encodeURIComponent(cell.name)}&emotion=${encodeURIComponent(cell.emo)}&days=${days}` : null} />
      </Panel>

      <Panel icon={Users} title="Detalle por concejal" hint="Temas en los que aparece y menciones más marcadas, con enlace.">
        <div className="grid gap-3">
          {o.members.map((m) => (
            <div key={m.name} className="flex gap-3.5 rounded-2xl border border-slate-200/80 bg-white p-4">
              <Avatar name={m.name} src={m.avatar} size="sm" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                  <b className="text-slate-900">{m.name}</b>
                  <span className="text-xs text-slate-500">{m.party || "sin partido"}{m.is_candidate ? " · candidato a la Alcaldía" : ""} · {m.mentions} menciones{m.comments ? ` · ${m.comments} comentarios (${m.comments_positive_pct}% a favor)` : ""}</span>
                </div>
                {m.mentions ? (
                  <div className="my-2 flex flex-wrap gap-1.5">
                    {m.categories.map((c) => <Tag key={c.category}>{c.category} · {c.count}</Tag>)}
                    {m.topics.map((t) => <Tag key={t.topic} tone="brand">{t.topic} · {t.count}</Tag>)}
                  </div>
                ) : <div className="mt-1 text-xs text-slate-500">Sin menciones en el período.</div>}
                <Quotes rows={m.samples} />
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

export default function Candidatos() {
  const [sub, setSub] = useState("lista");
  return (
    <div className="grid gap-5">
      <Segmented value={sub} onChange={setSub} label="Candidatos o concejales" options={[["lista", "Candidatos", Vote], ["concejales", "Concejales", Landmark]]} className="justify-self-start" />
      {sub === "lista" ? <ListaCandidatos /> : <Concejales />}
    </div>
  );
}
