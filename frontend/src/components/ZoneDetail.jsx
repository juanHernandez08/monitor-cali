import { useEffect, useRef, useState } from "react";
import { FilterX, LayoutList, ListTree, MapPinned, MessageSquareText, Newspaper, PlaySquare, Share2 } from "lucide-react";
import { useApi } from "../lib/useApi";
import { cap, clip, fmtDate, fmtNum } from "../lib/format";
import { Callout, Empty, Kpi, KpiGrid, LinkOut, Panel, PanelSkeleton, Segmented, Select, Tag, cx } from "./ui";
import { FeedItem, SentBadge, SourceChip } from "./Feed";

const KIND = { noticia: ["Noticias", Newspaper], publicacion: ["Publicaciones", Share2], comentario: ["Comentarios", MessageSquareText], video: ["Videos", PlaySquare] };
const CHANNEL = { prensa: "Prensa", redes: "Redes sociales", youtube: "YouTube" };
const LABEL = { negative: "Negativas", positive: "Positivas", neutral: "Neutrales" };
const SORT = [["recent", "Más recientes"], ["negative", "Más negativas primero"], ["positive", "Más positivas primero"]];
const EMPTY_F = { kind: "", channel: "", category: "", topic: "", label: "", subzone: "" };
const PAGE = 30;

const countOf = (facet, v) => facet?.find((x) => x.value === v)?.count || 0;
const withCount = (facet, labels, allLabel, total) => [["", `${allLabel} (${fmtNum(total)})`],
  ...(facet || []).map((x) => [x.value, `${labels ? labels[x.value]?.[0] || labels[x.value] || cap(x.value) : cap(x.name || x.value)} (${fmtNum(x.count)})`])];

/* Una mención en una línea (dentro de los bloques por tema): tipo, fuente, fecha, texto y tono. */
function MiniItem({ r }) {
  return (
    <li className="grid gap-1 py-2.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
        <SourceChip m={r} /><span>{fmtDate(r.published_at)}</span><SentBadge m={r} /><LinkOut href={r.link || r.url} />
      </div>
      <p className="line-clamp-2 text-[13px] leading-relaxed text-slate-800">{r.summary || clip(r.text, 240)}</p>
    </li>
  );
}

function ToneBar({ neg, pos }) {
  return (
    <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-slate-200" title={`${pos} % positivas · ${neg} % negativas`}>
      <span style={{ width: `${pos}%` }} className="bg-emerald-500" />
      <span style={{ width: `${Math.max(0, 100 - pos - neg)}%` }} className="bg-slate-300" />
      <span style={{ width: `${neg}%` }} className="bg-rose-500" />
    </div>
  );
}

function ActiveChips({ f, set, facets }) {
  const names = {
    kind: (v) => KIND[v]?.[0], channel: (v) => CHANNEL[v], category: cap, topic: (v) => `«${v}»`, label: (v) => LABEL[v],
    subzone: (v) => facets?.subzone?.find((x) => x.value === v)?.name || v,
  };
  const on = Object.entries(f).filter(([, v]) => v);
  if (!on.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {on.map(([k, v]) => <Tag key={k} tone="brand" onClick={() => set({ ...f, [k]: "" })} title="Quitar este filtro">{names[k](v)} ✕</Tag>)}
      <button type="button" onClick={() => set(EMPTY_F)} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-800">
        <FilterX className="size-3.5" />Quitar filtros
      </button>
    </div>
  );
}

