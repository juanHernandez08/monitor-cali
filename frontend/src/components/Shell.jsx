import { useEffect, useState } from "react";
import {
  BarChart3, Building2, FileText, History, LayoutDashboard, Menu, Newspaper, RefreshCw, Share2, Users, X, Radio, Target,
} from "lucide-react";
import { PERIODS, useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { ago } from "../lib/format";
import { getJSON, notify, post } from "../lib/api";
import { Button, Segmented, Select, cx } from "./ui";

export const NAV = [
  { id: "resumen", label: "Resumen", icon: LayoutDashboard, title: "Resumen", sub: "Lo esencial: cómo va Carlos frente a sus rivales" },
  { id: "candidatos", label: "Candidatos", icon: Users, title: "Candidatos y concejales", sub: "Quién habla más, cómo les va y qué emoción transmiten" },
  { id: "publicaciones", label: "Publicaciones", icon: Newspaper, title: "Publicaciones", sub: "Prensa, redes sociales y YouTube, una por una" },
  { id: "meta", label: "Meta y redes", icon: Share2, title: "Meta y redes", sub: "Alcance, reacción de la audiencia y qué funciona en redes" },
  { id: "analisis", label: "Análisis en gráficas", icon: BarChart3, title: "Análisis en gráficas", sub: "Alcance, percepción y temas con lectura en palabras" },
  { id: "ciudad", label: "Ciudad", icon: Building2, title: "Ciudad", sub: "De qué habla Cali y cómo lo siente la gente" },
  { id: "historico", label: "Histórico", icon: History, title: "Histórico", sub: "Cali de 2008 a hoy, alcaldías y cambios de conversación" },
  { id: "agenda", label: "Agenda", icon: Target, title: "Agenda", sub: "Qué conviene decir, y qué no" },
  { id: "reporte", label: "Reporte", icon: FileText, title: "Reporte diario", sub: "Se genera solo de lunes a viernes en la mañana" },
];

function Brand() {
  return (
    <div className="flex items-center gap-3 px-2">
      <div className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-700 text-lg font-extrabold text-white shadow-glow ring-1 ring-white/20">M</div>
      <div className="leading-tight">
        <div className="text-[15px] font-bold tracking-tight text-white">Monitor Cali</div>
        <div className="text-[11px] font-medium text-blue-200/70">Alcaldía 2027</div>
      </div>
    </div>
  );
}

function Sidebar({ open, onClose }) {
  const { route, go } = useApp();
  const health = useApi("/health");
  return (
    <>
      <div onClick={onClose} className={cx("fixed inset-0 z-30 bg-slate-950/50 backdrop-blur-sm transition lg:hidden", open ? "opacity-100" : "pointer-events-none opacity-0")} />
      <aside className={cx(
        "fixed inset-y-0 left-0 z-40 flex w-[272px] flex-col gap-5 overflow-y-auto bg-gradient-to-b from-navy-800 via-navy-900 to-navy-950 p-4 transition-transform duration-300 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0",
        open ? "translate-x-0 shadow-2xl" : "-translate-x-full")}>
        <div className="flex items-center justify-between pt-1">
          <Brand />
          <button type="button" aria-label="Cerrar menú" onClick={onClose} className="rounded-lg p-2 text-blue-100 hover:bg-white/10 lg:hidden"><X className="size-5" /></button>
        </div>
        <nav aria-label="Secciones del monitor" className="flex flex-1 flex-col gap-1">
          {NAV.map(({ id, label, icon: Icon }) => {
            const on = route.tab === id;
            return (
              <button key={id} type="button" onClick={() => { go(id); onClose(); }} aria-current={on ? "page" : undefined}
                className={cx("group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[13.5px] font-medium transition",
                  on ? "bg-gradient-to-r from-brand-500/90 to-brand-600/70 text-white shadow-glow" : "text-blue-100/70 hover:bg-white/[0.06] hover:text-white")}>
                <Icon className={cx("size-[18px] shrink-0 transition", on ? "text-white" : "text-blue-200/60 group-hover:text-white")} strokeWidth={2} />
                <span className="truncate">{label}</span>
                {on && <span className="absolute -left-4 h-6 w-1 rounded-r-full bg-brand-300" />}
              </button>
            );
          })}
        </nav>
        <div className="rounded-2xl bg-white/[0.06] p-4 ring-1 ring-white/10">
          <div className="flex items-center gap-2.5 text-[13px] font-semibold text-white">
            <span className="size-2 animate-pulse-ring rounded-full bg-emerald-400" />Captura en vivo
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-blue-100/60">
            Prensa, YouTube, Instagram, Facebook y X. Se actualiza sola cada 15 min.
          </p>
          <div className="mt-2 text-[11px] font-medium text-blue-200/50">Última captura: {health.data ? ago(health.data.last_run) : "…"}</div>
        </div>
      </aside>
    </>
  );
}

function Header({ onMenu }) {
  const { route, days, setDays, refresh } = useApp();
  const meta = NAV.find((n) => n.id === route.tab) || { title: "Perfil", sub: "Todo lo recopilado de esta persona" };
  const health = useApi("/health");
  const [busy, setBusy] = useState(false);

  async function onRefresh() {
    setBusy(true);
    const clickedAt = Date.now();
    try {
      const r = await post("/api/refresh");
      if (r.status === 429) { const d = await r.json(); notify(`La captura no se relanzó: ${d.reason || "ya hay una en curso"}.`); }
      else if (!r.ok) { notify("No se pudo iniciar la actualización.", "error"); return; }
      else {
        // Consulta /health hasta ver una corrida terminada después del clic (90 s como salvavidas).
        const deadline = Date.now() + 90000;
        while (Date.now() < deadline) {
          await new Promise((res) => setTimeout(res, 1500));
          const s = await getJSON("/health");
          if (s.last_run && new Date(s.last_run + "Z").getTime() > clickedAt) break;
        }
      }
      refresh();
    } catch { notify("La actualización falló; revisa la conexión.", "error"); }
    finally { setBusy(false); }
  }

  const showPeriod = route.tab !== "reporte";
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/75 backdrop-blur-xl">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-8">
        <button type="button" aria-label="Abrir menú" onClick={onMenu} className="-ml-1 rounded-xl p-2 text-slate-600 hover:bg-slate-100 lg:hidden"><Menu className="size-5" /></button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-bold tracking-tight text-slate-900 sm:text-xl">{meta.title}</h1>
          <p className="hidden truncate text-[13px] text-slate-500 sm:block">{meta.sub}</p>
        </div>
        <div className="flex w-full shrink-0 items-center justify-between gap-2.5 sm:w-auto sm:justify-end">
          <span className="hidden items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600 2xl:inline-flex">
            <Radio className="size-3.5 text-emerald-500" />Actualizado {health.data ? ago(health.data.last_run) : "…"}
          </span>
          {showPeriod && (
            <>
              <div className="hidden xl:block"><Segmented label="Período" size="sm" value={days} onChange={setDays} options={PERIODS.map(([d, l]) => [d, l])} /></div>
              <div className="xl:hidden"><Select label="Período" value={String(days)} onChange={(v) => setDays(Number(v))}
                options={PERIODS.map(([d, l]) => [String(d), d === 1 ? "Últimas 24 h" : `Últimos ${l}`])} /></div>
            </>
          )}
          <Button onClick={onRefresh} loading={busy} icon={RefreshCw} className="px-3.5">
            {busy ? "Actualizando…" : "Actualizar ahora"}
          </Button>
        </div>
      </div>
    </header>
  );
}

