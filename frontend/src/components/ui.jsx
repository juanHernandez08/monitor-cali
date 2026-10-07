import { useEffect, useRef, useState } from "react";
import { ChevronDown, Info, Lightbulb, Inbox, Loader2, Check, AlertTriangle } from "lucide-react";
import { initials, safeUrl, scored } from "../lib/format";
import { onNotify } from "../lib/api";

export const cx = (...a) => a.filter(Boolean).join(" ");

/* ---------- animación de entrada escalonada ---------- */
export function Reveal({ children, delay = 0, className }) {
  return <div className={cx("animate-fade-up", className)} style={{ animationDelay: `${Math.min(delay, 600)}ms` }}>{children}</div>;
}

/* ---------- paneles ---------- */
const TONES = {
  brand: "bg-brand-50 text-brand-600 ring-brand-100",
  green: "bg-emerald-50 text-emerald-600 ring-emerald-100",
  red: "bg-rose-50 text-rose-600 ring-rose-100",
  amber: "bg-amber-50 text-amber-600 ring-amber-100",
  violet: "bg-violet-50 text-violet-600 ring-violet-100",
  slate: "bg-slate-100 text-slate-600 ring-slate-200",
};
export function IconChip({ icon: Icon, tone = "brand", size = "md" }) {
  if (!Icon) return null;
  return (
    <span className={cx("inline-grid shrink-0 place-items-center rounded-xl ring-1", TONES[tone], size === "sm" ? "size-8" : "size-10")}>
      <Icon className={size === "sm" ? "size-4" : "size-5"} strokeWidth={2} />
    </span>
  );
}

/* Los textos de ayuda largos se pliegan: quien no los necesita no se los come, y quien sí, un clic. */
function Hint({ children }) {
  const [open, setOpen] = useState(false);
  const long = typeof children === "string" ? children.length > 150 : true;
  if (!children) return null;
  if (!long) return <p className="mt-0.5 text-[13px] leading-snug text-slate-500">{children}</p>;
  return (
    <div className="mt-0.5">
      <p className={cx("rich text-[13px] leading-snug text-slate-500", !open && "line-clamp-2")}>{children}</p>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-800">
        <Info className="size-3.5" />{open ? "Ver menos" : "Cómo leer esto"}
        <ChevronDown className={cx("size-3.5 transition-transform", open && "rotate-180")} />
      </button>
    </div>
  );
}

