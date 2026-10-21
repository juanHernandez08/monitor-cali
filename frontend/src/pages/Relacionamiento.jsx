import { useState } from "react";
import { ClipboardCheck, Gauge as GaugeIcon, Grid3x3, HeartHandshake, MapPinned, Orbit, Trash2, Users } from "lucide-react";
import { useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { clearCache } from "../lib/cache";
import { del, notify, post } from "../lib/api";
import { CARLOS, cap, fmtNum } from "../lib/format";
import { CRITICAL, GOOD } from "../lib/palette";
import { Button, Callout, Empty, Intro, Kpi, KpiGrid, Panel, PanelSkeleton, Reading, Select, Tag, cx } from "../components/ui";
import { HBar } from "../charts/Chart";
import { NUCLEOS } from "./Mapa";

/* Anillos de cercanía: del más cercano al más lejano. Diverge de verde (cerca) a rojo (lejos) con gris al centro. */
const RINGS = [
  { id: "simpatizantes", label: "Simpatizantes", color: "#1f8a5b", desc: "2+ opiniones, todas a favor" },
  { id: "cercanos", label: "Cercanos", color: "#7cc4a0", desc: "más a favor que en contra" },
  { id: "indecisos", label: "Indecisos", color: "#b9bec9", desc: "tibios o empatados" },
  { id: "críticos", label: "Críticos", color: "#ec9a8f", desc: "más en contra que a favor" },
  { id: "opositores", label: "Opositores", color: "#b8372b", desc: "2+ opiniones, casi todas en contra" },
];
const SOURCE_LABEL = { prensa: "Prensa", social: "Instagram / Facebook / X", youtube: "YouTube", reddit: "Reddit" };

function NpsValue({ r, big }) {
  if (!r || r.nps == null) return <span className="text-slate-400">—</span>;
  return (
    <span className={cx("font-bold tabular-nums", big ? "text-2xl" : "text-sm", r.nps >= 0 ? "text-emerald-700" : "text-rose-700")}>
      {r.nps > 0 ? "+" : ""}{r.nps}
      {!r.conclusive && <span className="ml-1 align-middle text-[10px] font-semibold uppercase text-amber-600">pocas</span>}
    </span>
  );
}

function NpsSplit({ r }) {
  if (!r?.n) return null;
  return (
    <div className="flex h-2 w-full overflow-hidden rounded-full bg-slate-100" title={`${r.promoters_pct} % promotores · ${r.passives_pct} % pasivos · ${r.detractors_pct} % detractores`}>
      <span style={{ width: `${r.promoters_pct}%`, background: GOOD }} />
      <span style={{ width: `${r.passives_pct}%`, background: "#c9ccd3" }} />
      <span style={{ width: `${r.detractors_pct}%`, background: CRITICAL }} />
    </div>
  );
}

/* Círculos concéntricos: centro = Carlos; cada anillo hacia afuera, más lejos de Carlos. */
function Circles({ rings, own, total }) {
  const size = 360, c = size / 2, step = 30, inner = 34;
  return (
    <div className="grid items-center gap-5 md:grid-cols-[minmax(0,360px)_1fr]">
      <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto w-full max-w-[360px]" role="img" aria-label="Círculos de cercanía">
        {[...RINGS].reverse().map((ring, i) => {
          const idx = RINGS.length - 1 - i;
          const r = inner + step * (idx + 1);
          const row = rings.find((x) => x.ring === ring.id);
          return (
            <g key={ring.id}>
              <circle cx={c} cy={c} r={r} fill={ring.color} fillOpacity={row?.accounts ? 0.9 : 0.25} stroke="#fff" strokeWidth={3} />
              <text x={c} y={c - r + step / 2 + 4} textAnchor="middle" className="fill-white text-[13px] font-bold" style={{ paintOrder: "stroke", stroke: "rgba(0,0,0,.25)", strokeWidth: 2 }}>
                {row?.accounts ?? 0}
              </text>
            </g>
          );
        })}
        <circle cx={c} cy={c} r={inner} fill="#1d2b4f" stroke="#fff" strokeWidth={3} />
        <text x={c} y={c} textAnchor="middle" dominantBaseline="central" className="fill-white text-[13px] font-bold">Carlos</text>
      </svg>
      <ul className="grid gap-2">
        {RINGS.map((ring) => {
          const row = rings.find((x) => x.ring === ring.id) || { accounts: 0, pct: 0, opinions: 0 };
          return (
            <li key={ring.id} className="grid grid-cols-[14px_1fr_auto] items-center gap-x-3 rounded-xl border border-slate-200 bg-white px-3 py-2">
              <span className="row-span-2 size-3.5 rounded-full" style={{ background: ring.color }} />
              <b className="text-sm text-slate-900">{ring.label}</b>
              <span className="row-span-2 whitespace-nowrap text-right text-sm tabular-nums"><b>{fmtNum(row.accounts)}</b> <span className="text-xs text-slate-500">({row.pct} %)</span></span>
              <span className="text-xs leading-tight text-slate-500">{ring.desc}</span>
            </li>
          );
        })}
        <li className="px-1 text-xs text-slate-500">{fmtNum(total)} cuentas con al menos una opinión sobre Carlos en el período{own ? ` (sin contar ${own === 1 ? "su cuenta propia" : `sus ${own} cuentas propias`})` : ""}. Solo se muestran totales: el monitor no lista ni perfila a las personas.</li>
      </ul>
    </div>
  );
}

function Matrix({ rows }) {
  if (!rows.length) return <Empty>Sin cuentas con opinión en el período.</Empty>;
  const max = Math.max(1, ...rows.flatMap((r) => RINGS.map((x) => r[x.id])));
  return (
    <div className="scroll-thin overflow-x-auto">
      <table className="w-full min-w-[560px] border-separate border-spacing-1 text-sm">
        <thead>
          <tr><th className="px-2 text-left text-xs font-semibold text-slate-500">Esfera</th>
            {RINGS.map((x) => <th key={x.id} className="px-2 text-xs font-semibold" style={{ color: x.color }}>{x.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.esfera}>
              <td className="px-2 py-1 font-medium text-slate-800">{cap(r.esfera)}</td>
              {RINGS.map((x) => (
                <td key={x.id} className="rounded-md px-2 py-1 text-center tabular-nums"
                  style={{ background: r[x.id] ? `color-mix(in srgb, ${x.color} ${Math.round(15 + (r[x.id] / max) * 70)}%, white)` : "#f5f6f8",
                    color: r[x.id] / max > 0.55 ? "#fff" : "#1d2330" }}>{r[x.id] || "·"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const SCOPES = [["cali", "Toda Cali"], ...NUCLEOS.map((n) => [`nucleo:${n.id}`, n.name]),
  ...Array.from({ length: 22 }, (_, i) => [`comuna:${String(i + 1).padStart(2, "0")}`, `Comuna ${i + 1}`])];
const scopeName = (s) => SCOPES.find(([v]) => v === s)?.[1] || s;

function SurveyForm({ onSaved }) {
  const today = new Date().toISOString().slice(0, 10);
  const [f, setF] = useState({ date: today, scope: "cali", promoters: "", passives: "", detractors: "", source: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target ? e.target.value : e });
  const n = ["promoters", "passives", "detractors"].reduce((a, k) => a + (parseInt(f[k], 10) || 0), 0);
  const preview = n ? Math.round(((parseInt(f.promoters, 10) || 0) - (parseInt(f.detractors, 10) || 0)) / n * 100) : null;
  async function save() {
    setBusy(true);
    try {
      const r = await post("/api/nps/survey", f);
      const d = await r.json();
      if (!r.ok) { notify(d.error || "No se pudo guardar la medición.", "error"); return; }
      notify(`Medición guardada: NPS ${d.nps > 0 ? "+" : ""}${d.nps} sobre ${d.n} respuestas.`);
      setF({ ...f, promoters: "", passives: "", detractors: "", notes: "" });
      onSaved();
    } finally { setBusy(false); }
  }
  const input = "h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-[13px] text-slate-800 shadow-sm outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-100";
  const lab = "grid gap-1 text-xs font-semibold text-slate-500";
  return (
    <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className={lab}>Fecha del trabajo de campo<input type="date" className={input} value={f.date} onChange={set("date")} /></label>
        <label className={lab}>Alcance<Select value={f.scope} onChange={set("scope")} options={SCOPES} label="Alcance" /></label>
        <label className={lab}>Fuente o método<input className={input} value={f.source} onChange={set("source")} placeholder="p. ej. encuesta telefónica" maxLength={120} /></label>
        <label className={lab}>Notas<input className={input} value={f.notes} onChange={set("notes")} placeholder="opcional" maxLength={500} /></label>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className={lab}>Promotores (respondieron 9 o 10)<input type="number" min="0" className={input} value={f.promoters} onChange={set("promoters")} /></label>
        <label className={lab}>Pasivos (7 u 8)<input type="number" min="0" className={input} value={f.passives} onChange={set("passives")} /></label>
        <label className={lab}>Detractores (0 a 6)<input type="number" min="0" className={input} value={f.detractors} onChange={set("detractors")} /></label>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-[13px] text-slate-600">{n ? <>NPS de esta medición: <b>{preview > 0 ? "+" : ""}{preview}</b> sobre {fmtNum(n)} respuestas{n < 100 && <span className="text-amber-700"> · menos de 100 respuestas: muy ruidoso</span>}</> : "Solo se guardan los totales, nunca respuestas individuales."}</span>
        <Button icon={ClipboardCheck} loading={busy} disabled={!n} onClick={save}>Guardar medición</Button>
      </div>
    </div>
  );
}

function Survey({ rows, digital, refresh }) {
  const latestCali = rows.find((r) => r.scope === "cali");
  async function remove(id) {
    if (!window.confirm("¿Borrar esta medición de encuesta?")) return;
    const r = await del(`/api/nps/survey/${id}`);
    if (!r.ok) notify("No se pudo borrar la medición.", "error");
    refresh();
  }
  return (
    <Panel icon={ClipboardCheck} tone="violet" title="NPS de encuesta"
      hint="La pregunta clásica: «De 0 a 10, ¿qué tan probable es que le recomiende a un amigo votar por Carlos Arias?». La campaña carga aquí los totales de cada medición; el monitor los compara con el NPS digital.">
      {latestCali && digital && (
        <Reading>
          Última encuesta en toda Cali ({latestCali.date}): <b>NPS {latestCali.nps > 0 ? "+" : ""}{latestCali.nps}</b> sobre {fmtNum(latestCali.n)} respuestas.
          El NPS digital de Carlos en el período es <b>{digital.nps > 0 ? "+" : ""}{digital.nps ?? "—"}</b>.
          {digital.nps != null && Math.abs(latestCali.nps - digital.nps) >= 20 ? " La diferencia es grande: quien comenta en redes no es una muestra de toda la ciudad." : " Van en la misma línea."}
        </Reading>
      )}
      <SurveyForm onSaved={refresh} />
      <div className="mt-4 grid gap-2">
        {rows.length ? rows.map((r) => (
          <div key={r.id} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 sm:grid-cols-[110px_1fr_150px_auto]">
            <span className="text-sm font-semibold text-slate-800">{r.date}</span>
            <span className="text-sm text-slate-600 sm:order-none">{scopeName(r.scope)}{r.source && <span className="text-xs text-slate-400"> · {r.source}</span>}</span>
            <span className="col-span-2 sm:col-span-1"><NpsSplit r={r} /><span className="text-xs text-slate-500">{fmtNum(r.n)} respuestas</span></span>
            <span className="flex items-center gap-2"><NpsValue r={r} />
              <button type="button" onClick={() => remove(r.id)} className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600" aria-label="Borrar medición"><Trash2 className="size-4" /></button></span>
          </div>
        )) : <Empty icon={ClipboardCheck}>Aún no hay mediciones de encuesta cargadas.</Empty>}
      </div>
    </Panel>
  );
}

export default function Relacionamiento() {
  const { days, refresh } = useApp();
  const win = Math.max(days, 30);
  const [cid, setCid] = useState("");
  const npsApi = useApi(`/api/nps?days=${win}`);
  const relApi = useApi(`/api/relationship?days=${win}${cid ? `&candidate_id=${cid}` : ""}`);
  const n = npsApi.data, r = relApi.data;
  const cands = n?.rows || [];
  const carlosNps = cands.find((x) => x.candidate === CARLOS);
  const reload = () => { clearCache(); refresh(); };

  return (
    <div className="grid gap-5">
      <Intro icon={HeartHandshake} title="Esferas de relacionamiento y NPS">
        <p><b>Esferas por sector</b>: desde qué sector de la ciudad habla quien escribe (ciudadanía, JAC, gremios, academia, iglesias, medios, actores políticos…). <b>Esferas por cercanía</b>: cada cuenta que opina se ubica en un anillo según todo lo que ha dicho del candidato; solo se muestran totales, nunca nombres. <b>NPS digital</b>: % de promotores (apoyo fuerte) menos % de detractores (cualquier mención en contra), leído de lo que la gente escribe. No reemplaza al <b>NPS de encuesta</b>, que la campaña carga abajo.</p>
        <p className="mt-2 rounded-lg bg-white/10 px-3 py-2 text-white">Ventana: últimos {win} días{days < 30 && " (mínimo 30: con menos días casi no hay opiniones suficientes)"}.</p>
      </Intro>

      {!n ? <PanelSkeleton h="h-40" /> : (
        <KpiGrid>
          <Kpi icon={GaugeIcon} label="NPS digital de Carlos" value={carlosNps?.nps ?? 0} foot={carlosNps?.n ? `IC 95 %: ${carlosNps.low} a ${carlosNps.high} · ${carlosNps.n} opiniones` : "sin opiniones en el período"} tone={carlosNps?.nps < 0 ? "neg" : "default"} />
          <Kpi delay={60} icon={Users} iconTone="green" label="Promotores" value={carlosNps?.promoters_pct ?? 0} suffix=" %" foot={`${carlosNps?.promoters ?? 0} opiniones de apoyo fuerte`} />
          <Kpi delay={120} icon={Users} iconTone="red" label="Detractores" value={carlosNps?.detractors_pct ?? 0} suffix=" %" foot={`${carlosNps?.detractors ?? 0} opiniones en contra`} />
          <Kpi delay={180} icon={Orbit} label="Cuentas en sus círculos" value={r?.accounts ?? 0} foot="personas con al menos una opinión" />
        </KpiGrid>
      )}

      <Panel icon={GaugeIcon} title="NPS digital por candidato" hint={`% promotores − % detractores, de −100 a +100. Con menos de ${n?.min_n || 30} opiniones se marca «pocas»: no es concluyente.`}>
        {!n ? <PanelSkeleton h="h-64" /> : cands.filter((x) => x.n).length ? (
          <>
            <HBar categories={cands.filter((x) => x.n).map((x) => `${x.candidate} (${x.n})`)} data={cands.filter((x) => x.n).map((x) => x.nps)}
              colors={cands.filter((x) => x.n).map((x) => (x.nps >= 0 ? GOOD : CRITICAL))} labelFmt={(v) => (v > 0 ? "+" : "") + v} label="NPS digital por candidato" />
            <Callout label="Cómo se calcula">Promotor = mención positiva con fuerza (puntaje ≥ 0,6). Detractor = cualquier mención negativa. Pasivo = apoyo tibio o neutral con emoción. No cuentan las publicaciones del propio candidato, las notas puramente informativas ni las menciones de paso.</Callout>
          </>
        ) : <Empty>Sin opiniones en el período.</Empty>}
      </Panel>

      <Panel icon={Orbit} tone="green" title={`Círculos de cercanía${r?.candidate ? ` · ${r.candidate}` : ""}`}
        hint="Cada cuenta se ubica según todas sus opiniones sobre el candidato en el período. Los medios no entran: no son personas que se acercan o se alejan."
        actions={<Select value={cid} onChange={setCid} label="Candidato" options={[["", "Carlos Arias"], ...cands.filter((x) => x.candidate !== CARLOS).map((x) => [String(x.candidate_id), x.candidate])]} />}>
        {!r ? <PanelSkeleton h="h-80" /> : r.error ? <Empty>{r.error}</Empty> : <Circles rings={r.rings} own={r.own_accounts} total={r.accounts} />}
      </Panel>

      {r && !r.error && (
        <>
          <Panel icon={Users} tone="brand" title="Esferas por sector" hint="Desde qué sector habla quien escribe (o el actor principal de una nota). Tono de esas menciones y su NPS digital.">
            {r.pending_esfera > 0 && (
              <Callout label="Aún clasificando">{fmtNum(r.pending_esfera)} de {fmtNum(r.mentions)} menciones del período todavía no tienen esfera: la IA del PC las está releyendo en su tiempo libre y esta sección se completa sola.</Callout>
            )}
            {r.spheres.length ? (
              <div className="grid gap-2">
                {r.spheres.map((s) => (
                  <div key={s.esfera} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 md:grid-cols-[220px_1fr_150px_70px]">
                    <span className="text-sm font-semibold text-slate-900">{cap(s.esfera)}</span>
                    <span className="text-right text-xs tabular-nums text-slate-500 md:order-last md:text-right"><NpsValue r={s.nps} /></span>
                    <span className="col-span-2 flex flex-wrap gap-1 md:col-span-1">{s.categories.map((c) => <Tag key={c.category}>{c.category} · {c.count}</Tag>)}</span>
                    <span className="col-span-2 text-xs text-slate-500 md:col-span-1">{fmtNum(s.mentions)} menc. · <span className="text-emerald-700">{s.positive_pct} %</span> / <span className="text-rose-700">{s.negative_pct} %</span></span>
                  </div>
                ))}
              </div>
            ) : <Empty>Las esferas aparecen a medida que la IA las clasifica.</Empty>}
          </Panel>

          <Panel icon={Grid3x3} title="Sector × cercanía" hint="Cuántas cuentas de cada esfera están en cada anillo. Muestra, por ejemplo, si los líderes comunitarios están entre los simpatizantes o entre los críticos.">
            <Matrix rows={r.matrix} />
          </Panel>

          <div className="grid items-start gap-5 lg:grid-cols-2">
            <Panel icon={MapPinned} tone="amber" title="NPS digital por núcleo territorial" hint="Opiniones sobre el candidato que además nombran una zona de ese núcleo.">
              {r.by_nucleo.length ? (
                <ul className="grid gap-2">{r.by_nucleo.map((x) => {
                  const color = NUCLEOS.find((k) => k.id === x.nucleo)?.color;
                  return (
                    <li key={x.nucleo} className="grid grid-cols-[14px_1fr_auto] items-center gap-x-3 gap-y-1 rounded-xl border border-slate-200 bg-white px-3 py-2">
                      <span className="size-3.5 rounded" style={{ background: color }} />
                      <span className="text-sm font-medium text-slate-800">{x.name} <span className="text-xs text-slate-400">({x.n})</span></span>
                      <NpsValue r={x} />
                      <span className="col-start-2 col-end-4"><NpsSplit r={x} /></span>
                    </li>
                  );
                })}</ul>
              ) : <Empty icon={MapPinned}>Pocas opiniones del candidato nombran una zona: crece a medida que la IA relee el lugar de cada mención.</Empty>}
            </Panel>
            <Panel icon={GaugeIcon} title="NPS digital por tipo de fuente" hint="La prensa y las redes no hablan igual: compararlas evita leer un solo canal como si fuera toda la conversación.">
              {r.by_source.length ? (
                <ul className="grid gap-2">{r.by_source.map((x) => (
                  <li key={x.source} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <span className="text-sm font-medium text-slate-800">{SOURCE_LABEL[x.source] || x.source} <span className="text-xs text-slate-400">({x.n})</span></span>
                    <NpsValue r={x} /><span className="col-span-2"><NpsSplit r={x} /></span>
                  </li>
                ))}</ul>
              ) : <Empty>Sin opiniones en el período.</Empty>}
            </Panel>
          </div>
        </>
      )}

      {n && <Survey rows={n.survey} digital={carlosNps} refresh={reload} />}
    </div>
  );
}
