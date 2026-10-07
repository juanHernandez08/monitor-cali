import { Clock, Heart, LineChart, MessageCircle, Newspaper, Sparkles, Swords, Target, TrendingUp, Trophy } from "lucide-react";
import { periodLabel, useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { CARLOS, SRC_LABEL, cap, clip, fmtNum } from "../lib/format";
import { BLUE, CARLOS_GRAY, CRITICAL, GOOD, INK, MUTED } from "../lib/palette";
import { Callout, Intro, Kpi, KpiGrid, Panel, PanelSkeleton, Reading, SectionTitle, Skeleton } from "../components/ui";
import { Chart, HBar, HBar100, SENT_COLORS } from "../charts/Chart";
import { splitByCouncil, useCouncilorNames } from "./Publicaciones";

/* Mediana, no promedio: un solo reel viral multiplicaba el promedio de una cuenta (auditoría
   estadística 2026-09-29). La tendencia también compara medianas de cada mitad del período. */
function ReachBlock({ rows, intro, trendHint, reachHint }) {
  const val = (c) => c.median_engagement ?? c.avg_engagement;
  const sorted = [...rows].sort((a, b) => val(b) - val(a));
  const trend = (c) => c.median_trend_pct ?? c.trend_pct;
  const trendRows = rows.filter((c) => trend(c) != null && c.posts >= 6);
  return (
    <>
      <Panel icon={Trophy} tone="amber" title="Alcance típico por publicación" hint={reachHint}>
        <HBar categories={sorted.map((c) => `${c.candidate} (${c.posts})`)} data={sorted.map(val)} colors={sorted.map((c) => (c.candidate === CARLOS ? BLUE : CARLOS_GRAY))} label="Alcance típico" />
      </Panel>
      {trendRows.length > 0 && (
        <Panel icon={TrendingUp} tone="green" title="Tendencia de alcance" hint={trendHint}>
          <HBar categories={trendRows.map((c) => c.candidate)} data={trendRows.map(trend)} colors={trendRows.map((c) => (trend(c) >= 0 ? GOOD : CRITICAL))}
            labelFmt={(v) => (v >= 0 ? "+" : "") + v + "%"} label="Tendencia de alcance" />
        </Panel>
      )}
      {intro}
    </>
  );
}

function ReactionBlock({ rows, hint }) {
  const withReaction = rows.filter((c) => c.comments > 0);
  return (
    <Panel icon={Heart} tone="red" title="Reacción de la audiencia" hint={hint}>
      <HBar100 categories={withReaction.map((c) => `${cap(c.candidate)} (${c.comments})`)} colors={SENT_COLORS} label="Reacción de la audiencia"
        series={[{ name: "Positivo", data: withReaction.map((c) => c.positive_pct) }, { name: "Neutral", data: withReaction.map((c) => c.neutral_pct) }, { name: "Negativo", data: withReaction.map((c) => c.negative_pct) }]} />
    </Panel>
  );
}

/* Qué le funciona a cada cuenta: alcance RELATIVO (1,0 = una publicación típica de esa cuenta). */
function RelBars({ title, hint, icon, rowsAll, rowsMine }) {
  const keys = rowsAll.map((r) => r.key);
  // Celdas de Carlos con menos de 5 publicaciones no se dibujan: un solo reel viral un sábado no demuestra que el sábado funcione.
  const mine = Object.fromEntries(rowsMine.filter((r) => r.conclusive).map((r) => [r.key, r]));
  const options = {
    chart: { type: "bar" },
    series: [{ name: "Todas las cuentas", data: rowsAll.map((r) => r.median_rel) }, { name: "Carlos Arias", data: keys.map((k) => (mine[k] ? mine[k].median_rel : null)) }],
    xaxis: { categories: keys.map((k) => { const a = rowsAll.find((r) => r.key === k); return `${cap(k)} (n=${a.n}${mine[k] ? `/${mine[k].n}` : ""})`; }) },
    colors: [CARLOS_GRAY, BLUE], plotOptions: { bar: { borderRadius: 4, columnWidth: "58%" } },
    dataLabels: { enabled: true, formatter: (v) => (v == null ? "" : v.toFixed(2) + "×"), style: { colors: [INK] }, offsetY: -18 },
    yaxis: { labels: { formatter: (v) => (v == null ? "" : Number(v).toFixed(1) + "×") } },
    annotations: { yaxis: [{ y: 1, borderColor: MUTED, strokeDashArray: 4, label: { text: "publicación típica", style: { color: MUTED, background: "#fff" } } }] },
    tooltip: { y: { formatter: (v, { seriesIndex, dataPointIndex }) => {
      if (v == null) return "sin publicaciones";
      const r = seriesIndex === 0 ? rowsAll[dataPointIndex] : mine[keys[dataPointIndex]];
      return `${v.toFixed(2)}× (la mitad central entre ${r.q1}× y ${r.q3}×, n=${r.n}${r.conclusive ? "" : ", no concluyente"})`;
    } } },
    legend: { position: "bottom" },
  };
  return <Panel icon={icon} title={title} hint={hint}><Chart options={options} height={340} label={title} /></Panel>;
}

function Insights() {
  const { days } = useApp();
  const { data: d } = useApi(`/api/social/insights?days=${Math.max(days, 60)}`);
  if (!d) return <div className="grid gap-5 xl:grid-cols-2"><PanelSkeleton /><PanelSkeleton /></div>;

  const wk = d.weekly;
  const weeklyOptions = {
    chart: { type: "line" },
    series: [{ name: "Carlos Arias (mediana)", data: wk.mine }, { name: "Resto de cuentas (mediana)", data: wk.others }],
    xaxis: { categories: wk.weeks.map((x) => x.replace("-S", " · sem ")) },
    colors: [BLUE, CARLOS_GRAY], stroke: { width: [3, 2], curve: "straight" }, markers: { size: [5, 3] },
    yaxis: { labels: { formatter: (v) => fmtNum(Math.round(v)) }, title: { text: "interacciones por publicación" } },
    tooltip: { shared: true, y: { formatter: (v, { seriesIndex, dataPointIndex }) => (v == null ? "sin publicaciones" : `${fmtNum(Math.round(v))}${seriesIndex === 0 ? ` (${wk.mine_n[dataPointIndex]} publicaciones)` : ""}`) } },
    legend: { position: "bottom" },
  };
  const cad = d.cadence.filter((r) => r.posts >= 2).slice(0, 18);
  const conc = d.all.format.filter((r) => r.conclusive);
  const best = [...conc].sort((a, b) => b.median_rel - a.median_rel)[0];
  const worst = [...conc].sort((a, b) => a.median_rel - b.median_rel)[0];
  const days7 = d.all.weekday.filter((r) => r.conclusive);
  const spread = days7.length ? (Math.max(...days7.map((r) => r.median_rel)) - Math.min(...days7.map((r) => r.median_rel))).toFixed(2) : null;
  const mineCad = d.cadence.filter((r) => r.candidate === CARLOS).reduce((a, r) => a + r.posts_per_week, 0);
  const others = d.cadence.filter((r) => r.candidate !== CARLOS).map((r) => r.posts_per_week).sort((a, b) => a - b);
  const medOthers = others.length ? others[Math.floor(others.length / 2)] : null;

  return (
    <>
      <Intro icon={Sparkles} title="Qué funciona en redes (análisis estadístico)">
        <p>Todas las cifras de esta sección usan <b>alcance relativo</b>: las interacciones de cada publicación divididas por la mediana de su propia cuenta. 1,0× es una publicación típica de esa cuenta y 2,0× el doble de lo habitual. Así una cuenta grande no aplasta a una pequeña. Entre paréntesis, cuántas publicaciones hay detrás de cada barra (todas las cuentas / Carlos). Las publicaciones con likes ocultos no se cuentan.</p>
        <p className="mt-2 rounded-lg bg-white/10 px-3 py-2 text-white">
          {best && worst ? <>En {d.posts_total} publicaciones, el formato que mejor rinde frente a lo habitual de cada cuenta es <b>{best.key}</b> ({best.median_rel}×); el que menos, <b>{worst.key}</b> ({worst.median_rel}×). </> : null}
          {spread !== null ? <>El día de la semana mueve poco el resultado (diferencia máxima de {spread}× entre días): pesa más qué y cuánto se publica que cuándo. </> : null}
          {medOthers !== null ? <>Carlos publica <b>{mineCad.toFixed(1)} veces por semana</b>; la cuenta mediana monitoreada, {medOthers}. </> : null}
          {d.engagement_per_view_pct ? <>De cada 100 personas que ven un video suyo, {d.engagement_per_view_pct} interactúan.</> : null}
        </p>
      </Intro>
      <div className="grid gap-5 xl:grid-cols-2">
        <RelBars icon={Newspaper} title="¿Qué formato rinde más?" hint="reel, carrusel, imagen, video, trino" rowsAll={d.all.format} rowsMine={d.candidate_dims.format} />
        <RelBars icon={Clock} tone="amber" title="¿Importa el día?" hint="hora Bogotá" rowsAll={d.all.weekday} rowsMine={d.candidate_dims.weekday} />
        <RelBars icon={Clock} title="¿Importa la franja horaria?" hint="madrugada, mañana, tarde, noche" rowsAll={d.all.hour_block} rowsMine={d.candidate_dims.hour_block} />
        <Panel icon={Swords} title="Ritmo de publicación" hint="publicaciones por semana, por cuenta y red">
          <HBar categories={cad.map((r) => `${r.candidate} · ${SRC_LABEL[r.platform] || r.platform}`)} data={cad.map((r) => r.posts_per_week)}
            colors={cad.map((r) => (r.candidate === CARLOS ? BLUE : CARLOS_GRAY))} labelFmt={(v) => v + "/sem"} label="Ritmo de publicación" />
        </Panel>
      </div>
      <Panel icon={LineChart} title="Interacciones por publicación, semana a semana" hint="Mediana semanal de Carlos Arias frente a la mediana del resto de cuentas monitoreadas. La mediana no se deja arrastrar por un solo reel viral.">
        <Chart options={weeklyOptions} height={400} label="Interacciones por publicación semana a semana" />
      </Panel>
    </>
  );
}

export default function Meta() {
  const { days } = useApp();
  const kpis = useApi(`/api/social/kpis?days=${days}`);
  const reach = useApi(`/api/social/reach?days=${days}`);
  const reaction = useApi(`/api/social/reaction?days=${days}`);
  const latest = useApi("/api/reports/latest");
  const { names } = useCouncilorNames();
  const k = kpis.data;
  const n = latest.data?.narrative;

  return (
    <div className="grid gap-5">
      <p className="px-1 text-[13px] leading-relaxed text-slate-500">Análisis de desempeño en redes sociales de todos los candidatos y concejales — alcance, reacción de la audiencia y estrategia recomendada. Para ver las publicaciones una por una, ir a Publicaciones → Redes sociales.</p>
      {!k ? <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28" />)}</div> : (
        <KpiGrid>
          <Kpi icon={Newspaper} label="Publicaciones" value={k.total_posts} foot={`Instagram, Facebook y X · ${periodLabel(days)}`} />
          <Kpi delay={60} icon={Heart} iconTone="red" label="Likes" value={k.total_likes} foot="suma de todas las publicaciones" />
          <Kpi delay={120} icon={MessageCircle} label="Comentarios" value={k.total_comments} foot="suma de todas las publicaciones" />
          <Kpi delay={180} icon={Trophy} iconTone="amber" small label="Publicación con más alcance"
            value={k.top_post ? clip(k.top_post.text, 46) : "—"} foot={k.top_post ? `${k.top_post.candidate} · ${fmtNum(k.top_post.engagement)} de alcance` : "sin publicaciones en el período"} />
        </KpiGrid>
      )}

      <SectionTitle>Candidatos a la Alcaldía</SectionTitle>
      {!reach.data || !reaction.data || !names ? <PanelSkeleton h="h-72" /> : (() => {
        const [reachCand, reachCouncil] = splitByCouncil(reach.data, names);
        const [reactCand, reactCouncil] = splitByCouncil(reaction.data, names);
        return (
          <>
            <ReachBlock rows={reachCand}
              reachHint={<>Cuántos «likes» y comentarios junta, en general, cada publicación — mide qué tanta gente ve e interactúa, no si esa interacción es buena o mala (eso está en «Reacción de la audiencia», más abajo, que mide algo distinto). Se usa la <b>mediana</b> (el valor «de la mitad»: la mitad de sus publicaciones queda por encima y la mitad por debajo) en vez del promedio, para que una sola publicación que se hizo viral no infle el número de las demás. Entre paréntesis, cuántas publicaciones se pudieron medir; no incluye las que la red social oculta. Carlos en azul.</>}
              trendHint="Si el alcance típico de arriba subió o bajó, comparando la primera mitad del período con la segunda (solo cuentas con 6 o más publicaciones). Verde sube, rojo baja. Ojo: un porcentaje grande no dice nada por sí solo si el alcance de partida era muy bajo — mirar siempre junto con la gráfica de arriba, que trae los números reales." />
            <ReactionBlock rows={reactCand}
              hint={<><b>Esto mide algo distinto al alcance de arriba.</b> De la gente que SÍ comenta en sus publicaciones (no menciones de paso en otro lado), qué porcentaje reacciona positivo, neutral o negativo. Se puede tener poco alcance (pocas personas ven o comentan) y aun así una reacción muy buena entre esas pocas — son dos cosas distintas, no una contradicción: una mide cuánta gente llega, la otra qué tan bien le cae a la gente que sí llegó.</>} />

            <SectionTitle>Concejales</SectionTitle>
            <p className="px-1 text-[13px] text-slate-500">No incluye a Carlos Arias ni a Roberto Ortiz — ya están en la sección de candidatos de arriba.</p>
            <ReachBlock rows={reachCouncil}
              reachHint="Mediana (el valor «de la mitad») de likes + comentarios por publicación — mide cuánta gente ve e interactúa, no si esa interacción es buena o mala. Concejales con al menos 2 publicaciones medibles en el período."
              trendHint="Si el alcance típico subió o bajó entre la primera y la segunda mitad del período. Verde sube, rojo baja. Un porcentaje grande no dice nada por sí solo si el punto de partida era muy bajo — comparar siempre con la gráfica de arriba." />
            <ReactionBlock rows={reactCouncil}
              hint={<><b>Mide algo distinto al alcance de arriba:</b> de quienes SÍ comentan en sus publicaciones, qué porcentaje reacciona positivo, neutral o negativo — no cuánta gente llega, sino qué tan bien le cae a la que llega.</>} />
          </>
        );
      })()}

      <SectionTitle>Qué funciona en redes</SectionTitle>
      <Insights />

      {n && (
        <Panel icon={Target} tone="violet" title="Análisis y estrategia" hint={`del análisis diario del ${latest.data.date} — ver el reporte completo en la pestaña Reporte`}>
          <Reading>{n.resumen_ejecutivo}</Reading>
          <p className="text-sm leading-relaxed text-slate-700">{n.factores_hipotesis}</p>
          {n.limitaciones && <Callout label="Qué NO se puede determinar con estos datos">{n.limitaciones}</Callout>}
          <h3 className="mb-2 mt-4 text-sm font-semibold text-slate-900">Plan de 72 horas</h3>
          <ul className="divide-y divide-slate-100 text-sm">
            {(n.plan_72h || []).length ? n.plan_72h.map((it, i) => <li key={i} className="py-2.5"><b>{it.dia}:</b> {it.accion}</li>) : <li className="py-2.5 text-slate-500">Sin plan generado en este corte.</li>}
          </ul>
        </Panel>
      )}
    </div>
  );
}