export function Panel({ title, hint, icon, tone, actions, children, className, bodyClass, id, flush }) {
  return (
    <section id={id} className={cx("card min-w-0 p-4 sm:p-5", className)}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
          <div className="flex min-w-0 flex-[1_1_300px] items-start gap-3">
            <IconChip icon={icon} tone={tone} size="sm" />
            <div className="min-w-0 flex-1">
              <h2 className="text-[15px] font-semibold leading-tight tracking-tight text-slate-900 sm:text-base">{title}</h2>
              <Hint>{hint}</Hint>
            </div>
          </div>
          {actions && <div className="flex max-w-full flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={cx(flush && "-mx-1", bodyClass)}>{children}</div>
    </section>
  );
}

export function SectionTitle({ children }) {
  return (
    <div className="mt-3 flex items-center gap-3">
      <h3 className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">{children}</h3>
      <div className="h-px flex-1 bg-gradient-to-r from-slate-300/70 to-transparent" />
    </div>
  );
}

export function Intro({ title, children, icon: Icon, tone = "brand" }) {
  return (
    <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-navy-800 via-brand-800 to-brand-600 p-5 text-white shadow-lift sm:p-6">
      <div className="pointer-events-none absolute -right-10 -top-16 size-56 rounded-full bg-white/10 blur-2xl" />
      <div className="relative flex items-start gap-4">
        {Icon && <span className="hidden size-11 shrink-0 place-items-center rounded-xl bg-white/15 ring-1 ring-white/25 sm:grid"><Icon className="size-5" /></span>}
        <div className="min-w-0">
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
          <div className="mt-1.5 max-w-4xl text-sm leading-relaxed text-blue-50/90 [&_b]:font-semibold [&_b]:text-white">{children}</div>
        </div>
      </div>
    </section>
  );
}

/* ---------- avisos ---------- */
export function Reading({ children, className }) {
  if (!children) return null;
  return (
    <div className={cx("rich mb-3 flex gap-3 rounded-xl border border-brand-100 bg-gradient-to-r from-brand-50 to-white px-4 py-3 text-sm leading-relaxed text-slate-700", className)}>
      <Lightbulb className="mt-0.5 size-4 shrink-0 text-brand-500" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
export function Callout({ label, children, className }) {
  return (
    <div className={cx("my-3 rounded-xl border-l-[3px] border-slate-300 bg-slate-50 px-4 py-3 text-[13px] leading-relaxed text-slate-700 [&_li]:my-1 [&_ul]:mt-1.5 [&_ul]:list-disc [&_ul]:pl-5", className)}>
      {label && <span className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-slate-500">{label}</span>}
      {children}
    </div>
  );
}
export function Empty({ children, icon: Icon = Inbox, className }) {
  return (
    <div className={cx("flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-8 text-center text-sm text-slate-500", className)}>
      <Icon className="size-6 text-slate-300" />
      <div className="max-w-md">{children}</div>
    </div>
  );
}
export function Skeleton({ className }) { return <div className={cx("skeleton", className)} />; }
export function PanelSkeleton({ h = "h-64", className }) {
  return <div className={cx("card p-5", className)}><Skeleton className="mb-4 h-5 w-48" /><Skeleton className={cx("w-full", h)} /></div>;
}
export function Loading({ rows = 3 }) {
  return <div className="grid gap-3">{Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-16 w-full" />)}</div>;
}

/* ---------- etiquetas ---------- */
const TAG = {
  neutral: "bg-slate-100 text-slate-600",
  positive: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100",
  negative: "bg-rose-50 text-rose-700 ring-1 ring-rose-100",
  pending: "bg-amber-50 text-amber-700 ring-1 ring-amber-100",
  brand: "bg-brand-50 text-brand-700 ring-1 ring-brand-100",
  violet: "bg-violet-50 text-violet-700 ring-1 ring-violet-100",
  dark: "bg-slate-900 text-white",
};
export function Tag({ tone = "neutral", children, className, title, onClick }) {
  const cls = cx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-semibold", TAG[tone] || TAG.neutral,
    onClick && "cursor-pointer transition hover:brightness-95", className);
  return onClick ? <button type="button" title={title} onClick={onClick} className={cls}>{children}</button> : <span title={title} className={cls}>{children}</span>;
}
export const sentTone = (label) => (label === "positive" ? "positive" : label === "negative" ? "negative" : "neutral");

/* ---------- controles ---------- */
export function Select({ value, onChange, options, className, label, children }) {
  return (
    <label className={cx("relative inline-flex", className)}>
      <span className="sr-only">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}
        className="h-9 w-full cursor-pointer appearance-none rounded-xl border border-slate-200 bg-white pl-3 pr-8 text-[13px] font-medium text-slate-700 shadow-sm outline-none transition hover:border-slate-300 focus:border-brand-400 focus:ring-4 focus:ring-brand-100">
        {children || options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
    </label>
  );
}

export function Segmented({ value, onChange, options, label, className, size = "md" }) {
  return (
    <div role="tablist" aria-label={label} className={cx("scroll-thin inline-flex max-w-full gap-1 overflow-x-auto rounded-xl bg-slate-200/60 p-1", className)}>
      {options.map(([v, l, Icon]) => {
        const on = v === value;
        return (
          <button key={v} role="tab" aria-selected={on} type="button" onClick={() => onChange(v)}
            className={cx("inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg font-semibold transition-all",
              size === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-1.5 text-[13px]",
              on ? "bg-white text-brand-700 shadow-sm ring-1 ring-slate-200" : "text-slate-500 hover:text-slate-800")}>
            {Icon && <Icon className="size-4" />}{l}
          </button>
        );
      })}
    </div>
  );
}

const BTN = {
  primary: "bg-gradient-to-b from-brand-500 to-brand-600 text-white shadow-sm shadow-brand-600/30 hover:from-brand-600 hover:to-brand-700 disabled:opacity-60",
  soft: "bg-brand-50 text-brand-700 hover:bg-brand-100 disabled:opacity-60",
  ghost: "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-60",
};
export function Button({ variant = "primary", loading, icon: Icon, children, className, ...rest }) {
  return (
    <button type="button" {...rest} disabled={rest.disabled || loading}
      className={cx("inline-flex h-9 items-center justify-center gap-2 rounded-xl px-4 text-[13px] font-semibold transition", BTN[variant], className)}>
      {loading ? <Loader2 className="size-4 animate-spin" /> : Icon && <Icon className="size-4" />}{children}
    </button>
  );
}

export function LinkOut({ href, children = "ver original" }) {
  const url = safeUrl(href);
  if (!url) return null;
  return <a href={url} target="_blank" rel="noopener" className="inline-flex items-center gap-1 font-medium text-brand-600 hover:text-brand-800 hover:underline">{children}<span aria-hidden>↗</span></a>;
}

/* ---------- avatar ---------- */
export function Avatar({ name, src, size = "md", className }) {
  const [broken, setBroken] = useState(false);
  const url = safeUrl(src);
  const dim = { sm: "size-10 text-sm", md: "size-14 text-lg", lg: "size-20 text-2xl", xl: "size-24 text-3xl" }[size];
  if (url && !broken) {
    return <img src={url} alt="" referrerPolicy="no-referrer" onError={() => setBroken(true)}
      className={cx("shrink-0 rounded-full bg-brand-50 object-cover ring-2 ring-white shadow-md", dim, className)} />;
  }
  return (
    <div aria-hidden="true" className={cx("grid shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-100 to-brand-200 font-bold text-brand-700 ring-2 ring-white shadow-md", dim, className)}>
      {initials(name)}
    </div>
  );
}

/* ---------- barra de sentimiento ---------- */
export function SentimentBar({ r, h = "h-2", className }) {
  const t = scored(r) || 1;
  return (
    <div className={cx("flex overflow-hidden rounded-full bg-slate-100", h, className)} role="img"
      aria-label={`${r.positive} positivas, ${r.neutral} neutrales, ${r.negative} negativas`}>
      <i className="block bg-pos transition-all" style={{ width: `${(r.positive / t) * 100}%` }} />
      <i className="block bg-neu transition-all" style={{ width: `${(r.neutral / t) * 100}%` }} />
      <i className="block bg-neg transition-all" style={{ width: `${(r.negative / t) * 100}%` }} />
    </div>
  );
}
export function SentimentLegend() {
  return (
    <div className="flex gap-3 text-xs text-slate-500">
      <span className="inline-flex items-center gap-1.5"><i className="size-2 rounded-sm bg-pos" />positivo</span>
      <span className="inline-flex items-center gap-1.5"><i className="size-2 rounded-sm bg-neu" />neutral</span>
      <span className="inline-flex items-center gap-1.5"><i className="size-2 rounded-sm bg-neg" />negativo</span>
    </div>
  );
}

/* ---------- KPIs ---------- */
export function useCountUp(target, ms = 700) {
  const [v, setV] = useState(target);
  const from = useRef(0);
  useEffect(() => {
    if (typeof target !== "number" || !Number.isFinite(target)) return undefined;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { setV(target); return undefined; }
    const start = performance.now(), a = from.current;
    let raf;
    const tick = (t) => {
      const p = Math.min(1, (t - start) / ms), e = 1 - Math.pow(1 - p, 3);
      setV(Math.round(a + (target - a) * e));
      if (p < 1) raf = requestAnimationFrame(tick); else from.current = target;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return typeof target === "number" ? v : target;
}

const KPI_TONE = { default: "text-slate-900", pos: "text-emerald-600", neg: "text-rose-600" };
export function Kpi({ label, value, suffix = "", foot, tone = "default", icon, iconTone = "brand", small, delay = 0, children }) {
  const n = useCountUp(typeof value === "number" ? value : NaN);
  const shown = typeof value === "number" ? n.toLocaleString("es-CO") : value;
  return (
    <Reveal delay={delay} className="h-full">
      <div className="card group relative h-full overflow-hidden p-4 transition duration-300 hover:-translate-y-0.5 hover:shadow-lift">
        <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-brand-500 via-brand-300 to-transparent opacity-70" />
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs font-medium text-slate-500">{label}</div>
            <div className={cx("mt-1.5 font-bold tracking-tight", small ? "line-clamp-2 text-xl leading-7" : "truncate text-[28px] leading-8", KPI_TONE[tone])}>
              {shown}{suffix}
            </div>
          </div>
          <IconChip icon={icon} tone={iconTone} size="sm" />
        </div>
        {foot && <div className="mt-2 text-xs leading-snug text-slate-500">{foot}</div>}
        {children}
      </div>
    </Reveal>
  );
}
export function KpiGrid({ children, cols = 4, className }) {
  return <div className={cx("grid grid-cols-2 gap-3", cols === 4 ? "lg:grid-cols-4" : cols === 3 ? "lg:grid-cols-3" : "", className)}>{children}</div>;
}

/* ---------- aviso flotante ---------- */
export function Toaster() {
  const [t, setT] = useState(null);
  useEffect(() => {
    let timer;
    const off = onNotify((n) => { setT(n); clearTimeout(timer); timer = setTimeout(() => setT(null), 6000); });
    return () => { off(); clearTimeout(timer); };
  }, []);
  if (!t) return null;
  const err = t.kind === "error";
  return (
    <div role="status" aria-live="polite" key={t.id}
      className={cx("fixed bottom-4 right-4 z-[90] flex max-w-[min(420px,calc(100vw-2rem))] animate-fade-up items-start gap-3 rounded-2xl px-4 py-3 text-sm text-white shadow-2xl",
        err ? "bg-rose-600" : "bg-slate-900")}>
      {err ? <AlertTriangle className="mt-0.5 size-4 shrink-0" /> : <Check className="mt-0.5 size-4 shrink-0" />}
      <span>{t.msg}</span>
    </div>
  );
}

/* Texto con HTML interno mínimo (<b>) que arman las lecturas automáticas: se escribe en JSX, no con
   innerHTML, así que lo que viene de la base nunca se interpreta como HTML. */
export const B = ({ children }) => <b>{children}</b>;
