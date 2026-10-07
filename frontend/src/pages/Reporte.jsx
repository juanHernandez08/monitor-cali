import { useEffect, useState } from "react";
import { Activity, AlertTriangle, ClipboardList, Download, FileText, Flame, Lightbulb, MapPinned, Megaphone, MessageSquareText, Microscope, Play, Rocket, ScanSearch, Smile, Target, TrendingUp, Users2 } from "lucide-react";
import { useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { clearCache } from "../lib/cache";
import { post, notify } from "../lib/api";
import { CARLOS, SRC_LABEL, cap, clip, esc, fmtNum } from "../lib/format";
import { BLUE, CARLOS_GRAY, CRITICAL, GOOD, INK, MUTED } from "../lib/palette";
import { Button, Callout, Empty, Intro, Kpi, KpiGrid, LinkOut, Panel, PanelSkeleton, Reading, SectionTitle, Select, Skeleton, Tag } from "../components/ui";
import { Chart, HBar, HBar100, SENT_COLORS } from "../charts/Chart";
import { SimpleQuote } from "../components/Feed";

const INTENSITY = (v) => (v >= 0.6 ? "alta" : v >= 0.35 ? "media" : "leve");
const SHARE_COLORS = ["#c0392b", "#7a4fb0", "#7a8a2e", "#5b7a99", "#2c7a5b", "#d9822b", "#b9bec9"];

/* «otro» desagregado en sus subtemas reales: un cajón de sastre sin abrir no dice nada. */
const repTopicLabel = (t) => (t.category !== "otro" || !t.subtopics?.length ? cap(t.category) : `Otro — ${t.subtopics.slice(0, 3).map((s) => s.topic).join(", ")}`);
const noPresence = (n) => (n === 0 ? "no se detectaron publicaciones clasificadas sobre este tema en las cuentas y la ventana revisadas" : `${n} menciones`);

function ListItem({ children, meta }) {
  return <li className="py-3 text-sm"><div className="text-slate-800">{children}</div>{meta && <div className="mt-1 text-xs text-slate-500">{meta}</div>}</li>;
}

function EmotionHeatmapBlock({ r, hm }) {
  const row0 = hm.rows[0];
  const real0 = Object.entries(row0.cells).filter(([e]) => e !== "sin emoción marcada").sort((a, b) => b[1].count - a[1].count)[0];
  const example = real0
    ? `Por ejemplo, «${cap(row0.category)}» tuvo ${row0.total} menciones: esas ${row0.total} son el 100 %. «${real0[1].count} (${real0[1].pct} % del tema)» quiere decir que ${real0[1].count} de esas ${row0.total} expresan ${real0[0]} (${real0[1].count} de ${row0.total} = ${real0[1].pct} %).`
    : "Todas las menciones de un tema suman el 100 % de ese tema. «N (X % del tema)» quiere decir que N de esas menciones expresan esa emoción y N es el X % del total del tema.";
  const heatOptions = {
    chart: { type: "heatmap" },
    series: hm.rows.map((row) => ({ name: cap(row.category), data: hm.emotions.map((e) => ({ x: e === "sin emoción marcada" ? "Sin emoción" : cap(e), y: (row.cells[e] || {}).count || 0 })) })),
    colors: [BLUE],
    plotOptions: { heatmap: { radius: 6, colorScale: { ranges: [{ from: 0, to: 0, color: "#eef1f6" }] } } },
    stroke: { width: 3, colors: ["#fff"] },
    dataLabels: { enabled: true, style: { colors: [INK], fontWeight: 600 } },
    xaxis: { labels: { style: { colors: MUTED } }, position: "top" },
    legend: { show: false },
    tooltip: { custom: ({ seriesIndex, dataPointIndex }) => {
      const row = hm.rows[seriesIndex], emo = hm.emotions[dataPointIndex], c = row.cells[emo];
      return `<div style="padding:8px 12px;font-size:12px"><b>${esc(cap(row.category))} · ${esc(cap(emo))}</b><br>` +
        (c ? `${c.count} menciones (${c.pct}% del tema)<br>intensidad ${c.intensity.toFixed(2)} (${INTENSITY(c.intensity)})` : "sin menciones") + "</div>";
    } },
  };
  return (
    <Panel icon={Smile} tone="amber" title="Mapa de calor: emociones percibidas por tema"
      hint={<>Últimos {r.city_window_days} días. Color y número = menciones de cada celda. <b>Intensidad</b> = fuerza media de la carga emocional de esas menciones, de 0 (leve) a 1 (muy fuerte); al pasar el cursor sobre una celda se ve junto con su % del tema.</>}>
      <Callout label="Cómo leer esto, paso a paso">
        <b>Cada tema es un 100 %.</b> {example}{" "}
        <b>El resto del 100 %</b> se reparte en las demás emociones y en «sin emoción marcada» (textos que solo informan); el gráfico de barras de abajo muestra el reparto completo.{" "}
        Las tarjetas de apalancadores solo muestran las <b>dos emociones más fuertes</b> de cada tema, por eso sus porcentajes no suman 100 %.{" "}
        <b>Intensidad:</b> qué tan fuerte es lo que sienten, de 0 (leve) a 1 (muy fuerte).
      </Callout>
      <Chart options={heatOptions} height={Math.max(220, hm.rows.length * 38 + 40)} label="Mapa de calor de emociones por tema" />
      <h3 className="mb-1 mt-5 text-sm font-semibold text-slate-900">Cómo se reparte el 100 % de cada tema</h3>
      <HBar100 categories={hm.rows.map((row) => `${cap(row.category)} (${row.total})`)} colors={SHARE_COLORS} label="Reparto de emociones por tema"
        series={hm.emotions.map((e) => ({ name: cap(e), data: hm.rows.map((row) => Math.round((((row.cells[e] || {}).count || 0) / row.total) * 100)) }))} />
      <h3 className="mb-2 mt-5 text-sm font-semibold text-slate-900">Apalancadores: qué dispara cada emoción</h3>
      <div className="grid gap-3 lg:grid-cols-2">
        {hm.levers.map((lv, i) => {
          const row = hm.rows.find((x) => x.category === lv.category);
          const rest = row ? Object.entries(row.cells).filter(([e]) => e !== lv.emotion).sort((a, b) => b[1].count - a[1].count)
            .map(([e, c]) => `${e === "sin emoción marcada" ? "sin emoción" : e} ${c.pct}%`).join(" · ") : "";
          return (
            <div key={i} className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h4 className="text-[15px] font-semibold text-slate-900">{cap(lv.category)} · {cap(lv.emotion)}</h4>
                <span className="text-xs text-slate-500">{lv.count} menciones ({lv.pct}% del tema) · intensidad {lv.intensity.toFixed(2)} ({INTENSITY(lv.intensity)})</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">El resto del tema ({100 - lv.pct}%): {rest}</p>
              {lv.apalancadores.length ? (
                <ul className="my-2 grid gap-1 text-[13px] text-slate-700">
                  {lv.apalancadores.map((a, j) => <li key={j} className="flex gap-2"><span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-brand-400" /><span>{a.text} <span className="text-xs text-slate-400">· n={a.count} · int. {a.intensity.toFixed(2)}</span></span></li>)}
                </ul>
              ) : <p className="my-2 text-xs text-slate-500">Sin apalancador registrado en estas menciones.</p>}
              {lv.ejemplo?.text && <SimpleQuote text={lv.ejemplo.text} source={lv.ejemplo.source} url={lv.ejemplo.url} />}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function ReportBody({ date }) {
  const { data: r, loading } = useApi(`/api/reports/${date}`);
  if (loading || !r) return <div className="grid gap-5"><Skeleton className="h-28" /><PanelSkeleton /></div>;
  if (r.error) return <Empty>{r.error}</Empty>;

  const k = r.social_kpis, n = r.narrative, scope = r.method_scope || {}, changes = r.changes_vs_previous;
  const reach = r.reach_comparison || [], reaction = (r.comment_reaction || []).filter((c) => c.comments > 0);
  const gaps = r.topic_gaps || [], convEmotions = r.conversation_emotions || [];
  const hm = r.emotion_heatmap && r.emotion_heatmap.rows.length ? r.emotion_heatmap : null;
  const trendRows = reach.filter((c) => c.trend_pct !== null);
  const carlosColor = (c) => (c.candidate === CARLOS ? BLUE : CARLOS_GRAY);

  return (
    <div className="grid gap-5">
      <KpiGrid>
        <Kpi icon={Megaphone} label="Publicaciones (redes)" value={k.total_posts} foot={`últimos ${r.social_window_days} días`} />
        <Kpi delay={60} icon={Activity} iconTone="red" label="Likes" value={k.total_likes} />
        <Kpi delay={120} icon={MessageSquareText} label="Comentarios" value={k.total_comments} />
        <Kpi delay={180} icon={ClipboardList} iconTone={r.pending_review.total ? "red" : "slate"} tone={r.pending_review.total ? "neg" : "default"} label="Pendiente de análisis" value={r.pending_review.total} />
      </KpiGrid>

      {n ? (
        <Intro icon={FileText} title="Resumen ejecutivo"><p>{n.resumen_ejecutivo}</p></Intro>
      ) : (
        <Intro icon={FileText} title="Análisis narrativo no disponible en este corte">
          <p>El análisis narrativo aún no se redactó: lo hace la inteligencia artificial del PC del cliente, que estaba apagado o sin conexión al generar este reporte. Se completa solo cuando vuelve a estar en línea (revisa cada 10 minutos). Las cifras y gráficas de abajo son reales e íntegras igual.</p>
        </Intro>
      )}

      <Panel icon={Microscope} title="Método y alcance"
        hint={`Generado el ${scope.generado || "—"}. «Alcance» = likes + comentarios por publicación (no reproducciones ni «personas alcanzadas», que las plataformas no entregan por scraping). Se usa la mediana porque un solo post viral infla el promedio.`}>
        <p className="text-sm leading-relaxed text-slate-700">En los últimos {r.city_window_days} días se revisaron <b>{scope.publicaciones_revisadas_7d || 0} publicaciones</b> y <b>{scope.comentarios_revisados_7d || 0} comentarios</b>, de {scope.cuentas_y_medios_revisados || 0} cuentas/medios ({(scope.plataformas || []).join(", ") || "sin datos"}).</p>
      </Panel>

      <Panel icon={ScanSearch} tone="violet" title="Cambios frente al informe anterior">
        {!changes ? <p className="text-sm text-slate-500">No hay un reporte anterior guardado con el cual comparar (primer corte).</p> : (
          <div className="grid gap-3 text-sm">
            <p className="text-slate-500">Comparado con el reporte del {changes.informe_anterior}:</p>
            {changes.aparecio.length > 0 && <div><b>Apareció:</b> <div className="mt-1 flex flex-wrap gap-1.5">{changes.aparecio.map((c) => <Tag key={c} tone="positive">{cap(c)}</Tag>)}</div></div>}
            {changes.cambio.length > 0 && <div><b>Cambió:</b><ul className="ml-5 mt-1 list-disc">{changes.cambio.map((c) => <li key={c.category}>{cap(c.category)}: {c.antes} → {c.ahora} menciones ({c.variacion_pct >= 0 ? "+" : ""}{c.variacion_pct}%)</li>)}</ul></div>}
            {changes.persiste.length > 0 && <div><b>Persiste:</b> <div className="mt-1 flex flex-wrap gap-1.5">{changes.persiste.map((c) => <Tag key={c}>{cap(c)}</Tag>)}</div></div>}
            {changes.no_se_pudo_volver_a_comprobar.length > 0 && <div><b>No se pudo volver a comprobar en esta ventana:</b> <div className="mt-1 flex flex-wrap gap-1.5">{changes.no_se_pudo_volver_a_comprobar.map((c) => <Tag key={c} tone="pending">{cap(c)}</Tag>)}</div></div>}
          </div>
        )}
      </Panel>

      <SectionTitle>Métricas y comparación entre cuentas</SectionTitle>
      <Panel icon={TrendingUp} tone="amber" title="Alcance típico por publicación (mediana)" hint={`likes + comentarios por publicación, candidatos y concejales con al menos 2 posts en ${r.comparison_window_days} días. Carlos en azul.`}>
        <HBar categories={reach.map((c) => c.candidate)} data={reach.map((c) => c.median_engagement ?? c.avg_engagement)} colors={reach.map(carlosColor)} label="Alcance típico" />
      </Panel>
      {trendRows.length > 0 && (
        <Panel icon={TrendingUp} tone="green" title="Tendencia de alcance" hint="variación de la mediana entre la primera y la segunda mitad del período — verde sube, rojo baja">
          <HBar categories={trendRows.map((c) => c.candidate)} data={trendRows.map((c) => c.trend_pct)} colors={trendRows.map((c) => (c.trend_pct >= 0 ? GOOD : CRITICAL))} labelFmt={(v) => (v >= 0 ? "+" : "") + v + "%"} label="Tendencia de alcance" />
        </Panel>
      )}
      <Panel icon={Users2} tone="red" title="Reacción ciudadana en comentarios propios" hint="solo comentarios dejados en la publicación de cada quien, mínimo 3 comentarios — quien comenta ahí no es una muestra de toda Cali, es la audiencia que ya sigue esa cuenta.">
        <HBar100 categories={reaction.map((c) => `${cap(c.candidate)} (${c.comments})`)} colors={SENT_COLORS} label="Reacción ciudadana"
          series={[{ name: "Positivo", data: reaction.map((c) => c.positive_pct) }, { name: "Neutral", data: reaction.map((c) => c.neutral_pct) }, { name: "Negativo", data: reaction.map((c) => c.negative_pct) }]} />
      </Panel>
      <Panel icon={Megaphone} title="Publicaciones por candidato y concejal" hint={`últimos ${r.social_window_days} días`}>
        <HBar categories={k.by_candidate.map((c) => c.candidate)} data={k.by_candidate.map((c) => c.count)} colors={k.by_candidate.map(carlosColor)} label="Publicaciones por candidato y concejal" />
      </Panel>
      <Panel icon={Flame} tone="amber" title="Actividad fuerte en redes">
        {r.strong_social.length ? (
          <ul className="divide-y divide-slate-100">
            {r.strong_social.map((p, i) => (
              <ListItem key={i} meta={<>{SRC_LABEL[p.platform] || p.platform} · ❤️ {fmtNum(p.likes)} · 💬 {fmtNum(p.comments)}{p.url && <> · <LinkOut href={p.url}>ver</LinkOut></>}</>}>
                <Tag tone="positive" className="mr-2">{p.multiplier}×</Tag><b>{p.candidate}</b>: {clip(p.text, 160)}
              </ListItem>
            ))}
          </ul>
        ) : <Empty icon={Flame}>Sin publicaciones fuera de lo habitual.</Empty>}
      </Panel>
      <Panel icon={MapPinned} title="Temas de ciudad — los más mencionados" hint={`últimos ${r.city_window_days} días`}>
        <HBar categories={r.city_topics.map(repTopicLabel)} data={r.city_topics.map((t) => t.count)} colors={BLUE} label="Temas de ciudad" />
      </Panel>
      <Panel icon={AlertTriangle} tone="amber" title="Temas de ciudad sin cobertura de Carlos en esta ventana" hint={`categorías con conversación real en la ciudad, sin publicación clasificada de Carlos en los últimos ${r.city_window_days} días`}>
        {gaps.length ? <ul className="divide-y divide-slate-100">{gaps.map((g) => <ListItem key={g.category}><b>{cap(g.category)}</b>: {g.count} menciones en la ciudad — {noPresence(0)}</ListItem>)}</ul>
          : <Empty>Carlos tiene al menos una mención en todas las categorías activas.</Empty>}
      </Panel>
      <Panel icon={Rocket} tone="green" title="Novedades donde Carlos podría hablar">
        {r.city_opportunities.novedades.length ? (
          <ul className="divide-y divide-slate-100">
            {r.city_opportunities.novedades.map((t, i) => <ListItem key={i}><b>{cap(t.topic)}</b> <span className="text-xs text-slate-500">({cap(t.category)})</span>: {t.count} menciones · Carlos: {noPresence(t.carlos_mentions)}</ListItem>)}
          </ul>
        ) : <Empty>Sin novedades sin presencia de Carlos en el período.</Empty>}
      </Panel>

      <SectionTitle>Conversación y emociones</SectionTitle>
      {hm && <EmotionHeatmapBlock r={r} hm={hm} />}
      <Panel icon={Lightbulb} tone="amber" title="Qué situación concreta hay detrás de cada tema" hint="Emoción predominante y su apalancador — qué está generando concretamente esa emoción, no solo cuánto se habla del tema.">
        {convEmotions.length ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {convEmotions.map((ce, i) => (
              <div key={i} className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h4 className="text-[15px] font-semibold text-slate-900">{repTopicLabel({ category: ce.category, subtopics: [] })}</h4>
                  <span className="text-xs text-slate-500">{ce.count} menciones · siente, sobre todo: {ce.dominant_emotion || "sin emoción marcada"}</span>
                </div>
                {ce.apalancadores.length > 0 && <p className="my-2 text-[13px] text-slate-700">Lo que más dispara esta emoción: <b>{ce.apalancadores.join("; ")}</b></p>}
                {ce.evidencia.map((ev, j) => <SimpleQuote key={j} text={ev.text} source={ev.source} url={ev.url} />)}
              </div>
            ))}
          </div>
        ) : <Empty>Sin suficientes menciones clasificadas en esta ventana.</Empty>}
      </Panel>

      {n && (
        <>
          <Panel icon={Target} title="Activación y respuesta factual"><Reading>{n.activacion_respuesta}</Reading></Panel>
          <Panel icon={Microscope} tone="violet" title="Factores observados e hipótesis por comprobar" hint={`correlaciones observadas en los datos de este corte, últimos ${r.comparison_window_days} días — no causas demostradas`}>
            <Reading>{n.factores_hipotesis}</Reading>
            {n.limitaciones && <Callout label="Qué NO se puede determinar con estos datos">{n.limitaciones}</Callout>}
          </Panel>
          <Panel icon={Play} tone="green" title="Plan de 72 horas">
            {(n.plan_72h || []).length ? (
              <ul className="divide-y divide-slate-100">
                {n.plan_72h.map((it, i) => (
                  <ListItem key={i}><b>{it.dia}:</b> {it.accion}
                    {it.dato_necesario && <span className="text-xs text-slate-500"> — dato necesario: {it.dato_necesario}; fuente: {it.fuente}; condición para publicar: {it.condicion_para_publicar}</span>}</ListItem>
                ))}
              </ul>
            ) : <Empty>Sin plan generado en este corte.</Empty>}
          </Panel>
        </>
      )}

      <Panel icon={ClipboardList} tone="slate" title="Fuentes, límites y pendientes"
        hint={`${r.pending_review.total} menciones totales sin clasificar aún, algunas de muestra abajo — lo que digan no está reflejado en las cifras de arriba todavía`}>
        {r.pending_review.samples.length ? (
          <div className="grid gap-2.5">
            {r.pending_review.samples.map((s, i) => (
              <article key={i} className="rounded-2xl border border-slate-200/80 bg-white p-3.5">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500"><b className="text-slate-800">{s.candidate}</b><Tag tone="brand">{s.source}</Tag><LinkOut href={s.url} /></div>
                <p className="text-sm text-slate-800">{s.text}</p>
              </article>
            ))}
          </div>
        ) : <Empty>Nada pendiente por ahora.</Empty>}
      </Panel>
    </div>
  );
}

export default function Reporte() {
  const { refresh } = useApp();
  const list = useApi("/api/reports");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const dates = (list.data || []).map((x) => x.date);
  useEffect(() => { if (dates.length && !dates.includes(date)) setDate(dates[0]); }, [dates.join(","), date]); // eslint-disable-line react-hooks/exhaustive-deps

  async function generate() {
    setBusy(true);
    try {
      const r = await post("/api/reports/generate");
      if (r.status === 429) { const d = await r.json(); notify(d.error || "Espera un momento antes de regenerar."); }
      else if (!r.ok) notify("No se pudo generar el reporte.", "error");
      clearCache(); refresh();
    } finally { setBusy(false); }
  }

  return (
    <div className="grid gap-5">
      <Intro icon={FileText} title="Reporte diario">
        <p>Se genera solo, de lunes a viernes en la mañana: actividad en redes de candidatos y concejales, publicaciones con fuerza fuera de lo habitual, temas de ciudad y lo que todavía no se ha analizado. Queda guardado — puedes revisar cualquier día anterior.</p>
      </Intro>
      <Panel>
        <div className="flex flex-wrap items-center gap-2.5">
          <Select label="Fecha del reporte" value={date} onChange={setDate}>
            {dates.length ? dates.map((d) => <option key={d} value={d}>{d}</option>) : <option value="">Sin reportes todavía</option>}
          </Select>
          <Button onClick={generate} loading={busy} icon={Play}>{busy ? "Generando…" : "Generar el de hoy"}</Button>
          <Button variant="ghost" icon={Download} disabled={!date} onClick={() => window.open(`/api/reports/${encodeURIComponent(date)}/pdf`, "_blank", "noopener")}>Descargar PDF</Button>
        </div>
      </Panel>
      {!list.data ? <PanelSkeleton /> : date ? <ReportBody date={date} key={date} /> : <Empty>Aún no se ha generado ningún reporte. Toca «Generar el de hoy».</Empty>}
    </div>
  );
}