export function ZoneDetail({ ids, title, days, color, candidateId }) {
  const [f, setF] = useState(EMPTY_F);
  const [view, setView] = useState("tema");
  const [sort, setSort] = useState("recent");
  const [limit, setLimit] = useState(PAGE);
  const idsKey = ids.join(",");
  useEffect(() => { setF(EMPTY_F); setLimit(PAGE); }, [idsKey, candidateId]);
  const set = (next) => { setF(next); setLimit(PAGE); };

  const qs = new URLSearchParams({ days: String(days), ids: idsKey, sort, limit: String(view === "lista" ? limit : 1) });
  Object.entries(f).forEach(([k, v]) => v && qs.set(k, v));
  if (candidateId) qs.set("candidate_id", candidateId);
  if (view === "tema") qs.set("group", "category");
  const api = useApi(ids.length ? `/api/geo/detail?${qs}` : null);
  // al cambiar un filtro o pedir más, se sigue viendo lo anterior (atenuado) en vez de un esqueleto
  const last = useRef(null);
  if (api.data) last.current = api.data;
  const d = api.data || (last.current && last.current.ids.join(",") === idsKey ? last.current : null);
  const loading = api.loading;
  if (!ids.length) return null;
  if (!d) return <PanelSkeleton h="h-72" />;

  const fac = d.facets;
  const filtered = Object.values(f).some(Boolean);
  const few = d.mentions < 5;

  return (
    <Panel icon={MapPinned} title={title} hint={`${d.names.length > 3 ? `${d.names.length} zonas` : d.names.join(", ")} · últimos ${days} días`}
      actions={color && <span className="inline-block h-3 w-10 rounded" style={{ background: color }} />}>
      <KpiGrid>
        <Kpi label={filtered ? "Menciones con estos filtros" : "Menciones de la zona"} value={d.mentions} foot={filtered ? `de ${fmtNum(d.total)} en la zona` : `${d.scored} clasificadas`} />
        <Kpi delay={60} label="Negativas" value={d.negative_pct} suffix=" %" tone={d.negative_pct >= 40 ? "neg" : "default"} foot={`${d.negative} menciones`} />
        <Kpi delay={120} label="Positivas" value={d.positive_pct} suffix=" %" foot={`${d.positive} menciones`} />
        <Kpi delay={180} label="Sentimiento neto" value={d.net ?? 0} foot="% positivas − % negativas" />
      </KpiGrid>

      {/* ---------- filtros ---------- */}
      <div className="mt-4 grid gap-2.5 rounded-2xl border border-slate-200 bg-slate-50/70 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Segmented size="sm" value={f.kind} onChange={(v) => set({ ...f, kind: v })} label="Tipo de contenido"
            options={[["", `Todo (${fmtNum(fac.kind.reduce((a, x) => a + x.count, 0))})`],
              ...Object.entries(KIND).filter(([k]) => countOf(fac.kind, k) || f.kind === k).map(([k, [l, I]]) => [k, `${l} (${countOf(fac.kind, k)})`, I])]} />
          <Segmented size="sm" value={f.channel} onChange={(v) => set({ ...f, channel: v })} label="Canal"
            options={[["", "Todos los canales"], ...Object.entries(CHANNEL).filter(([k]) => countOf(fac.channel, k) || f.channel === k).map(([k, l]) => [k, `${l} (${countOf(fac.channel, k)})`])]} />
        </div>
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-5">
          <Select value={f.category} onChange={(v) => set({ ...f, category: v, topic: "" })} label="Tema" options={withCount(fac.category, null, "Todos los temas", fac.category.reduce((a, x) => a + x.count, 0))} />
          <Select value={f.topic} onChange={(v) => set({ ...f, topic: v })} label="Asunto" options={withCount(fac.topic, null, "Todos los asuntos", d.mentions)} />
          <Select value={f.label} onChange={(v) => set({ ...f, label: v })} label="Tono" options={withCount(fac.label, Object.fromEntries(Object.entries(LABEL).map(([k, v]) => [k, [v]])), "Todo tono", fac.label.reduce((a, x) => a + x.count, 0))} />
          <Select value={f.subzone} onChange={(v) => set({ ...f, subzone: v })} label="Barrio o zona" options={withCount(fac.subzone, null, "Todos los barrios", d.mentions)} />
          <Select value={sort} onChange={setSort} label="Orden" options={SORT} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <ActiveChips f={f} set={set} facets={fac} />
          <Segmented size="sm" className="ml-auto" value={view} onChange={setView} label="Vista" options={[["tema", "Por tema", ListTree], ["lista", "Lista", LayoutList]]} />
        </div>
      </div>

      {d.emotions?.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">Emociones que predominan:
          {d.emotions.map((e) => <Tag key={e.emotion} tone="violet">{cap(e.emotion)} · {e.count}</Tag>)}
        </div>
      )}
      {few && <Callout label="Pocas menciones">Con menos de 5 menciones el tono no es concluyente: léelas una por una.</Callout>}
      <div className={cx("mt-4 transition-opacity", loading && "opacity-50")}>
        {d.mentions === 0 ? <Empty>No hay menciones con estos filtros.</Empty> : view === "tema" ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {d.groups.map((g) => (
              <section key={g.category} className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="text-[15px] font-semibold text-slate-900">{cap(g.category)}</h3>
                  <span className="shrink-0 text-xs tabular-nums text-slate-500">{fmtNum(g.mentions)} menc. · <span className="text-rose-700">{g.negative_pct} % neg.</span></span>
                </div>
                <div className="mt-2"><ToneBar neg={g.negative_pct} pos={g.positive_pct} /></div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {Object.entries(g.kinds).sort((a, b) => b[1] - a[1]).map(([k, n]) => (
                    <Tag key={k} onClick={() => { set({ ...f, category: g.category, kind: k }); setView("lista"); }} title={`Ver solo ${KIND[k]?.[0].toLowerCase()} de este tema`}>{n} {KIND[k]?.[0].toLowerCase()}</Tag>
                  ))}
                  {g.topics.map((t) => <Tag key={t.topic} tone="violet" onClick={() => { set({ ...f, category: g.category, topic: t.topic }); setView("lista"); }}>{t.topic} · {t.count}</Tag>)}
                </div>
                <ul className="mt-1 divide-y divide-slate-100">{g.items.map((r) => <MiniItem key={r.id} r={r} />)}</ul>
                {g.mentions > g.items.length && (
                  <button type="button" onClick={() => { set({ ...f, category: g.category }); setView("lista"); }}
                    className="mt-1 text-[13px] font-semibold text-brand-700 hover:underline">Ver las {fmtNum(g.mentions)} de este tema →</button>
                )}
              </section>
            ))}
          </div>
        ) : (
          <div className="grid gap-2.5">
            <p className="text-xs text-slate-500">Mostrando {fmtNum(Math.min(d.items.length, d.mentions))} de {fmtNum(d.mentions)}{filtered && " con estos filtros"}.</p>
            {d.items.map((r) => <FeedItem key={r.id} r={r} showCandidate />)}
            {d.mentions > d.items.length && (
              <button type="button" onClick={() => setLimit(limit + PAGE)} disabled={loading}
                className="justify-self-center rounded-xl bg-brand-50 px-4 py-2 text-[13px] font-semibold text-brand-700 hover:bg-brand-100 disabled:opacity-60">
                {loading ? "Cargando…" : `Mostrar ${Math.min(PAGE, d.mentions - d.items.length)} más`}
              </button>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
