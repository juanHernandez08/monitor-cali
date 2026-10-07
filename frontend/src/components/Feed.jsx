import { useState } from "react";
import { ChevronRight, Eye, Heart, MessageCircle, Newspaper, PlayCircle, Camera, Sparkles, Clock3, Quote as QuoteIcon, Lightbulb } from "lucide-react";
import { KIND, LABEL, SRC_LABEL, cap, clip, emotionLine, fmtDate, fmtNum, mergedSources, safeUrl, srcName, ago } from "../lib/format";
import { Empty, LinkOut, Tag, cx, sentTone } from "./ui";

/* ---------- sentimiento + tema + emoción de una mención ---------- */
export function SentBadge({ m }) {
  if (!m.label) return <Tag tone="pending"><Clock3 className="size-3" />pendiente</Tag>;
  const emo = emotionLine(m);
  return (
    <div className="grid justify-items-start gap-1 xl:justify-items-end xl:text-right">
      <Tag tone={sentTone(m.label)}>{LABEL[m.label]} {m.score}</Tag>
      {m.topic && <div className="text-[11px] font-medium text-slate-500">{m.topic}</div>}
      {emo && (
        <div className="max-w-[230px] text-[11px] leading-snug text-slate-500">
          siente: {emo.text}{emo.lever ? ` — por: ${emo.lever}` : ""}
        </div>
      )}
    </div>
  );
}

const SRC_ICON = { Prensa: Newspaper, YouTube: PlayCircle, Instagram: Camera, Facebook: Camera, X: MessageCircle };
const SRC_TONE = {
  Prensa: "bg-brand-50 text-brand-700 ring-brand-100", YouTube: "bg-orange-50 text-orange-700 ring-orange-100",
  Instagram: "bg-pink-50 text-pink-700 ring-pink-100", Facebook: "bg-emerald-50 text-emerald-700 ring-emerald-100",
  X: "bg-violet-50 text-violet-700 ring-violet-100",
};
export function SourceChip({ m, withKind = true }) {
  const name = srcName(m);
  const Icon = SRC_ICON[name] || Newspaper;
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1", SRC_TONE[name] || "bg-slate-100 text-slate-600 ring-slate-200")}>
      <Icon className="size-3" />{name}{withKind && KIND[m.kind] ? ` · ${KIND[m.kind]}` : ""}
    </span>
  );
}

