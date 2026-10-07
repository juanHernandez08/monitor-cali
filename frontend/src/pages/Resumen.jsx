import { AlertTriangle, Bell, Flame, MessageSquare, Percent, TrendingDown, TrendingUp, UsersRound } from "lucide-react";
import { useApp, periodLabel } from "../lib/app";
import { useApi } from "../lib/useApi";
import { CARLOS, SRC_LABEL, ago, clip, fmtNum, pct, safeUrl, scored, srcName } from "../lib/format";
import { Avatar, Empty, Kpi, KpiGrid, LinkOut, Panel, PanelSkeleton, Reveal, SentimentBar, Skeleton, Tag } from "../components/ui";
import { Hero } from "../components/Hero";

function KpiSkeleton() {
  return <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28" />)}</div>;
}

export function RivalCard({ r, onOpen, big }) {
  return (
    <button type="button" onClick={onOpen}
      className="card group flex w-full items-center gap-3.5 p-4 text-left transition duration-300 hover:-translate-y-0.5 hover:shadow-lift">
      <Avatar name={r.name} src={r.avatar} size={big ? "md" : "sm"} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-slate-900 group-hover:text-brand-700">
          {r.name}{big && r.name === CARLOS && <Tag tone="brand" className="ml-2">nuestro candidato</Tag>}
        </div>
        <div className="min-h-4 truncate text-xs text-slate-500">{r.party || (big ? "sin partido" : "")}</div>
        <div className="mt-1.5 flex items-baseline gap-1.5">
          <span className="text-2xl font-bold leading-none tracking-tight text-slate-900">{r.mentions}</span>
          <span className="text-xs text-slate-500">menciones{r.pending ? ` · ${r.pending} pend.` : ""}</span>
        </div>
        <SentimentBar r={r} className="mt-2.5" />
      </div>
    </button>
  );
}

function DeltaFoot({ carlos }) {
  if (!carlos.previous) return "sin período anterior";
  const d = Math.round(((carlos.mentions - carlos.previous) / carlos.previous) * 100);
  const up = carlos.mentions >= carlos.previous;
  return (
    <span className="inline-flex items-center gap-1">
      {up ? <TrendingUp className="size-3.5 text-emerald-600" /> : <TrendingDown className="size-3.5 text-rose-600" />}
      <b className={up ? "text-emerald-600" : "text-rose-600"}>{Math.abs(d)}%</b> vs período anterior
    </span>
  );
}

export default function Resumen() {
  const { days, openProfile } = useApp();
  const summary = useApi(`/api/summary?days=${days}`);
  const alerts = useApi(`/api/alerts?days=${days}`);
  const strong = useApi(`/api/social/strong?days=${Math.min(days, 90)}`);
  const rows = summary.data;

  if (!rows) return <div className="grid gap-5"><KpiSkeleton /><Skeleton className="h-64 rounded-3xl" /><PanelSkeleton /></div>;
  if (!rows.length) return <Empty>Sin candidatos configurados todavía.</Empty>;

  const carlos = rows.find((r) => r.name === CARLOS) || rows[0];
  const rivals = rows.filter((r) => r !== carlos);
  const total = rows.reduce((a, r) => a + r.mentions, 0);
  const cScored = scored(carlos);
  const rivalsScored = rivals.reduce((a, r) => a + scored(r), 0);
  const rivalsPos = rivals.reduce((a, r) => a + r.positive, 0);
  const cPct = pct(carlos.positive, cScored), rPct = pct(rivalsPos, rivalsScored);
  const nAlerts = alerts.data?.length ?? 0;

  return (
    <div className="grid gap-5">
      <KpiGrid>
        <Kpi delay={0} icon={MessageSquare} label="Menciones en el período" value={total} foot={`notas, posts y comentarios · ${rows.length} candidatos`} />
        <Kpi delay={60} icon={UsersRound} label="Menciones de Carlos Arias" value={carlos.mentions} foot={<DeltaFoot carlos={carlos} />} />
        <Kpi delay={120} icon={Percent} iconTone="green" label="Positividad de Carlos Arias" value={cScored ? `${cPct}%` : "—"} tone={cPct >= 50 ? "pos" : "default"}
          foot={`rivales: ${rivalsScored ? rPct + "%" : "—"} en promedio`} />
        <Kpi delay={180} icon={Bell} iconTone={nAlerts ? "red" : "slate"} label="Alertas activas" value={nAlerts} tone={nAlerts ? "neg" : "default"}
          foot="menciones negativas (≤ −0.5) sobre Carlos" />
      </KpiGrid>

      <Reveal delay={120}><Hero r={carlos} rivals={rivals} onOpen={() => openProfile(carlos.candidate_id)} /></Reveal>

      <p className="-mb-2 px-1 text-[13px] text-slate-500">Toca a Carlos o a cualquier rival para ver todo lo recopilado de esa persona.</p>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {rivals.map((r, i) => <Reveal key={r.candidate_id} delay={200 + i * 40}><RivalCard r={r} onOpen={() => openProfile(r.candidate_id)} /></Reveal>)}
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Alertas" icon={AlertTriangle} tone="red" hint="menciones negativas fuertes sobre Carlos Arias">
          {!alerts.data ? <Skeleton className="h-24" /> : alerts.data.length ? (
            <ul className="scroll-thin max-h-80 divide-y divide-slate-100 overflow-auto">
              {alerts.data.map((m, i) => (
                <li key={i} className="py-3 text-sm">
                  <div className="flex items-start gap-2"><Tag tone="negative">{m.score}</Tag><span className="text-slate-800">{clip(m.text, 200)}</span></div>
                  <div className="mt-1 text-xs text-slate-500">{srcName(m)} · {m.author || ""} · {ago(m.published_at)}{m.url && <> · <LinkOut href={m.url}>ver</LinkOut></>}</div>
                </li>
              ))}
            </ul>
          ) : <Empty icon={Bell}>Sin menciones negativas fuertes sobre Carlos Arias en el período.</Empty>}
        </Panel>
        <Panel title="Actividad fuerte en redes" icon={Flame} tone="amber" hint="publicaciones (de cualquier candidato o concejal) muy por encima del alcance habitual de esa cuenta">
          {!strong.data ? <Skeleton className="h-24" /> : strong.data.length ? (
            <ul className="scroll-thin max-h-80 divide-y divide-slate-100 overflow-auto">
              {strong.data.map((p, i) => (
                <li key={i} className="py-3 text-sm">
                  <div className="flex items-start gap-2"><Tag tone="positive">{p.multiplier}×</Tag><span className="text-slate-800"><b>{p.candidate}</b>: {clip(p.text, 160)}</span></div>
                  <div className="mt-1 text-xs text-slate-500">{SRC_LABEL[p.platform] || p.platform} · ❤️ {fmtNum(p.likes)} · 💬 {fmtNum(p.comments)}
                    {p.views ? ` · 👁 ${fmtNum(p.views)}` : ""} · habitual: ~{fmtNum(p.baseline)} · {ago(p.published_at)}
                    {safeUrl(p.url) && <> · <LinkOut href={p.url}>ver</LinkOut></>}</div>
                </li>
              ))}
            </ul>
          ) : <Empty icon={Flame}>Sin publicaciones muy por encima de lo habitual en el período.</Empty>}
        </Panel>
      </div>
      <span className="sr-only">{periodLabel(days)}</span>
    </div>
  );
}
