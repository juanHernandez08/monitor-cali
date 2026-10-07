import { useState } from "react";
import { Building2, Flame, HeartCrack, ListTree, Lightbulb, MapPinned, Rocket, Smile, Sparkles, ThumbsUp, Layers } from "lucide-react";
import { periodLabel, useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { CATEGORY_OPTIONS, cap, pct } from "../lib/format";
import { BLUE, CRITICAL, EMOTION_COLOR, GOOD, MUTED, NEUTRAL_TONE } from "../lib/palette";
import { Empty, Kpi, KpiGrid, Panel, PanelSkeleton, Select, Skeleton } from "../components/ui";
import { HBar, HBar100 } from "../charts/Chart";
import { EmotionHeatmap, SamplesDetail } from "../charts/Heatmap";
import { Quotes, TopicCards } from "../components/Feed";
import { FeedPanel } from "../components/FeedPanel";

function Opportunities({ opps }) {
  const [cat, setCat] = useState("");
  const novedades = opps.novedades.filter((t) => !cat || t.category === cat);
  const strong = opps.carlos_strong.filter((t) => !cat || t.category === cat);
  const select = (
    <Select label="Filtrar por categoría" value={cat} onChange={setCat}>
      <option value="">Todas las categorías</option>
      {CATEGORY_OPTIONS.map((c) => <option key={c} value={c}>{cap(c)}</option>)}
    </Select>
  );
  return (
    <Panel icon={Rocket} tone="green" title="Oportunidades para Carlos Arias" actions={select}
      hint="Temas nuevos o en fuerte alza en la ciudad (sea cual sea su tono) donde Carlos aún no tiene presencia, y temas donde ya suma.">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-rose-100 bg-gradient-to-br from-rose-50/70 to-white p-4">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-rose-700"><Flame className="size-4" />Novedades donde Carlos podría hablar</h3>
          {novedades.length ? (
            <ul className="grid gap-2 text-[13px] leading-relaxed text-slate-700">
              {novedades.map((t, i) => (
                <li key={i} className="rounded-lg bg-white/80 px-3 py-2 ring-1 ring-slate-100"><b>{cap(t.topic)}</b> <span className="text-slate-500">({cap(t.category)})</span>: {t.count} menciones
                  {t.is_new ? " · tema nuevo" : ` · ${t.trend_pct}% más que el período anterior`} · {pct(t.positive, t.count)}% a favor, {pct(t.negative, t.count)}% molestia · Carlos: {t.carlos_mentions === 0 ? "sin cobertura detectada en esta ventana" : `${t.carlos_mentions} menciones`}</li>
              ))}
            </ul>
          ) : <div className="text-sm text-slate-500">No hay temas nuevos ni en alza sin cobertura de Carlos en el período{cat ? " en esta categoría" : ""}.</div>}
        </div>
        <div className="rounded-2xl border border-emerald-100 bg-gradient-to-br from-emerald-50/70 to-white p-4">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-emerald-700"><ThumbsUp className="size-4" />Temas donde Carlos ya suma</h3>
          {strong.length ? (
            <ul className="grid gap-2 text-[13px] leading-relaxed text-slate-700">
              {strong.map((t, i) => <li key={i} className="rounded-lg bg-white/80 px-3 py-2 ring-1 ring-slate-100"><b>{cap(t.category)}</b>: {t.carlos_mentions} menciones de Carlos, {t.carlos_positive_pct}% positivas · la ciudad habló {t.city_count} veces del tema</li>)}
            </ul>
          ) : <div className="text-sm text-slate-500">Aún no hay temas con presencia positiva sostenida de Carlos en el período{cat ? " en esta categoría" : ""}.</div>}
        </div>
      </div>
    </Panel>
  );
}

export default function Ciudad() {
  const { days } = useApp();
  const topics = useApi(`/api/city/topics?days=${days}`);
  const opps = useApi(`/api/city/opportunities?days=${days}`);
  const kpis = useApi(`/api/city/kpis?days=${days}`);
  const emotions = useApi(`/api/city/emotions?days=${days}`);
  const emoByTopic = useApi(`/api/city/emotion-by-topic?days=${days}`);
  const [emoSel, setEmoSel] = useState(null);
  const [cell, setCell] = useState(null);
  const [openIdx, setOpenIdx] = useState(null);

  const k = kpis.data, tp = topics.data, em = emotions.data;
  const topEmotion = em ? (em.find((e) => e.emotion !== "sin emoción marcada") || em[0]) : null;
  const heat = (emoByTopic.data || []).slice(0, 12).map((r) => ({ name: r.category, emotions: r.emotions }));

  return (
    <div className="grid gap-5">
      {!k ? <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28" />)}</div> : (
        <KpiGrid>
          <Kpi icon={Building2} label="Menciones sobre la ciudad" value={k.total} foot={`noticias, videos, posts y comentarios · ${periodLabel(days)}`} />
          <Kpi delay={60} icon={MapPinned} small label="Tema del que más se habla" value={cap(k.top_category || "—")} foot="por número de menciones" />
          <Kpi delay={120} icon={Smile} iconTone="amber" small label="Emoción dominante" value={topEmotion ? cap(topEmotion.emotion) : "—"} foot={topEmotion ? `${topEmotion.count} menciones` : ""} />
          <Kpi delay={180} icon={HeartCrack} iconTone="red" tone={k.negative_pct >= 40 ? "neg" : "default"} label="Molestia ciudadana" value={k.total ? `${k.negative_pct}%` : "—"} foot="menciones con queja, miedo o indignación" />
        </KpiGrid>
      )}

      <Panel icon={Layers} title="¿De qué habla Cali en este período?" hint="Menciones por tema: seguridad, movilidad, servicios públicos y demás. Toca una barra para ver su detalle abajo.">
        {!tp ? <Skeleton className="h-80" /> : (
          <HBar categories={tp.map((t) => cap(t.category))} data={tp.map((t) => t.count)} colors={BLUE} label="Menciones por tema de ciudad"
            onClick={(i) => { setOpenIdx(i); requestAnimationFrame(() => document.getElementById(`city-t-${i}`)?.scrollIntoView({ behavior: "smooth", block: "center" })); }} />
        )}
      </Panel>

      <Panel icon={HeartCrack} tone="red" title="¿Cómo lo siente la gente?" hint="De cada 100 menciones del tema, cuántas son molestia (queja, miedo, indignación), cuántas informativas y cuántas a favor (orgullo, celebración).">
        {!tp ? <Skeleton className="h-80" /> : (() => {
          const sc = tp.filter((t) => t.count > 0);
          return <HBar100 categories={sc.map((t) => `${cap(t.category)} (${t.count})`)} colors={[CRITICAL, NEUTRAL_TONE, GOOD]} label="Percepción por tema"
            series={[{ name: "Molestia", data: sc.map((t) => pct(t.negative, t.count)) }, { name: "Informativa", data: sc.map((t) => pct(t.neutral, t.count)) }, { name: "A favor", data: sc.map((t) => pct(t.positive, t.count)) }]} />;
        })()}
      </Panel>

      <Panel icon={Smile} tone="amber" title="¿Qué emoción transmite la ciudad?" hint="Más allá de positivo/negativo: qué siente concretamente quien escribe — miedo, ira, felicidad, sorpresa y demás. Toca una barra para ver ejemplos.">
        {!em ? <Skeleton className="h-72" /> : (
          <>
            <HBar categories={em.map((e) => cap(e.emotion))} data={em.map((e) => e.count)} colors={em.map((e) => EMOTION_COLOR[e.emotion] || MUTED)} label="Emoción de la ciudad"
              onClick={(i) => setEmoSel(em[i])} />
            {emoSel ? (
              <div className="mt-3 animate-fade-in rounded-2xl border border-slate-200 bg-white p-4">
                <div className="mb-1 flex items-center justify-between gap-2"><h3 className="text-[15px] font-semibold">{cap(emoSel.emotion)}</h3><span className="text-sm text-slate-500">{emoSel.count} menciones</span></div>
                {emoSel.samples.length ? <Quotes rows={emoSel.samples} /> : <div className="text-sm text-slate-500">Sin ejemplos de muestra para esta emoción.</div>}
              </div>
            ) : <SamplesDetail url={null} />}
          </>
        )}
      </Panel>

      <Panel icon={Sparkles} tone="violet" title="¿Qué emoción transmite cada tema?" hint="Cruce tema × emoción: dentro de cada tema, qué tan presente está cada emoción. Más oscuro = más menciones. Toca una celda para ver qué está generando concretamente esa emoción (el apalancador).">
        {!emoByTopic.data ? <Skeleton className="h-72" /> : heat.length ? <EmotionHeatmap rows={heat} label="Emoción por tema" onCell={(r, e) => setCell({ name: r.name, emo: e })} /> : <Empty>Sin emociones clasificadas en el período.</Empty>}
        <SamplesDetail title={cell ? `${cap(cell.name)} · ${cap(cell.emo)}` : ""}
          url={cell ? `/api/city/topic-emotion-samples?category=${encodeURIComponent(cell.name)}&emotion=${encodeURIComponent(cell.emo)}&days=${days}` : null} />
      </Panel>

      {!opps.data ? <PanelSkeleton h="h-48" /> : <Opportunities opps={opps.data} />}

      <Panel icon={ListTree} title="Detalle por tema" hint="Toca un tema para ver sus subtemas y comentarios ciudadanos representativos, con link al original.">
        {!tp ? <Skeleton className="h-48" /> : (
          <TopicCards idPrefix="city-t" visibleCount={6} openIdx={openIdx}
            rows={tp.map((t) => ({ topic: cap(t.category), count: t.count, positive: t.positive, neutral: t.neutral, negative: t.negative,
              positive_pct: pct(t.positive, t.count), dominant_emotion: t.dominant_emotion, sources: t.sources, samples: t.samples, subtopics: t.subtopics }))} />
        )}
      </Panel>

      <FeedPanel icon={Lightbulb} tone="amber" title="Todo lo que pasa en Cali"
        hint="cada publicación de prensa, Instagram, Facebook y X que no nombra a ningún candidato — con su sentimiento, el de sus comentarios, el tema y la emoción"
        fixed={{ city: true }} fields={["source", "label", "emotion", "category", "sort"]} />
    </div>
  );
}
