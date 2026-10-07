import { useState } from "react";
import { useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { CATEGORY_OPTIONS, EMOTION_OPTIONS, cap } from "../lib/format";
import { Loading, Panel, Select } from "./ui";
import { FeedList } from "./Feed";

const LABELS = [["", "Todo sentimiento"], ["negative", "Negativo"], ["neutral", "Neutral"], ["positive", "Positivo"]];
const SORTS = [["recent", "Más reciente"], ["engagement", "Más alcance"], ["views", "Más visto"]];
const SOURCES = [["", "Todas las fuentes"], ["google_news", "Prensa (Google News)"], ["rss", "Prensa (RSS)"], ["youtube", "YouTube"], ["social", "Instagram / Facebook / X"]];

/* Panel con filtros + lista de menciones. Sirve para Prensa, YouTube y el feed de Ciudad: cada uno
   dice qué filtros muestra (`fields`) y qué parámetros fijos manda (`fixed`). */
export function FeedPanel({ title, hint, icon, tone, fixed, fields, showCandidate, empty }) {
  const { days } = useApp();
  const [f, setF] = useState({});
  const set = (k) => (v) => setF((p) => ({ ...p, [k]: v }));
  const summary = useApi(fields.includes("candidate") ? `/api/summary?days=${days}` : null);

  const p = new URLSearchParams({ days, limit: 80, ...fixed });
  for (const [k, v] of Object.entries(f)) if (v) p.set(k === "candidate" ? "candidate_id" : k === "source" ? "source_type" : k, v);
  const feed = useApi(`/api/feed?${p}`);

  const filters = (
    <>
      {fields.includes("candidate") && (
        <Select label="Filtrar por candidato" value={f.candidate || ""} onChange={set("candidate")}>
          <option value="">Todos los candidatos</option>
          {(summary.data || []).map((r) => <option key={r.candidate_id} value={r.candidate_id}>{r.name}</option>)}
        </Select>
      )}
      {fields.includes("source") && <Select label="Filtrar por fuente" value={f.source || ""} onChange={set("source")} options={SOURCES} />}
      {fields.includes("label") && <Select label="Filtrar por sentimiento" value={f.label || ""} onChange={set("label")} options={LABELS} />}
      {fields.includes("emotion") && (
        <Select label="Filtrar por emoción" value={f.emotion || ""} onChange={set("emotion")}>
          <option value="">Toda emoción</option>
          {EMOTION_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </Select>
      )}
      {fields.includes("category") && (
        <Select label="Filtrar por tema" value={f.category || ""} onChange={set("category")}>
          <option value="">Todos los temas</option>
          {CATEGORY_OPTIONS.map((c) => <option key={c} value={c}>{cap(c)}</option>)}
        </Select>
      )}
      {fields.includes("sort") && <Select label="Ordenar" value={f.sort || "recent"} onChange={set("sort")} options={SORTS} />}
    </>
  );

  return (
    <Panel icon={icon} tone={tone} title={title} hint={hint} actions={filters}>
      {!feed.data ? <Loading rows={4} /> : <FeedList rows={feed.data} showCandidate={showCandidate} empty={empty} />}
    </Panel>
  );
}
