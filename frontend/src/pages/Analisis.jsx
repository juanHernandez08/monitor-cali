import { useState } from "react";
import { Activity, BarChart3, CalendarDays, Crosshair, Globe2, HandHeart, HeartPulse, ListChecks, Radar, Scale, X } from "lucide-react";
import { periodLabel, useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { CARLOS, SRC_LABEL, esc, ordinal, pct, scored, share } from "../lib/format";
import { BLUE, CARLOS_GRAY, COLORS, GRID, INK, MUTED, SRC_COLOR, VIOLET } from "../lib/palette";
import { CalloutFold, Empty, Panel, PanelSkeleton, Reading, SectionTitle, Skeleton, Button } from "../components/ui";
import { Chart, HBar, HBar100, SENT_COLORS } from "../charts/Chart";
import { FeedList, SourceChip } from "../components/Feed";
import { LinkOut } from "../components/ui";

/* ---------- ¿De quién se habla más? ---------- */
function Volume({ rows }) {
  const { days } = useApp();
  const total = rows.reduce((a, r) => a + r.mentions, 0);
  const byVol = [...rows].sort((a, b) => b.mentions - a.mentions);
  const carlos = rows.find((r) => r.name === CARLOS) || rows[0];
  const vRank = byVol.findIndex((r) => r.name === CARLOS);
  const tied = byVol.filter((r) => r.mentions === carlos.mentions && r.name !== CARLOS);
  const next = byVol.find((r) => r.mentions < carlos.mentions);
  return (
    <Panel icon={BarChart3} title="¿De quién se habla más?" hint="Número de menciones por candidato en el período. Incluye prensa, YouTube, Instagram y Facebook.">
      <Reading>
        En {periodLabel(days)} se registraron <b>{total} menciones</b> de los {rows.length} candidatos.{" "}
        {vRank === 0
          ? <><b>Carlos Arias</b> es de quien más se habla, con {carlos.mentions} menciones{tied.length ? ` (empatado con ${tied.map((r) => r.name).join(" y ")})` : ""}; le sigue {next?.name || ""}.</>
          : <><b>{byVol[0].name}</b> es de quien más se habla ({byVol[0].mentions}). <b>Carlos Arias</b> ocupa el {ordinal(vRank)} lugar con {carlos.mentions} menciones, {byVol[0].mentions - carlos.mentions} menos.</>}
      </Reading>
      <HBar categories={byVol.map((r) => r.name)} data={byVol.map((r) => r.mentions)} colors={byVol.map((r) => (r.name === CARLOS ? BLUE : CARLOS_GRAY))} label="¿De quién se habla más?" />
    </Panel>
  );
}

/* ---------- ¿Cuándo se habló de ellos? ---------- */
function PeakDetail({ peak, onClose }) {
  const { data: p, loading } = useApi(`/api/peak?candidate=${encodeURIComponent(peak.name)}&day=${peak.day}`);
  const nice = new Date(peak.day + "T12:00:00").toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" });
  return (
    <div className="mt-4 animate-fade-in border-t border-slate-100 pt-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div><h3 className="text-[15px] font-semibold text-slate-900">{peak.name} · {nice}</h3>
          {p?.text && <span className="text-xs text-slate-500">{p.mentions_that_day} {p.mentions_that_day === 1 ? "mención" : "menciones"} ese día, la mayoría de esta publicación</span>}</div>
        <Button variant="ghost" icon={X} onClick={onClose}>cerrar</Button>
      </div>
      {loading ? <Skeleton className="h-16" /> : !p?.text ? <div className="text-sm text-slate-500">Sin publicaciones de {peak.name} ese día.</div> : (
        <article className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-500"><SourceChip m={p} />{p.url && <LinkOut href={p.url} />}</div>
          <p className="text-sm leading-relaxed text-slate-800">{p.text}</p>
        </article>
      )}
    </div>
  );
}

function Timeline({ rows }) {
  const { days } = useApp();
  const { data: d } = useApi(`/api/timeline?days=${Math.max(days, 7)}`);
  const [peak, setPeak] = useState(undefined); // undefined = aún por decidir (pico de Carlos); null = cerrado
  if (!d) return <PanelSkeleton h="h-96" />;
  const top = [CARLOS, ...rows.filter((r) => r.name !== CARLOS).sort((a, b) => b.mentions - a.mentions).slice(0, 4).map((r) => r.name)];
  const series = d.series.filter((s) => top.includes(s.name));
  const cs = series.find((s) => s.name === CARLOS);
  let defaultPeak = null;
  if (cs) {
    const idx = cs.data.reduce((best, v, i) => (v > cs.data[best] ? i : best), 0);
    if (cs.data[idx] > 0) defaultPeak = { name: CARLOS, day: d.labels[idx] };
  }
  const shown = peak === undefined ? defaultPeak : peak;
  const options = {
    chart: { type: "line", events: { dataPointSelection: (_e, _c, cfg) => setPeak({ name: series[cfg.seriesIndex].name, day: d.labels[cfg.dataPointIndex] }) } },
    series: series.map((s) => ({ name: s.name, data: s.data })),
    xaxis: { categories: d.labels.map((l) => l.slice(5).replace("-", "/")), tickAmount: 10 },
    colors: series.map((_s, i) => COLORS[i % COLORS.length]),
    stroke: { curve: "smooth", width: series.map((s) => (s.name === CARLOS ? 3.5 : 1.5)) },
    markers: { size: series.map((s) => (s.name === CARLOS ? 4 : 3)), hover: { size: 7 } },
    legend: { position: "bottom" },
    yaxis: { labels: { formatter: (v) => Math.round(v) }, title: { text: "menciones ese día" } },
    tooltip: { shared: false, intersect: true, y: { formatter: (v) => `${v} ${v === 1 ? "mención" : "menciones"} · clic para ver la publicación` } },
  };
  return (
    <Panel icon={CalendarDays} tone="violet" title="¿Cuándo se habló de ellos?"
      hint="Menciones por día de Carlos Arias (línea gruesa) y de los 4 rivales con más menciones. Pasa el mouse por un punto para ver el valor; haz clic para ver la publicación que lo causó.">
      <Chart options={options} height={420} label="Menciones por día" clickable minWidth={560} />
      {shown && <PeakDetail peak={shown} onClose={() => setPeak(null)} />}
    </Panel>
  );
}

/* ---------- Canales ---------- */
function Sources() {
  const { days } = useApp();
  const { data: d } = useApi(`/api/sources?days=${days}`);
  if (!d) return <PanelSkeleton h="h-96" />;
  const groups = {};
  for (const [type, counts] of Object.entries(d.series)) {
    const label = SRC_LABEL[type] || type;
    groups[label] = (groups[label] || Array(d.candidates.length).fill(0)).map((v, i) => v + counts[i]);
  }
  const labels = Object.keys(groups);
  const ci = d.candidates.indexOf(CARLOS);
  const totals = labels.map((l) => [l, groups[l].reduce((a, b) => a + b, 0)]).sort((a, b) => b[1] - a[1]);
  const carlosBy = labels.map((l) => [l, groups[l][ci] || 0]).sort((a, b) => b[1] - a[1]);
  const cTotal = carlosBy.reduce((a, x) => a + x[1], 0);
  const options = {
    chart: { type: "bar", stacked: true },
    series: labels.map((l) => ({ name: l, data: groups[l] })),
    xaxis: { categories: d.candidates },
    colors: labels.map((l) => SRC_COLOR[l] || MUTED),
    plotOptions: { bar: { borderRadius: 3, columnWidth: "55%" } },
    dataLabels: { enabled: true, formatter: (v) => (v >= 6 ? v : ""), style: { colors: ["#fff"], fontWeight: 600, fontSize: "11px" } },
    legend: { position: "bottom" },
  };
  return (
    <Panel icon={Radar} tone="amber" title="¿En qué canales aparece cada candidato?" hint="Dónde se generan las menciones: prensa (medios de comunicación), YouTube (videos y comentarios) o Instagram / Facebook (posts y comentarios).">
      <Reading>
        {totals.length ? <>El canal con más conversación es <b>{totals[0][0]}</b> ({totals[0][1]} menciones en total).{" "}
          {cTotal ? <>Las menciones de <b>Carlos Arias</b> vienen sobre todo de <b>{carlosBy[0][0]}</b> ({pct(carlosBy[0][1], cTotal)}% de sus {cTotal})
            {carlosBy[1] && carlosBy[1][1] ? `, seguido de ${carlosBy[1][0]} (${pct(carlosBy[1][1], cTotal)}%).` : "."}</> : null}</> : "Sin datos en el período."}
      </Reading>
      <Chart options={options} height={420} label="Canales por candidato" minWidth={480} />
    </Panel>
  );
}

/* ---------- Percepción ---------- */
function Sentiment({ rows }) {
  const sc = rows.filter((r) => scored(r) > 0);
  const carlos = rows.find((r) => r.name === CARLOS) || rows[0];
  const byPos = [...sc].sort((a, b) => share(b, "positive") - share(a, "positive"));
  const byNeg = [...sc].sort((a, b) => share(b, "negative") - share(a, "negative"));
  const cRank = byPos.findIndex((r) => r.name === CARLOS);
  return (
    <Panel icon={HeartPulse} tone="green" title="¿Cómo se habla de cada candidato?" hint="De cada 100 menciones clasificadas, cuántas son positivas, neutrales o negativas. Entre paréntesis, el total de menciones clasificadas.">
      <Reading>
        {sc.length ? <><b>{byPos[0].name}</b> tiene la mejor imagen: {share(byPos[0], "positive")}% de sus menciones son positivas. <b>{byNeg[0].name}</b> concentra la mayor carga negativa ({share(byNeg[0], "negative")}% negativas).{" "}
          {cRank >= 0 && <><b>Carlos Arias</b> es {ordinal(cRank)} en positividad, con {share(carlos, "positive")}% positivas y {share(carlos, "negative")}% negativas sobre {scored(carlos)} menciones clasificadas.</>}</>
          : "Aún no hay menciones clasificadas en el período."}
      </Reading>
      <HBar100 categories={sc.map((r) => `${r.name} (${scored(r)})`)} colors={SENT_COLORS} label="Cómo se habla de cada candidato"
        series={[{ name: "Positivas", data: sc.map((r) => share(r, "positive")) }, { name: "Neutrales", data: sc.map((r) => share(r, "neutral")) }, { name: "Negativas", data: sc.map((r) => share(r, "negative")) }]} />
    </Panel>
  );
}

/* Volumen (menciones) contra positividad (%): 4 cuadrantes clásicos de análisis de reputación. */
function Quadrant({ rows }) {
  const sc = rows.filter((r) => scored(r) > 0);
  const hint = "Cada punto es un candidato. A la derecha, quienes más se mencionan; arriba, quienes mejor imagen tienen. El cuadrante ideal es arriba a la derecha: mucho volumen y buena imagen.";
  if (!sc.length) return <Panel icon={Crosshair} tone="violet" title="Volumen contra positividad: ¿quién habla mucho y bien?" hint={hint}><Reading>Aún no hay menciones clasificadas en el período.</Reading></Panel>;
  const sortedVol = sc.map((r) => r.mentions).sort((a, b) => a - b);
  const medVol = sortedVol[Math.floor(sortedVol.length / 2)];
  const pts = sc.map((r) => ({ name: r.name, x: r.mentions, y: share(r, "positive") }));
  const carlos = pts.find((p) => p.name === CARLOS);
  const rivals = pts.filter((p) => p.name !== CARLOS);
  const quadName = (p) => (p.x >= medVol ? (p.y >= 50 ? "mucho volumen y buena imagen" : "mucho volumen pero imagen floja") : (p.y >= 50 ? "poco volumen pero buena imagen" : "poco volumen y sin destacar"));
  const loudBad = rivals.filter((p) => p.x >= medVol && p.y < 50).sort((a, b) => b.x - a.x)[0];
  const options = {
    chart: { type: "scatter", zoom: { enabled: false } },
    series: [{ name: "Rivales", data: rivals.map((p) => [p.x, p.y]) }, ...(carlos ? [{ name: "Carlos Arias", data: [[carlos.x, carlos.y]] }] : [])],
    colors: [CARLOS_GRAY, BLUE],
    markers: { size: 10, strokeWidth: 3, strokeColors: "#fff" },
    xaxis: { title: { text: "menciones en el período" }, tickAmount: 5 },
    yaxis: { title: { text: "% de menciones positivas" }, min: 0, max: 100, labels: { formatter: (v) => Math.round(v) + "%" } },
    legend: { show: false },
    annotations: {
      xaxis: [{ x: medVol, borderColor: GRID, strokeDashArray: 4, label: { text: "mediana de volumen", orientation: "horizontal", style: { color: MUTED, background: "#fff", fontSize: "10px" } } }],
      yaxis: [{ y: 50, borderColor: GRID, strokeDashArray: 4, label: { text: "50% positividad", style: { color: MUTED, background: "#fff", fontSize: "10px" } } }],
      points: pts.map((p) => ({ x: p.x, y: p.y, marker: { size: 0 }, label: { text: p.name, offsetY: -14, borderWidth: 0, style: { color: INK, background: "transparent", fontSize: "11px", fontWeight: p.name === CARLOS ? 700 : 500 } } })),
    },
    tooltip: { custom: ({ seriesIndex, dataPointIndex }) => {
      const p = seriesIndex === 0 ? rivals[dataPointIndex] : carlos;
      return `<div style="padding:8px 12px"><b>${esc(p.name)}</b><br>${p.x} menciones · ${p.y}% positivas</div>`;
    } },
  };
  return (
    <Panel icon={Crosshair} tone="violet" title="Volumen contra positividad: ¿quién habla mucho y bien?" hint={hint}>
      <Reading>
        {carlos ? <><b>Carlos Arias</b> está en el cuadrante de <b>{quadName(carlos)}</b> ({carlos.x} menciones, {carlos.y}% positivas).
          {loudBad && <> El rival con más volumen e imagen floja es <b>{loudBad.name}</b> ({loudBad.x} menciones, {loudBad.y}% positivas) — ese es terreno para diferenciarse.</>}</>
          : "Sin datos de Carlos en el período."}
      </Reading>
      <Chart options={options} height={420} label="Volumen contra positividad" />
    </Panel>
  );
}

/* Participación en la conversación (share of voice) y sentimiento neto, semana a semana. */
function Conversation({ onWeek }) {
  const { days } = useApp();
  const { data: d } = useApi(`/api/conversation/weekly?days=${Math.max(days, 56)}`);
  if (!d) return <><PanelSkeleton h="h-96" /><PanelSkeleton h="h-96" /></>;
  const w = d.weeks.filter((x) => x.all_mentions > 0);
  const sc = w.filter((x) => x.scored > 0);
  const weekLabel = (x) => x.replace("-S", " · sem ");
  const last = sc[sc.length - 1];
  const avgShare = w.length ? (w.reduce((a, x) => a + x.share_pct, 0) / w.length).toFixed(1) : 0;

  const sovOptions = {
    chart: { type: "bar", events: { dataPointSelection: (_e, _c, cfg) => onWeek(w[cfg.dataPointIndex]?.week) } },
    series: [{ name: "Carlos Arias (% de las menciones de candidatos)", data: w.map((x) => x.share_pct) }],
    xaxis: { categories: w.map((x) => weekLabel(x.week)) },
    colors: [BLUE], plotOptions: { bar: { borderRadius: 4, columnWidth: "55%" } },
    dataLabels: { enabled: true, formatter: (v) => v + "%", style: { colors: [INK] }, offsetY: -18 },
    yaxis: { labels: { formatter: (v) => Math.round(v) + "%" } },
    tooltip: { y: { formatter: (v, { dataPointIndex }) => `${v}% · ${w[dataPointIndex].mentions} de ${w[dataPointIndex].all_mentions} menciones` } },
  };
  const netOptions = {
    chart: { type: "rangeArea", events: { dataPointSelection: (_e, _c, cfg) => onWeek(sc[cfg.dataPointIndex]?.week) } },
    series: [
      { type: "rangeArea", name: "Rango plausible (95%)", data: sc.map((x) => ({ x: weekLabel(x.week), y: [x.net_low, x.net_high] })) },
      { type: "line", name: "Sentimiento neto", data: sc.map((x) => ({ x: weekLabel(x.week), y: x.net_sentiment })) },
    ],
    colors: ["#c9dbf3", BLUE], fill: { opacity: [0.5, 1] }, stroke: { curve: "straight", width: [0, 3] },
    markers: { size: [0, 5] }, yaxis: { min: -100, max: 100, labels: { formatter: (v) => Math.round(v) } },
    annotations: { yaxis: [{ y: 0, borderColor: MUTED, strokeDashArray: 4 }] },
    tooltip: { shared: true, custom: ({ dataPointIndex }) => {
      const x = sc[dataPointIndex];
      return `<div style="padding:8px 12px"><b>${esc(x.week)}</b><br>neto ${x.net_sentiment} (rango ${x.net_low} a ${x.net_high})<br>${x.scored} menciones clasificadas</div>`;
    } },
    legend: { position: "bottom" },
  };
  return (
    <>
      <Panel icon={Activity} title="¿Qué parte de la conversación es de Carlos, semana a semana?"
        hint="Porcentaje de todas las menciones de candidatos que corresponden a Carlos Arias en cada semana (share of voice). Últimas 8 semanas como mínimo. Toca una barra para ver abajo las publicaciones de Carlos de esa semana.">
        <Reading>
          {w.length ? <>En promedio, Carlos concentra el <b>{avgShare}%</b> de las menciones de los candidatos por semana.{" "}
            {last && <>La última semana con datos ({last.week}) su sentimiento neto fue <b>{last.net_sentiment}</b> sobre {last.scored} menciones
              {last.scored < 15 ? `: con tan pocas menciones el rango va de ${last.net_low} a ${last.net_high}, así que no permite concluir si mejoró o empeoró.` : "."}</>}</>
            : "Sin menciones de candidatos en el período."}
        </Reading>
        <Chart options={sovOptions} height={420} label="Participación de Carlos semana a semana" clickable minWidth={560} />
      </Panel>
      <Panel icon={Scale} tone="green" title="Sentimiento neto de Carlos, con su margen"
        hint="% positivas menos % negativas en cada semana (de −100 a +100). La franja es el rango plausible al 95%: cuanto más ancha, menos menciones hubo y menos se puede concluir. Toca un punto para ver abajo las publicaciones de esa semana.">
        <CalloutFold label="Cómo leer esta gráfica, paso a paso">
          <ul>
            <li><b>La línea azul oscura («Sentimiento neto»)</b> es el dato real medido esa semana: de todas las menciones de Carlos que la IA clasificó, qué porcentaje fueron positivas menos qué porcentaje fueron negativas. Si una semana tuviera 70% positivas y 10% negativas, el neto sería +60. Si fueran 20% positivas y 50% negativas, el neto sería −30.</li>
            <li><b>0 es el punto neutro</b> (línea punteada gris): ni buena ni mala semana. Por encima de 0, predominan las menciones positivas; por debajo, las negativas.</li>
            <li><b>La franja celeste («Rango plausible 95%») es la parte más importante y la que más confunde.</b> No es un error de medición: es honestidad estadística. Con pocas menciones en una semana, el «% positivas» pudo salir distinto por puro azar de qué comentarios llegaron justo esos días. La franja muestra entre qué valores podría estar realmente el sentimiento de esa semana si hubiera habido más menciones. <b>Cuanto más angosta la franja, más se puede confiar en el número; cuanto más ancha, menos.</b></li>
            <li>Ejemplo real: si una semana el neto marca 0 pero la franja va de −56 a +56, eso NO significa «semana neutra» — significa «con tan pocas menciones, no se puede saber si esa semana fue buena o mala». En cambio, si el neto marca 92 con una franja angosta (de 63 a 98), ahí sí se puede confiar: esa semana fue claramente positiva.</li>
            <li>Por eso conviene mirar varias semanas seguidas en vez de una sola: una racha de semanas por encima de 0 (aunque cada una tenga franja ancha) sí es una señal confiable; una sola semana suelta con franja ancha, no.</li>
          </ul>
        </CalloutFold>
        <Chart options={netOptions} height={420} label="Sentimiento neto semanal" clickable minWidth={560} />
      </Panel>
    </>
  );
}

function WeekDetail({ week }) {
  const { data: people } = useApi("/api/social/candidates");
  const carlos = people?.find((p) => p.name === CARLOS);
  const feed = useApi(carlos ? `/api/feed?candidate_id=${carlos.candidate_id}&week=${week}&limit=80` : null);
  return (
    <Panel id="week-detail" icon={ListChecks} title={`Publicaciones de Carlos — semana ${week.replace("-S", " · sem ")}`} hint="Menciones de Carlos Arias en el período seleccionado (prensa, redes, YouTube) que componen ese dato de la gráfica.">
      {!people || feed.loading ? <Skeleton className="h-24" /> : !carlos ? <Empty>No se encontró a Carlos Arias.</Empty> : <FeedList rows={feed.data || []} />}
    </Panel>
  );
}

/* ---------- Temas ---------- */
function Topics() {
  const { days } = useApp();
  const pub = useApi(`/api/topics?days=${days}&kind=publications`);
  const com = useApi(`/api/topics?days=${days}&kind=comments`);
  const reading = (t, what) => (t.length
    ? <>El asunto más frecuente en {what} es <b>{t[0].topic}</b> ({t[0].count}){t[1] && <>, seguido de <b>{t[1].topic}</b> ({t[1].count})</>}{t[2] && <> y <b>{t[2].topic}</b> ({t[2].count})</>}.</>
    : `Sin asuntos identificados en ${what} para el período.`);
  return (
    <>
      <Panel icon={Globe2} title="¿De qué hablan las noticias y publicaciones?" hint="Asuntos más frecuentes en las notas de prensa, posts de Instagram / Facebook y videos de YouTube del período (todos los candidatos). No incluye comentarios.">
        {!pub.data ? <Skeleton className="h-72" /> : <><Reading>{reading(pub.data, "las noticias y publicaciones")}</Reading>
          <HBar categories={pub.data.map((x) => x.topic)} data={pub.data.map((x) => x.count)} colors={BLUE} label="Temas en noticias y publicaciones" /></>}
      </Panel>
      <Panel icon={HandHeart} tone="violet" title="¿Qué piden o reclaman los ciudadanos?" hint="Asuntos concretos que aparecen en los comentarios de la gente (Instagram, Facebook, YouTube). Los comentarios que solo aplauden o insultan, sin tratar un asunto, no se cuentan aquí.">
        {!com.data ? <Skeleton className="h-72" /> : <><Reading>{reading(com.data, "los comentarios de la gente")}</Reading>
          <HBar categories={com.data.map((x) => x.topic)} data={com.data.map((x) => x.count)} colors={VIOLET} label="Qué piden los ciudadanos" /></>}
      </Panel>
    </>
  );
}

export default function Analisis() {
  const { days } = useApp();
  const summary = useApi(`/api/summary?days=${days}`);
  const [week, setWeek] = useState(null);
  const rows = summary.data;
  if (!rows) return <div className="grid gap-5"><PanelSkeleton h="h-96" /><PanelSkeleton h="h-96" /></div>;
  if (!rows.length) return <Empty>Sin candidatos configurados todavía.</Empty>;

  const openWeek = (wk) => {
    if (!wk) return;
    setWeek(wk);
    requestAnimationFrame(() => document.getElementById("week-detail")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };
  return (
    <div className="grid gap-5">
      <SectionTitle>Alcance — quién habla y por dónde</SectionTitle>
      <Volume rows={rows} />
      <Timeline rows={rows} />
      <Sources />

      <SectionTitle>Percepción — cómo les está yendo</SectionTitle>
      <Sentiment rows={rows} />
      <Quadrant rows={rows} />
      <Conversation onWeek={openWeek} />
      {week && <WeekDetail week={week} />}

      <SectionTitle>Temas — de qué se habla</SectionTitle>
      <Topics />
    </div>
  );
}
