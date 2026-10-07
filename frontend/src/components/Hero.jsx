import { ArrowUpRight, TrendingDown, TrendingUp } from "lucide-react";
import { CARLOS, pct, scored } from "../lib/format";
import { Gauge } from "../charts/Chart";
import { Avatar, cx } from "./ui";

function Stat({ n, label, tone }) {
  return (
    <div className="rounded-xl bg-white/10 px-3.5 py-2.5 ring-1 ring-white/15 backdrop-blur-sm">
      <div className={cx("text-2xl font-bold leading-none tracking-tight", tone)}>{n}</div>
      <div className="mt-1 text-[11px] font-medium text-blue-100/70">{label}</div>
    </div>
  );
}

/* Panel destacado de un candidato: Carlos en el Resumen y cualquiera en su Perfil. */
export function Hero({ r, rivals, onOpen }) {
  const cScored = scored(r);
  const rivalsPos = rivals.reduce((a, x) => a + x.positive, 0);
  const rivalsScored = rivals.reduce((a, x) => a + scored(x), 0);
  const cPct = pct(r.positive, cScored), rPct = pct(rivalsPos, rivalsScored);
  const diff = cScored && rivalsScored ? cPct - rPct : null;
  const t = cScored || 1;
  const interactive = !!onOpen;
  const Wrapper = interactive ? "div" : "section";
  return (
    <Wrapper
      {...(interactive ? { role: "button", tabIndex: 0, onClick: onOpen, onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onOpen(); } } } : {})}
      className={cx("group relative overflow-hidden rounded-3xl bg-gradient-to-br from-navy-800 via-brand-800 to-brand-600 p-5 text-white shadow-lift ring-1 ring-white/10 sm:p-7",
        interactive && "cursor-pointer transition duration-300 hover:-translate-y-0.5 hover:shadow-2xl")}>
      <div className="pointer-events-none absolute -right-16 -top-24 size-80 rounded-full bg-brand-400/25 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 left-1/3 size-72 rounded-full bg-indigo-400/15 blur-3xl" />
      <div className="relative grid items-center gap-6 lg:grid-cols-[auto_1fr_auto]">
        <div className="flex items-center gap-4 lg:block">
          <Avatar name={r.name} src={r.avatar} size="xl" className="!ring-4 !ring-white/25" />
          <div className="lg:hidden"><HeroName r={r} /></div>
        </div>
        <div className="min-w-0">
          <div className="hidden lg:block"><HeroName r={r} /></div>
          <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-5">
            <Stat n={r.mentions} label="menciones" />
            <Stat n={r.positive} label="positivas" tone="text-emerald-300" />
            <Stat n={r.neutral} label="neutrales" tone="text-slate-200" />
            <Stat n={r.negative} label="negativas" tone="text-rose-300" />
            {r.pending ? <Stat n={r.pending} label="pendientes de análisis" tone="text-amber-200" /> : null}
          </div>
          <div className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-white/15" role="img" aria-label="Reparto de sentimiento">
            <i className="bg-emerald-400" style={{ width: `${(r.positive / t) * 100}%` }} />
            <i className="bg-slate-300" style={{ width: `${(r.neutral / t) * 100}%` }} />
            <i className="bg-rose-400" style={{ width: `${(r.negative / t) * 100}%` }} />
          </div>
          <div className="mt-2 flex gap-4 text-xs text-blue-100/70">
            <span className="inline-flex items-center gap-1.5"><i className="size-2 rounded-sm bg-emerald-400" />positivo</span>
            <span className="inline-flex items-center gap-1.5"><i className="size-2 rounded-sm bg-slate-300" />neutral</span>
            <span className="inline-flex items-center gap-1.5"><i className="size-2 rounded-sm bg-rose-400" />negativo</span>
          </div>
        </div>
        <div className="rounded-2xl bg-white p-4 text-center text-slate-900 shadow-xl lg:w-60">
          <div className="text-xs font-semibold text-slate-500">Positividad{r.name === CARLOS ? " de Carlos" : ""}</div>
          <Gauge value={cScored ? cPct : 0} />
          {diff === null ? (
            <div className="text-sm font-semibold text-slate-500">sin comparación</div>
          ) : (
            <div className={cx("inline-flex items-center gap-1 text-[15px] font-bold", diff >= 0 ? "text-emerald-600" : "text-rose-600")}>
              {diff >= 0 ? <TrendingUp className="size-4" /> : <TrendingDown className="size-4" />}
              {diff >= 0 ? "+" : ""}{diff} pts vs el resto
            </div>
          )}
          <div className="text-xs text-slate-500">({cScored ? cPct : "—"}% vs {rivalsScored ? rPct : "—"}%)</div>
        </div>
      </div>
    </Wrapper>
  );
}

function HeroName({ r }) {
  return (
    <div>
      <div className="flex items-center gap-2">
        <h2 className="text-2xl font-bold tracking-tight sm:text-[28px]">{r.name}</h2>
        {r.name === CARLOS && <span className="rounded-full bg-white/15 px-2.5 py-0.5 text-[11px] font-semibold ring-1 ring-white/20">nuestro candidato</span>}
      </div>
      <div className="mt-0.5 flex items-center gap-2 text-sm text-blue-100/80">
        {r.party || "sin partido"}
        <span className="inline-flex items-center gap-0.5 text-xs text-blue-200/70 opacity-0 transition group-hover:opacity-100">ver perfil <ArrowUpRight className="size-3.5" /></span>
      </div>
    </div>
  );
}
