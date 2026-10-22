import { CalendarDays, DoorOpen, Eye, ExternalLink, Newspaper, Radar as RadarIcon, Undo2, UserPlus, X } from "lucide-react";
import { useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { clearCache } from "../lib/cache";
import { notify, post } from "../lib/api";
import { Button, Empty, Intro, LinkOut, Panel, PanelSkeleton, Select, Tag, cx } from "../components/ui";

const STATUS = {
  oficial: { label: "Oficializó", tone: "positive" },
  suena: { label: "Suena", tone: "brand" },
  revisar: { label: "Por confirmar", tone: "pending" },
  declino: { label: "Declinó", tone: "negative" },
};
const NEWS = { oficial: ["Oficializa", "positive"], mueve: ["Se mueve", "pending"], declino: ["Declina", "negative"], suena: ["Suena", "brand"] };
const GROUPS = [["oficial", "Oficializados"], ["suena", "Suenan"], ["revisar", "Por confirmar"], ["declino", "Declinaron"]];
const fmtDay = (d) => (d ? new Date(d + "T12:00:00").toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" }) : "—");

function Person({ p, onChanged }) {
  const st = STATUS[p.status] || STATUS.revisar;
  async function act(path, body, okMsg) {
    const r = await post(path, body);
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { notify(d.error || "No se pudo hacer el cambio.", "error"); return; }
    if (okMsg) notify(okMsg);
    onChanged();
  }
  return (
    <article className="grid min-w-0 gap-2 rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-[1_1_220px] flex-wrap items-center gap-2">
          <h3 className="text-[15px] font-semibold text-slate-900">{p.name}</h3>
          <Tag tone={p.kind === "candidate" ? "dark" : "neutral"}>{p.kind === "candidate" ? "Candidato" : "En observación"}</Tag>
          {p.party && <Tag>{p.party}</Tag>}
        </div>
        <Select className="w-40 shrink-0" value={p.status} onChange={(v) => act(`/api/radar/person/${p.candidate_id}/status`, { status: v })} label={`Estado de ${p.name}`}
          options={[["oficial", "Oficializó"], ["suena", "Suena"], ["revisar", "Por confirmar"], ["declino", "Declinó"]]} />
      </div>
      {p.note && <p className="text-[13px] leading-relaxed text-slate-600">{p.note}{p.url && <> <LinkOut href={p.url}>fuente</LinkOut></>}</p>}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-slate-500">
        <Tag tone={st.tone}>{st.label}{p.date ? ` · ${fmtDay(p.date)}` : ""}</Tag>
        <span>{p.headlines} {p.headlines === 1 ? "titular" : "titulares"} en {p.outlets} {p.outlets === 1 ? "medio" : "medios"} (últimos 30 días)</span>
      </div>
      {p.last && <a href={p.last.url} target="_blank" rel="noopener noreferrer" className="flex min-w-0 items-center gap-1 text-xs text-brand-700 hover:underline"><Newspaper className="size-3.5 shrink-0" /><span className="truncate">{p.last.title}</span></a>}
      {(p.kind === "watch" || p.name !== "Carlos Arias") && (
        <div className="flex flex-wrap gap-2 pt-1">
          {p.kind === "watch" && <Button variant="soft" className="h-8 px-3 text-xs" onClick={() => window.confirm(`¿Pasar a ${p.name} a candidato completo? Cuenta en los gráficos y se busca también en YouTube.`) && act(`/api/radar/person/${p.candidate_id}/promote`, undefined, `${p.name} ya es candidato.`)}>Pasar a candidato</Button>}
          {p.name !== "Carlos Arias" && <Button variant="ghost" icon={DoorOpen} className="h-8 px-3 text-xs" onClick={() => window.confirm(`¿${p.name} anunció que no será candidato? Sale de las listas y de los gráficos (se puede reactivar).`) && act(`/api/radar/person/${p.candidate_id}/retire`, undefined, `${p.name} salió de las listas.`)}>Se retiró</Button>}
          {p.kind === "watch" && <Button variant="ghost" className="h-8 px-3 text-xs" onClick={() => window.confirm(`¿Dejar de seguir a ${p.name}?`) && act(`/api/radar/person/${p.candidate_id}/archive`, undefined, `${p.name} archivado.`)}>Dejar de seguir</Button>}
        </div>
      )}
    </article>
  );
}

export default function Radar() {
  const { refresh } = useApp();
  const { data: d } = useApi("/api/radar?days=30");
  const reload = () => { clearCache(); refresh(); };
  async function suggest(id, action, okMsg) {
    const r = await post(`/api/radar/suggestion/${id}/${action}`);
    if (!r.ok) { notify("No se pudo hacer el cambio.", "error"); return; }
    notify(okMsg);
    reload();
  }

  return (
    <div className="grid gap-5">
      <Intro icon={RadarIcon} title="Radar de precandidatos">
        <p>Para estar siempre al tanto de quién suena para la Alcaldía de Cali. El radar lee los titulares de prensa que el monitor ya recoge, <b>propone nombres nuevos</b> cuando la prensa empieza a mencionarlos y <b>avisa al equipo</b> de cada novedad: quién oficializa, quién declina, quién renuncia para aspirar. <b>Si alguien anuncia su retiro, sale solo de las listas y de los gráficos</b> y se reactiva con un clic si fue un error. Para sumar a alguien nuevo, una persona decide a quién seguir.</p>
        {d && <p className="mt-2 rounded-lg bg-white/10 px-3 py-2 text-white">Faltan <b>{d.days_to_election} días</b> para las elecciones territoriales (31 de octubre de 2027). Se revisa solo cada 3 horas.</p>}
      </Intro>

      {!d ? <PanelSkeleton h="h-64" /> : (
        <>
          <Panel icon={UserPlus} tone="amber" title="Nombres por revisar" hint="Personas que la prensa empezó a nombrar como posibles aspirantes y que aún no están en el monitor. Un titular puede equivocarse: revisa la nota antes de seguirlos.">
            {d.suggestions.length ? (
              <ul className="divide-y divide-slate-100">
                {d.suggestions.map((s) => (
                  <li key={s.id} className="grid gap-2 py-3 sm:grid-cols-[1fr_auto] sm:items-center">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2"><b className="text-slate-900">{s.name}</b><Tag tone="pending">{s.cue}</Tag>
                        <span className="text-xs text-slate-500">{s.headlines} {s.headlines === 1 ? "titular" : "titulares"} · {s.outlets.slice(0, 3).join(", ")} · {fmtDay(s.last_seen)}</span></div>
                      <a href={s.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex max-w-full items-center gap-1 text-[13px] text-brand-700 hover:underline"><ExternalLink className="size-3.5 shrink-0" /><span className="truncate">{s.title}</span></a>
                    </div>
                    <div className="flex gap-2">
                      <Button icon={Eye} className="h-8 px-3 text-xs" onClick={() => suggest(s.id, "follow", `Ahora se sigue a ${s.name}.`)}>Seguir</Button>
                      <Button variant="ghost" icon={X} className="h-8 px-3 text-xs" onClick={() => suggest(s.id, "dismiss", "Descartado.")}>No es</Button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : <Empty icon={UserPlus}>Ningún nombre nuevo por revisar. Si la prensa empieza a mencionar a alguien, aparece aquí y llega un aviso al equipo.</Empty>}
          </Panel>

          <Panel icon={Newspaper} tone="green" title="Novedades de las últimas dos semanas" hint="Titulares sobre candidatos y precandidatos que ya sigue el monitor. El estado de cada uno lo confirma una persona, abajo.">
            {d.news.length ? (
              <ul className="divide-y divide-slate-100">
                {d.news.map((n, i) => {
                  const [label, tone] = NEWS[n.kind] || NEWS.suena;
                  return (
                    <li key={i} className="py-2.5 text-sm">
                      <div className="flex flex-wrap items-center gap-2"><Tag tone={tone}>{label}</Tag><b className="text-slate-900">{n.name}</b><span className="text-xs text-slate-500">{fmtDay(n.date)} · {n.outlet}</span></div>
                      <a href={n.url} target="_blank" rel="noopener noreferrer" className="mt-1 block text-[13px] text-slate-700 hover:text-brand-700 hover:underline">{n.title}</a>
                    </li>
                  );
                })}
              </ul>
            ) : <Empty>Sin novedades en las últimas dos semanas.</Empty>}
          </Panel>

          <Panel icon={Eye} title="Panorama" hint={`${d.candidates_now} candidatos completos (máximo ${d.max_candidates}: los gráficos tienen colores para ${d.max_candidates}) y los precandidatos en observación, que se siguen solo por prensa y medios locales.`}>
            <div className="grid gap-5">
              {GROUPS.map(([key, title]) => {
                const rows = d.people.filter((p) => p.status === key);
                if (!rows.length) return null;
                return (
                  <section key={key}>
                    <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">{title} · {rows.length}</h3>
                    <div className="grid gap-2.5 lg:grid-cols-2">{rows.map((p) => <Person key={p.candidate_id} p={p} onChanged={reload} />)}</div>
                  </section>
                );
              })}
            </div>
          </Panel>

          <Panel icon={DoorOpen} tone="red" title="Se retiraron" hint="Anunciaron que no serán candidatos: salieron solas de las listas y de los gráficos cuando la prensa lo informó (candidatos, con dos medios; precandidatos, con uno). Si fue un error, se reactivan con un clic.">
            {d.retired.length ? (
              <ul className="divide-y divide-slate-100">
                {d.retired.map((p) => (
                  <li key={p.candidate_id} className="grid gap-2 py-3 sm:grid-cols-[1fr_auto] sm:items-center">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2"><b className="text-slate-900">{p.name}</b><Tag tone="negative">Se retiró · {fmtDay(p.date)}</Tag>{p.party && <Tag>{p.party}</Tag>}</div>
                      <p className="mt-1 text-[13px] text-slate-600">{p.note}{p.url && <> <LinkOut href={p.url}>nota</LinkOut></>}</p>
                    </div>
                    <Button variant="ghost" icon={Undo2} className="h-8 px-3 text-xs" onClick={() => window.confirm(`¿Reactivar a ${p.name}?`) && (async () => {
                      const r = await post(`/api/radar/person/${p.candidate_id}/restore`);
                      if (!r.ok) { notify("No se pudo reactivar.", "error"); return; }
                      notify(`${p.name} volvió a las listas.`); reload();
                    })()}>Reactivar</Button>
                  </li>
                ))}
              </ul>
            ) : <Empty icon={DoorOpen}>Nadie se ha retirado. Si la prensa informa que alguien no será candidato, sale solo de las listas y llega un aviso.</Empty>}
          </Panel>

          <Panel icon={CalendarDays} tone="violet" title="Calendario electoral" hint="Fechas aproximadas según la prensa; se ajustan cuando la Registraduría las confirme.">
            <ol className="grid gap-2.5 sm:grid-cols-3">
              {d.calendar.map((c) => (
                <li key={c.date} className={cx("rounded-2xl border bg-white p-4", c.approx ? "border-slate-200" : "border-brand-300 ring-1 ring-brand-200")}>
                  <div className="text-xs font-semibold text-slate-500">{fmtDay(c.date)}{c.approx && " (aprox.)"}</div>
                  <div className="mt-1 text-sm font-medium text-slate-800">{c.label}</div>
                </li>
              ))}
            </ol>
          </Panel>
        </>
      )}
    </div>
  );
}