function StatusFooter() {
  const { data: s } = useApi("/health");
  const { data: b } = useApi("/api/budget");
  if (!s) return null;
  return (
    <footer aria-live="polite" className="mt-8 border-t border-slate-200/70 px-1 pt-5 text-xs leading-relaxed text-slate-500">
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <span><b className="font-semibold text-slate-700">{s.total_mentions}</b> menciones capturadas</span>
        <span><b className="font-semibold text-slate-700">{s.scored}</b> clasificadas</span>
        <span><b className="font-semibold text-slate-700">{s.pending}</b> pendientes</span>
        <span><b className="font-semibold text-slate-700">{s.discarded}</b> descartadas (homónimos / ajenas)</span>
      </div>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
        {s.sources.filter((x) => x.type !== "REDDIT").map((x) => (
          <span key={x.name}>{x.name}: {x.total}{x.error ? <span className="ml-1 text-rose-600" title={x.error}>⚠</span> : null}</span>
        ))}
      </div>
      {b && b.used != null && (
        <div className="mt-1">
          Apify (redes): ${b.used.toFixed(2)} gastados de ${b.ceiling.toFixed(2)} del ciclo ·{" "}
          {b.ok ? `$${b.available.toFixed(2)} disponibles hasta el ${b.cycle_end} (hoy máx. $${b.job_budget.toFixed(2)})`
            : <span className="text-rose-600">captura de redes en pausa: {b.reason}</span>}
        </div>
      )}
    </footer>
  );
}

export function Shell({ children }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only z-[100] rounded-lg bg-slate-900 px-4 py-2 text-white focus:not-sr-only focus:absolute focus:left-2 focus:top-2">Saltar al contenido</a>
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header onMenu={() => setOpen(true)} />
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1400px] flex-1 px-4 pb-10 pt-5 outline-none sm:px-8 sm:pt-6">
          {children}
          <StatusFooter />
        </main>
      </div>
    </div>
  );
}