function Thumb({ r }) {
  const [broken, setBroken] = useState(false);
  let host = null;
  try { host = new URL(r.url).hostname; } catch { host = null; }
  const favicon = host ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=64` : "";
  const src = safeUrl(r.thumbnail);
  const box = "grid h-20 w-full shrink-0 place-items-center overflow-hidden rounded-xl bg-gradient-to-br from-slate-100 to-slate-50 text-[11px] text-slate-400 sm:h-[84px] sm:w-28";
  if (src && !broken) return <div className={box}><img src={src} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(true)} className="size-full object-cover" /></div>;
  if (favicon) return <div className={box}><img src={favicon} alt="" loading="lazy" className="size-9 object-contain" /></div>;
  return <div className={box} aria-hidden="true">{KIND[r.kind] || ""}</div>;
}

function Metrics({ r }) {
  if (!r.likes && !r.views && !r.comments_count) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
      {r.likes ? <span className="inline-flex items-center gap-1"><Heart className="size-3.5 text-rose-400" />{fmtNum(r.likes)}</span> : null}
      {r.views ? <span className="inline-flex items-center gap-1"><Eye className="size-3.5 text-slate-400" />{fmtNum(r.views)}</span> : null}
    </div>
  );
}

/* ---------- comentarios clasificados de una publicación (despliegue) ---------- */
function CommentsSummary({ r, open, onToggle }) {
  const s = r.comments_summary;
  if (!s?.total) return null;
  const t = s.total;
  return (
    <div className="grid gap-1.5 xl:justify-items-end">
      <button type="button" onClick={onToggle} aria-expanded={open}
        className="inline-flex items-center gap-1 text-[13px] font-semibold text-brand-600 hover:text-brand-800">
        <ChevronRight className={cx("size-4 transition-transform", open && "rotate-90")} />
        {t} comentario{t === 1 ? "" : "s"}
      </button>
      <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-slate-100 sm:w-36">
        <i className="bg-pos" style={{ width: `${(s.positive / t) * 100}%` }} />
        <i className="bg-neu" style={{ width: `${(s.neutral / t) * 100}%` }} />
        <i className="bg-neg" style={{ width: `${(s.negative / t) * 100}%` }} />
      </div>
      <div className="text-[11px] text-slate-500">{s.positive} positivos · {s.neutral} neutrales · {s.negative} negativos</div>
    </div>
  );
}

export function Thread({ comments }) {
  if (!comments?.length) return <div className="text-sm text-slate-500">Sin comentarios que cumplan el filtro.</div>;
  return (
    <div className="grid gap-2">
      {comments.map((c, i) => (
        <div key={i} className="grid gap-2 rounded-xl bg-slate-50 p-3 text-[13px] sm:grid-cols-[1fr_auto]">
          <div className="min-w-0">
            <div className="text-slate-800">{c.text}</div>
            <div className="mt-1 text-xs text-slate-500">{c.author || ""}{c.published_at ? ` · ${fmtDate(c.published_at)}` : ""}
              {(c.link || c.url) ? <> · <LinkOut href={c.link || c.url} >ver</LinkOut></> : null}</div>
          </div>
          <SentBadge m={c} />
        </div>
      ))}
    </div>
  );
}

/* ---------- una fila del feed ---------- */
export function FeedItem({ r, showCandidate }) {
  const [open, setOpen] = useState(false);
  const hasComments = r.comments_summary?.total > 0;
  return (
    <article className="grid gap-3 rounded-2xl border border-slate-200/80 bg-white p-3 transition hover:border-brand-200 hover:shadow-md sm:grid-cols-[7rem_1fr] sm:gap-4 xl:grid-cols-[7rem_1fr_auto]">
      <Thumb r={r} />
      <div className="min-w-0">
        <div className="mb-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-slate-500">
          {showCandidate && r.candidate && <span className="font-semibold text-slate-800">{r.candidate}</span>}
          <SourceChip m={r} />
          <span>{fmtDate(r.published_at)}</span>
          <LinkOut href={r.url} />
        </div>
        {r.fetched_at && <div className="mb-1 text-[11px] text-slate-400">capturado {fmtDate(r.fetched_at)}</div>}
        <p className="line-clamp-3 text-sm leading-relaxed text-slate-800">{r.text}</p>
        {r.summary && (
          <div className="mt-2 flex gap-2 rounded-lg bg-slate-50 px-3 py-2 text-[13px] text-slate-700">
            <Sparkles className="mt-0.5 size-3.5 shrink-0 text-brand-500" /><span>{r.summary}</span>
          </div>
        )}
        {r.author && <div className="mt-1.5 text-xs text-slate-500">{r.author}</div>}
      </div>
      <div className="grid content-start gap-2 sm:col-start-2 xl:col-start-auto xl:min-w-[160px] xl:justify-items-end">
        {r.kind === "comments" ? <span className="text-xs text-slate-500">solo comentarios</span> : <SentBadge m={r} />}
        <Metrics r={r} />
        <CommentsSummary r={r} open={open} onToggle={() => setOpen(!open)} />
      </div>
      {hasComments && open && <div className="border-t border-dashed border-slate-200 pt-3 col-span-full"><Thread comments={r.comments} /></div>}
    </article>
  );
}

export function FeedList({ rows, showCandidate, empty = "Sin publicaciones con esos filtros." }) {
  if (!rows?.length) return <Empty>{empty}</Empty>;
  return <div className="grid gap-2.5">{rows.map((r, i) => <FeedItem key={`${r.id ?? r.url ?? i}-${i}`} r={r} showCandidate={showCandidate} />)}</div>;
}

/* ---------- publicación de redes con vista previa de comentarios sin clasificar ---------- */
export function SocialPost({ r }) {
  const [open, setOpen] = useState(false);
  const c = r.comments_preview || [];
  return (
    <article className="grid gap-3 rounded-2xl border border-slate-200/80 bg-white p-3 transition hover:border-brand-200 hover:shadow-md sm:grid-cols-[7rem_1fr] sm:gap-4 xl:grid-cols-[7rem_1fr_auto]">
      <Thumb r={r} />
      <div className="min-w-0">
        <div className="mb-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-slate-500">
          <span className="font-semibold text-slate-800">{r.candidate}</span>
          <SourceChip m={r} withKind={false} />
          <span>{fmtDate(r.published_at)}</span>
          <LinkOut href={r.url} />
        </div>
        <p className="line-clamp-3 text-sm leading-relaxed text-slate-800">{r.text}</p>
        {r.summary && (
          <div className="mt-2 flex gap-2 rounded-lg bg-slate-50 px-3 py-2 text-[13px] text-slate-700">
            <Sparkles className="mt-0.5 size-3.5 shrink-0 text-brand-500" /><span>{r.summary}</span>
          </div>
        )}
        {c.length > 0 && (
          <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
            className="mt-2 inline-flex items-center gap-1 text-[13px] font-semibold text-brand-600 hover:text-brand-800">
            <ChevronRight className={cx("size-4 transition-transform", open && "rotate-90")} />
            {c.length} comentario{c.length === 1 ? "" : "s"} recientes (vista previa, sin clasificar)
          </button>
        )}
      </div>
      <div className="grid content-start gap-2 sm:col-start-2 xl:col-start-auto xl:min-w-[170px] xl:justify-items-end">
        <SentBadge m={r} />
        <div className="flex flex-wrap items-center gap-x-3 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1"><Heart className="size-3.5 text-rose-400" />{fmtNum(r.likes)}</span>
          <span className="inline-flex items-center gap-1"><MessageCircle className="size-3.5 text-brand-400" />{fmtNum(r.comments)}</span>
          {r.views ? <span className="inline-flex items-center gap-1"><Eye className="size-3.5 text-slate-400" />{fmtNum(r.views)}</span> : null}
        </div>
        <div className="text-[11px] text-slate-400 xl:text-right">medido {ago(r.fetched_at)}: puede haber crecido desde entonces</div>
      </div>
      {open && (
        <div className="grid gap-2 border-t border-dashed border-slate-200 pt-3 col-span-full">
          {c.map((x, i) => (
            <div key={i} className="rounded-xl bg-slate-50 p-3 text-[13px]">
              <div className="text-slate-800">{x.text}</div>
              <div className="mt-1 text-xs text-slate-500">{x.author || ""}{x.date ? ` · ${fmtDate(String(x.date).replace("Z", ""))}` : ""}</div>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

/* ---------- cita textual con su fuente ---------- */
export function Quote({ m, className }) {
  const emo = emotionLine(m);
  const link = m.link || m.url;
  return (
    <figure className={cx("relative my-2 rounded-xl border border-slate-200/70 bg-slate-50/80 px-4 py-3 text-[13px]", className)}>
      <QuoteIcon className="absolute right-3 top-3 size-4 text-slate-200" />
      <blockquote className="pr-5 leading-relaxed text-slate-800">“{clip(m.text, 220)}”</blockquote>
      <figcaption className="mt-1.5 text-xs text-slate-500">
        {srcName(m)} · {m.author || ""} · {fmtDate(m.published_at)}{m.fetched_at ? ` · capturado ${fmtDate(m.fetched_at)}` : ""}
        {link ? <> · <LinkOut href={link}>ver</LinkOut></> : null}
      </figcaption>
      {emo && (
        <div className="mt-1.5 flex items-start gap-1.5 text-xs text-slate-600">
          <Lightbulb className="mt-0.5 size-3.5 shrink-0 text-amber-500" />
          <span>siente: {emo.text}{emo.lever ? ` — por: ${emo.lever}` : ""}</span>
        </div>
      )}
    </figure>
  );
}
export function Quotes({ rows }) {
  return <>{(rows || []).map((m, i) => <Quote key={i} m={m} />)}</>;
}
/* Cita simple de un reporte: texto + fuente + enlace (formato más corto). */
export function SimpleQuote({ text, source, url }) {
  return (
    <figure className="my-2 rounded-xl border border-slate-200/70 bg-slate-50/80 px-4 py-3 text-[13px]">
      <blockquote className="leading-relaxed text-slate-800">“{clip(text, 200)}”</blockquote>
      <figcaption className="mt-1 text-xs text-slate-500">{source || ""}{url ? <> · <LinkOut href={url}>ver</LinkOut></> : null}</figcaption>
    </figure>
  );
}

/* ---------- tarjeta de tema (perfil de candidato y detalle de ciudad) ---------- */
export function TopicCard({ t, id, forceOpen, onOpened }) {
  const [open, setOpen] = useState(false);
  const isOpen = open || forceOpen;
  const subtopics = (t.subtopics || []).filter((s) => s.topic !== t.topic.toLowerCase());
  // Apalancadores (qué dispara la emoción) sacados de las muestras ya traídas.
  const levers = [...new Set((t.samples || []).map((s) => s.apalancador).filter(Boolean))].slice(0, 2);
  const tone = t.positive_pct >= 60 ? "positive" : t.positive_pct <= 30 ? "negative" : "neutral";
  const n = (t.samples || []).length;
  return (
    <div id={id} className="rounded-2xl border border-slate-200/80 bg-white p-4 transition hover:shadow-md">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[15px] font-semibold capitalize text-slate-900">{t.topic}</h3>
        <div className="flex items-center gap-2 text-sm text-slate-600">{t.count} menciones <Tag tone={tone}>{t.positive_pct}% a favor</Tag></div>
      </div>
      <div className="my-2.5 flex flex-wrap gap-1.5">
        <Tag tone="positive">{t.positive} positivas</Tag><Tag>{t.neutral} neutrales</Tag><Tag tone="negative">{t.negative} negativas</Tag>
        {Object.entries(mergedSources(t.sources)).map(([label, c]) => <Tag key={label} tone="brand">{label} · {c}</Tag>)}
      </div>
      {t.dominant_emotion && (
        <div className="text-xs text-slate-600">siente, sobre todo: <b className="font-semibold text-slate-800">{t.dominant_emotion}</b>{levers.length ? ` — por: ${levers.join("; ")}` : ""}</div>
      )}
      {subtopics.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{subtopics.map((s) => <Tag key={s.topic}>{s.topic} · {s.count}</Tag>)}</div>}
      {n > 0 && (
        <button type="button" onClick={() => { setOpen(!isOpen); if (!isOpen) onOpened?.(); }} aria-expanded={isOpen}
          className="mt-3 inline-flex items-center gap-1 text-[13px] font-semibold text-brand-600 hover:text-brand-800">
          <ChevronRight className={cx("size-4 transition-transform", isOpen && "rotate-90")} />
          ver {n} comentario{n === 1 ? "" : "s"} de ejemplo
        </button>
      )}
      {isOpen && n > 0 && <div className="mt-1 border-t border-dashed border-slate-200 pt-2"><Quotes rows={t.samples} /></div>}
    </div>
  );
}

export function TopicCards({ rows, visibleCount = 5, openIdx, idPrefix }) {
  const [allState, setAll] = useState(false);
  const all = allState || (openIdx != null && openIdx >= visibleCount);
  const shown = all ? rows : rows.slice(0, visibleCount);
  if (!rows.length) return <Empty>Aún no hay suficientes menciones con tema identificado en el período.</Empty>;
  return (
    <div className="grid gap-3">
      {shown.map((t, i) => <TopicCard key={t.topic} t={t} id={`${idPrefix}-${i}`} forceOpen={openIdx === i} />)}
      {!all && rows.length > visibleCount && (
        <button type="button" onClick={() => setAll(true)} className="justify-self-start text-[13px] font-semibold text-brand-600 hover:text-brand-800">
          ▸ ver {rows.length - visibleCount} tema{rows.length - visibleCount === 1 ? "" : "s"} más
        </button>
      )}
    </div>
  );
}

export { cap, SRC_LABEL };
