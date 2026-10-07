import { useState } from "react";
import { BarChart3, Building, GitCompareArrows, History, Landmark, Lightbulb, Milestone, Scale, Target, TrendingDown, TrendingUp } from "lucide-react";
import { periodLabel, useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { cap } from "../lib/format";
import { BLUE, CRITICAL, GOOD, INK, INK_SOFT, NEUTRAL_TONE, PERIOD_FILL, RED } from "../lib/palette";
import { Empty, Intro, Kpi, KpiGrid, LinkOut, Panel, PanelSkeleton, Reading, Segmented, Skeleton, Tag, cx } from "../components/ui";
import { Chart, HBar } from "../charts/Chart";

const DOMAIN_ORDER = ["economico", "social", "seguridad", "salud", "transporte"];
const STATUS_TAG = { completado: "positive", "en curso": "pending", incompleto: "negative" };

function fmtVal(v, ind) {
  if (v == null) return "—";
  return Number(v).toLocaleString("es-CO", { minimumFractionDigits: ind.decimals, maximumFractionDigits: ind.decimals });
}
function Verdict({ v, partial }) {
  if (!v) return <span className="text-xs text-slate-400">sin dato</span>;
  return <Tag tone={v === "mejoró" ? "positive" : v === "empeoró" ? "negative" : "neutral"}>{v}{partial ? " *" : ""}</Tag>;
}
const Source = ({ s }) => <>Fuente: <LinkOut href={s.url}>{s.name}</LinkOut>{s.verify ? <> <Tag tone="pending">por verificar</Tag></> : null}</>;

/* ---------- Cali 2008 a hoy ---------- */
function Indicator({ ind, periods }) {
  const pts = ind.points;
  const x0 = Math.min(...pts.map((p) => p.year)), x1 = Math.max(...pts.map((p) => p.year), 2025);
  const options = {
    chart: { type: "line", zoom: { enabled: false } },
    series: [{ name: ind.label, data: pts.map((p) => ({ x: p.year, y: p.value })) }],
    xaxis: { type: "numeric", min: x0 - 0.5, max: x1 + 0.5, tickAmount: Math.min(12, x1 - x0 + 1), labels: { formatter: (v) => Math.round(v) } },
    yaxis: { labels: { formatter: (v) => fmtVal(v, ind) } },
    colors: [BLUE], stroke: { width: 3, curve: "straight" }, markers: { size: 4, strokeWidth: 2, strokeColors: "#fff" },
    dataLabels: { enabled: pts.length <= 12, formatter: (v) => fmtVal(v, ind), style: { colors: [INK], fontSize: "10px" }, background: { enabled: false }, offsetY: -6 },
    // Franjas por alcaldía, detrás de la línea y solo donde hay datos; etiqueta corta para que no se encimen.
    annotations: { position: "back", xaxis: periods.map((p, i) => ({ p, i })).filter(({ p }) => p.end >= x0 && p.start <= x1).map(({ p, i }) => ({
      x: Math.max(p.start - 0.5, x0 - 0.5), x2: Math.min(p.end, x1) + 0.5, fillColor: PERIOD_FILL[i], opacity: 0.9, borderColor: "transparent",
      label: { text: p.label.split(" (")[0], orientation: "horizontal", position: "top", borderWidth: 0, style: { color: INK_SOFT, background: "transparent", fontSize: "9.5px" } } })) },
    tooltip: { x: { formatter: (v) => `${v}` }, y: { formatter: (v) => `${fmtVal(v, ind)} ${ind.unit}` } },
  };
  const o = ind.overall;
  return (
    <article id={`hist-ind-${ind.id}`} className="card min-w-0 p-4 sm:p-5">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div><h2 className="text-base font-semibold text-slate-900">{ind.label}</h2>
          <div className="text-[13px] text-slate-500">{ind.unit} · {ind.better === "lower" ? "menos es mejor" : ind.better === "higher" ? "más es mejor" : "contexto"}</div></div>
        <div className="flex items-center gap-2 text-[13px] text-slate-600">{o.first_year} → {o.last_year}: <b className="text-slate-900">{fmtVal(o.first, ind)} → {fmtVal(o.last, ind)}</b> <Verdict v={o.verdict} /></div>
      </div>
      <Chart options={options} height={260} label={ind.label} />
      <div className="scroll-thin overflow-x-auto">
        <table className="my-1.5 w-full border-collapse text-[12.5px]">
          <thead><tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
            {["Alcaldía", "Recibió", "Entregó", "Cambio", "Resultado"].map((h) => <th key={h} scope="col" className="border-b border-slate-200 px-2 py-2 font-semibold">{h}</th>)}</tr></thead>
          <tbody>
            {ind.periods.map((s) => (
              <tr key={s.label} className="align-top">
                <th scope="row" className="whitespace-nowrap border-b border-slate-100 px-2 py-2 text-left font-semibold">{s.label}</th>
                <td className="border-b border-slate-100 px-2 py-2">{s.start_year ? <>{fmtVal(s.start, ind)} <span className="text-slate-400">({s.start_year}{s.start_is_inherited ? ", recibido" : ""})</span></> : "—"}</td>
                <td className="border-b border-slate-100 px-2 py-2">{s.end_year ? <>{fmtVal(s.end, ind)} <span className="text-slate-400">({s.end_year})</span></> : "—"}</td>
                <td className="border-b border-slate-100 px-2 py-2">{s.pct != null ? `${s.pct > 0 ? "+" : ""}${s.pct.toLocaleString("es-CO")}%` : "—"}</td>
                <td className="border-b border-slate-100 px-2 py-2"><Verdict v={s.verdict} partial={s.partial} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {ind.notes && <p className="mt-2 text-xs text-slate-500">{ind.notes}</p>}
      <p className="mt-1 text-xs text-slate-500">Fuentes: {ind.sources.map((s, i) => <span key={s.url}>{i > 0 && " · "}<LinkOut href={s.url}>{s.name}</LinkOut></span>)}</p>
    </article>
  );
}

function DomainView({ h, domain }) {
  const inds = h.indicators.filter((i) => i.domain === domain);
  const events = h.events.filter((e) => e.domain === domain);
  const conclusion = h.conclusions.find((c) => c.domain === domain);
  return (
    <div className="grid gap-5">
      {conclusion && <Intro icon={Lightbulb} title="Lectura del período 2008 a hoy"><p>{conclusion.text}</p></Intro>}
      {events.length > 0 && (
        <Panel icon={Milestone} tone="amber" title="Hitos">
          <ul className="grid gap-2 text-sm leading-relaxed">
            {events.map((e, i) => (
              <li key={i} className="flex gap-3"><b className="w-12 shrink-0 text-brand-700">{e.year}</b>
                <span>{e.title}. <span className="text-slate-500">{e.detail} <LinkOut href={e.source.url}>fuente</LinkOut></span></span></li>
            ))}
          </ul>
        </Panel>
      )}
      <div className="grid items-start gap-5 xl:grid-cols-2">{inds.map((ind) => <Indicator key={ind.id} ind={ind} periods={h.periods} />)}</div>
    </div>
  );
}

function Comparison({ h }) {
  const { periods, scorecard, balance, domains, methodology } = h;
  const options = {
    chart: { type: "bar", stacked: true },
    series: [{ name: "Mejoraron", data: balance.map((b) => b.improved) }, { name: "Estables", data: balance.map((b) => b.stable) }, { name: "Empeoraron", data: balance.map((b) => b.worsened) }],
    xaxis: { categories: balance.map((b) => b.label) }, colors: [GOOD, NEUTRAL_TONE, CRITICAL],
    plotOptions: { bar: { horizontal: true, borderRadius: 3, barHeight: "60%" } },
    dataLabels: { enabled: true, style: { colors: ["#fff"], fontWeight: 600 } }, legend: { position: "bottom" },
  };
  const ranked = balance.map((b) => ({ ...b, net: b.improved - b.worsened, n: b.improved + b.worsened + b.stable })).filter((b) => b.n);
  const best = [...ranked].sort((a, b) => b.net - a.net)[0], worst = [...ranked].sort((a, b) => a.net - b.net)[0];
  const cellCls = (c) => cx("px-2 py-2 text-center text-xs min-w-24 border-b border-slate-100",
    c.verdict === "mejoró" ? "bg-emerald-50 text-emerald-800" : c.verdict === "empeoró" ? "bg-rose-50 text-rose-800" : c.verdict ? "bg-slate-50" : "text-slate-400",
    c.partial && "bg-[repeating-linear-gradient(135deg,transparent_0_6px,rgba(0,0,0,.04)_6px_12px)]");
  return (
    <div className="grid gap-5">
      <Panel icon={Scale} tone="violet" title="Balance por alcaldía" hint="Indicadores que mejoraron, empeoraron o quedaron estables (±2%) entre lo que cada alcaldía recibió y lo que entregó. Solo cuentan los que se pueden medir en el período completo.">
        {best && worst && (
          <Reading>Con los indicadores medibles de punta a punta, el mejor balance es el de <b>{best.label}</b> ({best.improved} mejoraron, {best.worsened} empeoraron) y el más negativo, el de <b>{worst.label}</b> ({worst.improved} contra {worst.worsened}), que coincide con la pandemia y el paro nacional. La alcaldía en curso se mide solo hasta el último dato cerrado (2025). El balance cuenta indicadores, no los pondera: una mejora en homicidios pesa lo mismo que una en empresas registradas.</Reading>
        )}
        <Chart options={options} height={420} label="Balance por alcaldía" />
      </Panel>
      <Panel icon={GitCompareArrows} title="Tablero comparativo" hint="Cambio de cada indicador en cada alcaldía. * = ventana parcial (falta el dato de inicio o de cierre): sirve como referencia, no para comparar alcaldías.">
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full border-collapse text-[12.5px]">
            <thead><tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
              <th scope="col" className="border-b border-slate-200 px-2 py-2 font-semibold">Indicador</th>
              {periods.map((p) => <th key={p.label} scope="col" className="border-b border-slate-200 px-2 py-2 text-center font-semibold">{p.label}</th>)}</tr></thead>
            <tbody>
              {DOMAIN_ORDER.map((dom) => {
                const rows = scorecard.filter((r) => r.domain === dom);
                if (!rows.length) return null;
                return [
                  <tr key={dom}><th colSpan={periods.length + 1} scope="rowgroup" className="bg-slate-100 px-2 py-1.5 text-left text-[11px] font-bold uppercase tracking-wider text-slate-500">{domains.find((d) => d.id === dom).label}</th></tr>,
                  ...rows.map((r) => (
                    <tr key={dom + r.label}>
                      <th scope="row" className="whitespace-nowrap border-b border-slate-100 px-2 py-2 text-left font-semibold">{r.label}</th>
                      {r.cells.map((c, i) => (
                        <td key={i} className={cellCls(c)}>
                          {c.verdict ? <>{c.verdict}{c.pct != null && <><br /><span className="text-[11px] text-slate-500">{c.pct > 0 ? "+" : ""}{c.pct.toLocaleString("es-CO")}%</span></>}{c.partial ? " *" : ""}</> : "sin dato"}
                        </td>
                      ))}
                    </tr>
                  )),
                ];
              })}
            </tbody>
          </table>
        </div>
        <ul className="mt-3 list-disc pl-5 text-xs text-slate-500">{methodology.map((m, i) => <li key={i} className="my-0.5">{m}</li>)}</ul>
      </Panel>
    </div>
  );
}

function Conclusions({ h, onGoto }) {
  const { conclusions, strategies, domains, indicators } = h;
  const label = (id) => domains.find((d) => d.id === id)?.label || id;
  const indLabel = (id) => indicators.find((i) => i.id === id)?.label || id;
  return (
    <div className="grid gap-5">
      <Panel icon={History} title="Qué dicen 17 años de datos">
        {conclusions.map((c) => (
          <div key={c.domain} className="grid gap-1 border-b border-slate-100 py-3 last:border-0 sm:grid-cols-[120px_1fr] sm:gap-3">
            <div><Tag tone="brand">{label(c.domain)}</Tag></div><p className="text-sm leading-relaxed text-slate-700">{c.text}</p>
          </div>
        ))}
      </Panel>
      <Panel icon={Target} tone="green" title="Estrategias para Carlos Arias" hint="Cada una se apoya en indicadores de esta pestaña y está dentro de lo que un concejal y candidato puede hacer: control político, proyectos de acuerdo, propuesta de gobierno y comunicación con datos.">
        <div className="grid gap-4 lg:grid-cols-2">
          {strategies.map((s, i) => (
            <article key={i} className="rounded-2xl border border-slate-200 bg-white p-4">
              <h3 className="mb-2 flex items-center gap-2 text-[15px] font-semibold text-slate-900"><span className="grid size-6 place-items-center rounded-lg bg-brand-50 text-xs font-bold text-brand-700">{i + 1}</span>{s.title}</h3>
              <div className="grid gap-2 text-[13px] leading-relaxed text-slate-700">
                <p><b>Por qué:</b> {s.why}</p>
                <div><b>Qué hacer:</b><ul className="ml-5 mt-1 list-disc">{s.actions.map((a, j) => <li key={j}>{a}</li>)}</ul></div>
                <p><b>Viabilidad:</b> {s.viability}</p>
                <p><b>Cómo medir el avance:</b> {s.measure}</p>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">{s.evidence.map((e) => <Tag key={e} tone="brand" onClick={() => onGoto(e)}>{indLabel(e)}</Tag>)}</div>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function CiudadHistoria() {
  const { data: h } = useApi("/api/city-history");
  const [domain, setDomain] = useState(DOMAIN_ORDER[0]);
  if (!h) return <div className="grid gap-5"><Skeleton className="h-28" /><PanelSkeleton h="h-80" /></div>;
  const heads = h.indicators.filter((i) => i.headline);
  const goto = (id) => {
    const ind = h.indicators.find((i) => i.id === id);
    if (!ind) return;
    setDomain(ind.domain);
    setTimeout(() => document.getElementById(`hist-ind-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 120);
  };
  return (
    <div className="grid gap-5">
      <Intro icon={History} title="Cali de 2008 a hoy, alcaldía por alcaldía">
        <p>Economía, condiciones sociales, seguridad, salud y transporte en las cinco alcaldías desde 2008 (Ospina, Guerrero, Armitage, Ospina y Eder, esta última en curso). Cada cifra enlaza su fuente oficial o su consolidación en <b>Cali Cómo Vamos</b>; los años sin dato verificable quedan vacíos en lugar de estimarse. Cada alcaldía se evalúa entre lo que recibió (el dato del año anterior a su posesión) y lo que entregó.</p>
      </Intro>
      <KpiGrid>
        {heads.map((ind, i) => {
          const o = ind.overall;
          return (
            <Kpi key={ind.id} delay={i * 50} small label={ind.label} value={fmtVal(o.last, ind)} tone={o.verdict === "mejoró" ? "pos" : o.verdict === "empeoró" ? "neg" : "default"}
              icon={o.verdict === "empeoró" ? TrendingDown : TrendingUp} iconTone={o.verdict === "mejoró" ? "green" : o.verdict === "empeoró" ? "red" : "slate"}
              foot={<>{o.last_year} · {o.first_year}: {fmtVal(o.first, ind)} ({o.pct > 0 ? "+" : ""}{o.pct.toLocaleString("es-CO")}%)
                {o.best_year && o.best_year !== o.last_year ? ` · mejor año: ${o.best_year} (${fmtVal(ind.points.find((p) => p.year === o.best_year).value, ind)})` : ""}</>} />
          );
        })}
      </KpiGrid>
      <Segmented value={domain} onChange={setDomain} label="Frentes del histórico" className="justify-self-start"
        options={[...DOMAIN_ORDER.map((id) => [id, h.domains.find((d) => d.id === id).label]), ["comparacion", "Comparación"], ["conclusiones", "Conclusiones y estrategias"]]} />
      {domain === "comparacion" ? <Comparison h={h} /> : domain === "conclusiones" ? <Conclusions h={h} onGoto={goto} /> : <DomainView h={h} domain={domain} />}
    </div>
  );
}

/* ---------- Alcaldías: proyectos y deuda ---------- */
function Alcaldias() {
  const { data } = useApi("/api/institutional-history");
  if (!data) return <div className="grid gap-5"><PanelSkeleton h="h-80" /><PanelSkeleton /></div>;
  const { administrations, debt_timeline } = data;
  return (
    <div className="grid gap-5">
      <p className="px-1 text-[13px] leading-relaxed text-slate-500">Investigación documental (prensa, fuentes oficiales, un estudio académico) sobre qué se hizo, qué quedó sin terminar y cómo evolucionó la deuda pública distrital en cada administración. Cada dato tiene su fuente citada; toca «fuente» para verificarlo. Donde la fuente es un editorial de opinión, se marca explícitamente: es un señalamiento de ese medio, no un hallazgo verificado de forma independiente. Las fuentes marcadas «por verificar» apuntan a una página general y deben reemplazarse por la nota específica.</p>
      <Panel icon={Landmark} tone="red" title="¿Cómo ha crecido la deuda pública del Distrito?" hint="Cifras con fuente citada únicamente; los períodos sin cifra verificable no aparecen en la gráfica.">
        <HBar categories={debt_timeline.map((d) => `${d.mayor} (${d.period})`)} data={debt_timeline.map((d) => d.value_billones_cop)} colors={RED} labelFmt={(v) => `$${v} billones`} label="Deuda pública del Distrito" />
      </Panel>
      <div className="grid items-start gap-5 xl:grid-cols-2">
        {administrations.map((a) => {
          const c = a.status_counts;
          return (
            <section key={a.mayor + a.period} className="card min-w-0 p-4 sm:p-5">
              <h2 className="text-base font-semibold text-slate-900">{a.mayor}</h2>
              <div className="mb-3 flex flex-wrap items-center gap-2 text-[13px] text-slate-500">{a.period} · {a.party} · <Tag tone={a.status === "en curso" ? "pending" : "neutral"}>{a.status}</Tag></div>
              <p className="text-sm leading-relaxed text-slate-700">{a.summary}</p>
              <div className="my-3 flex flex-wrap gap-1.5"><Tag tone="positive">{c.completado} completados</Tag><Tag tone="pending">{c["en curso"]} en curso</Tag><Tag tone="negative">{c.incompleto} incompletos</Tag></div>
              {a.debt && (
                <div className="mb-2">
                  {a.debt.value_billones_cop != null && <Tag tone="negative">Deuda: ~${a.debt.value_billones_cop} billones</Tag>}
                  <p className="mt-1 text-xs text-slate-500">{a.debt.note} — <LinkOut href={a.debt.source.url}>fuente: {a.debt.source.name}</LinkOut></p>
                </div>
              )}
              <div className="grid gap-2">
                {(a.metrics || []).map((m, i) => (
                  <div key={i} className="rounded-xl border border-slate-200 p-3 text-sm">
                    <b>{m.label}</b>{m.change_pct != null && <Tag tone={m.change_pct <= 0 ? "positive" : "negative"} className="ml-2">{m.change_pct > 0 ? "+" : ""}{m.change_pct}%</Tag>}
                    <div className="text-xs text-slate-500">{m.note}</div><div className="text-xs text-slate-500"><Source s={m.source} /></div>
                  </div>
                ))}
                {a.projects.map((p, i) => (
                  <div key={i} className="rounded-xl border border-slate-200 p-3 text-sm">
                    <div className="flex flex-wrap items-start justify-between gap-2"><b>{p.name}</b><Tag tone={STATUS_TAG[p.status]}>{p.status}</Tag></div>
                    <div className="text-xs text-slate-500">{p.category}</div>
                    <p className="my-1.5 text-slate-700">{p.description}</p>
                    <div className="text-xs text-slate-500"><Source s={p.source} /></div>
                  </div>
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

/* ---------- Conversación: período vs. anterior ---------- */
function Conversacion() {
  const { days } = useApp();
  const { data: topics } = useApi(`/api/city/topics?days=${days}`);
  if (!topics) return <div className="grid gap-5"><Skeleton className="h-28" /><PanelSkeleton h="h-80" /></div>;
  const totalNow = topics.reduce((a, t) => a + t.count, 0);
  const totalPrev = topics.reduce((a, t) => a + t.previous, 0);
  const totalTrend = totalPrev ? Math.round(((totalNow - totalPrev) / totalPrev) * 100) : null;
  // Solo cambios con volumen suficiente: «+300%» pasando de 1 a 4 menciones no es una tendencia.
  const withTrend = topics.filter((t) => t.trend_pct !== null && !t.small_sample).sort((a, b) => b.trend_pct - a.trend_pct);
  const rising = withTrend.find((t) => t.trend_significant && t.trend_pct > 0) || null;
  const sorted = [...topics].sort((a, b) => b.count - a.count);
  const badge = (t) => {
    const sign = t.trend_pct >= 0 ? "+" : "";
    if (t.previous === 0 && t.count > 0) return <Tag tone="positive">nuevo</Tag>;
    if (t.trend_pct === null) return <span className="text-slate-400">sin datos previos</span>;
    if (t.small_sample) return <span title="Menos de 10 menciones entre los dos períodos: no alcanza para hablar de tendencia">{sign}{t.trend_pct}% · muestra chica</span>;
    if (!t.trend_significant) return <Tag title={`p = ${t.trend_p}: el cambio cabe dentro de la variación normal`}>{sign}{t.trend_pct}% · no concluyente</Tag>;
    return <Tag tone={t.trend_pct >= 0 ? "positive" : "negative"} title={`p = ${t.trend_p}`}>{sign}{t.trend_pct}% · significativo</Tag>;
  };
  return (
    <div className="grid gap-5">
      <p className="px-1 text-[13px] leading-relaxed text-slate-500">Compara el período elegido arriba contra el período inmediatamente anterior de la misma duración: qué creció, qué bajó y qué es enteramente nuevo en la conversación de la ciudad. Un cambio solo se marca como significativo si supera la variación normal esperable (prueba binomial, 5%); con menos de 10 menciones entre los dos períodos se marca «muestra chica».</p>
      <KpiGrid>
        <Kpi icon={BarChart3} label="Menciones ahora" value={totalNow} foot={periodLabel(days)} />
        <Kpi delay={60} icon={History} iconTone="slate" label="Menciones período anterior" value={totalPrev} foot="misma duración, inmediatamente antes" />
        <Kpi delay={120} icon={totalTrend !== null && totalTrend < 0 ? TrendingDown : TrendingUp} iconTone={totalTrend === null ? "slate" : totalTrend >= 0 ? "green" : "red"}
          tone={totalTrend === null ? "default" : totalTrend >= 0 ? "pos" : "neg"} label="Variación total" value={totalTrend === null ? "—" : (totalTrend >= 0 ? "+" : "") + totalTrend + "%"} foot="vs el período anterior" />
        <Kpi delay={180} icon={Building} small label="Más creció" value={rising ? cap(rising.category) : "—"} foot={rising ? `+${rising.trend_pct}% vs antes` : "sin comparación disponible"} />
      </KpiGrid>
      <Panel icon={TrendingUp} tone="green" title="¿Qué cambió respecto al período anterior?" hint="% de variación en menciones por tema. Verde = creció, rojo = bajó, gris = el cambio no es concluyente.">
        {withTrend.length ? (
          <HBar categories={withTrend.map((t) => cap(t.category) + (t.trend_significant ? "" : " (no concluyente)"))} data={withTrend.map((t) => t.trend_pct)}
            colors={withTrend.map((t) => (!t.trend_significant ? NEUTRAL_TONE : t.trend_pct >= 0 ? GOOD : CRITICAL))} labelFmt={(v) => (v >= 0 ? "+" : "") + v + "%"} label="Variación por tema" />
        ) : <Empty>Sin datos suficientes para comparar con el período anterior.</Empty>}
      </Panel>
      <Panel icon={Scale} title="Detalle por tema" hint="Menciones actuales vs. período anterior, tema por tema.">
        {sorted.length ? (
          <div className="grid gap-2">
            {sorted.map((t) => (
              <div key={t.category} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200/80 bg-white px-4 py-3 text-sm">
                <b className="text-slate-900">{cap(t.category)}</b>
                <span className="flex flex-wrap items-center gap-2 text-xs text-slate-500">{t.count} ahora · {t.previous} antes · {badge(t)}</span>
              </div>
            ))}
          </div>
        ) : <Empty>Sin datos suficientes en el período.</Empty>}
      </Panel>
    </div>
  );
}

export default function Historico() {
  const [sub, setSub] = useState("ciudad");
  return (
    <div className="grid gap-5">
      <Segmented value={sub} onChange={setSub} label="Histórico" className="justify-self-start"
        options={[["ciudad", "Cali 2008 a hoy", History], ["alcaldias", "Alcaldías: proyectos y deuda", Landmark], ["conversacion", "Conversación: período vs. anterior", GitCompareArrows]]} />
      {sub === "ciudad" && <CiudadHistoria />}
      {sub === "alcaldias" && <Alcaldias />}
      {sub === "conversacion" && <Conversacion />}
    </div>
  );
}
