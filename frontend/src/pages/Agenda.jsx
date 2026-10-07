import { Megaphone, ShieldAlert, Users } from "lucide-react";
import { useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { CARLOS, pct } from "../lib/format";
import { Avatar, Empty, Intro, Panel, PanelSkeleton, Reading, Skeleton, Tag } from "../components/ui";
import { HBar100, SENT_COLORS } from "../charts/Chart";
import { Quotes } from "../components/Feed";

function SpeakCard({ t, i }) {
  return (
    <div className="rounded-2xl border border-slate-200 border-l-4 border-l-brand-500 bg-white p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="flex items-center gap-2 text-base font-semibold capitalize text-slate-900"><span className="grid size-6 place-items-center rounded-lg bg-brand-50 text-xs font-bold text-brand-700">{i + 1}</span>{t.category}</h3>
        <div className="flex flex-wrap gap-1.5">
          <Tag tone="negative">{t.negative_pct}% molestia</Tag><Tag>{t.count} menciones</Tag>
          {t.carlos_mentions === 0 ? <Tag>Carlos: sin presencia</Tag> : <Tag tone="positive">Carlos: {t.carlos_mentions} menciones</Tag>}
        </div>
      </div>
      <p className="my-2 text-[13px] leading-relaxed text-slate-500">La ciudad habló {t.count} veces de este tema y {t.negative_pct}% de esas menciones son quejas o denuncias.{" "}
        {t.carlos_mentions === 0 ? <b className="text-slate-700">Carlos no ha aparecido en la conversación.</b> : `Carlos ya tiene ${t.carlos_mentions} menciones aquí; hay espacio para reforzar.`}</p>
      {t.subtopics.length > 0 && <div className="mb-2 flex flex-wrap gap-1.5">{t.subtopics.map((x) => <Tag key={x.topic}>{x.topic} · {x.count}</Tag>)}</div>}
      <Quotes rows={t.samples.slice(0, 2)} />
    </div>
  );
}

function AvoidCard({ t }) {
  return (
    <div className="rounded-2xl border border-slate-200 border-l-4 border-l-rose-500 bg-white p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold capitalize text-slate-900">{t.category}</h3>
        <div className="flex flex-wrap gap-1.5"><Tag tone="negative">{t.candidate_negative_pct}% de rechazo</Tag><Tag>{t.candidate_comments} reacciones</Tag></div>
      </div>
      <p className="my-2 text-[13px] leading-relaxed text-slate-500">Cuando <b className="text-slate-700">{t.candidates.join(", ")}</b> {t.candidates.length === 1 ? "habló" : "hablaron"} de este tema, {t.candidate_negative_pct}% de las reacciones ciudadanas fueron en contra. La ciudad lo menciona {t.city_count} veces con {t.city_negative_pct}% de molestia.</p>
      {t.subtopics.length > 0 && <div className="mb-2 flex flex-wrap gap-1.5">{t.subtopics.map((x) => <Tag key={x.topic}>{x.topic} · {x.count}</Tag>)}</div>}
      <Quotes rows={t.samples.slice(0, 1)} />
    </div>
  );
}

export default function Agenda() {
  const { days } = useApp();
  const agenda = useApi(`/api/agenda?days=${days}`);
  const perception = useApi(`/api/perception?days=${days}`);
  const a = agenda.data;
  const withComments = (perception.data || []).filter((r) => r.comments > 0);
  const carlos = withComments.find((r) => r.name === CARLOS);
  const worst = [...withComments].sort((x, y) => y.negative_pct - x.negative_pct)[0];

  return (
    <div className="grid gap-5">
      <Intro icon={Megaphone} title="Qué conviene decir, y qué no">
        <p>Esta pestaña cruza tres cosas: <b>de qué se queja la ciudad</b>, <b>de qué habla Carlos</b> y <b>cómo le responde la gente a cada candidato</b>. Un tema entra en «hable de esto» cuando tiene volumen alto, molestia ciudadana y Carlos casi no ha aparecido en él. Entra en «con cuidado» cuando a los candidatos que ya hablaron del tema la gente les respondió mayoritariamente en contra. Todo con la cita textual del ciudadano y su enlace, para que pueda verificarse.</p>
      </Intro>

      {!a ? <div className="grid gap-5 xl:grid-cols-2"><PanelSkeleton h="h-80" /><PanelSkeleton h="h-80" /></div> : (
        <div className="grid items-start gap-5 xl:grid-cols-2">
          <Panel icon={Megaphone} tone="brand" title="Hable de esto" hint="Problemas de la ciudad con molestia alta donde Carlos aún no tiene presencia. Ordenados por prioridad (volumen × molestia, con menos peso si ya está hablando del tema).">
            <Reading>
              {a.speak[0] ? <>La prioridad es <b>{a.speak[0].category}</b>: {a.speak[0].count} menciones con {a.speak[0].negative_pct}% de molestia y {a.speak[0].carlos_mentions === 0 ? "ninguna mención" : `${a.speak[0].carlos_mentions} ${a.speak[0].carlos_mentions === 1 ? "mención" : "menciones"}`} de Carlos.{" "}
                {a.speak[1] && <>Le siguen <b>{a.speak[1].category}</b>{a.speak[2] && <> y <b>{a.speak[2].category}</b></>}.</>}</>
                : "Sin temas prioritarios en el período seleccionado."}
            </Reading>
            <div className="grid gap-3">{a.speak.length ? a.speak.map((t, i) => <SpeakCard key={t.category} t={t} i={i} />) : <Empty>No hay temas con molestia alta sin presencia de Carlos en el período.</Empty>}</div>
          </Panel>
          <Panel icon={ShieldAlert} tone="red" title="Con cuidado" hint="Temas donde la gente respondió mayoritariamente en contra a los candidatos que los tocaron. No significa callar: significa medir el tono y el ángulo antes de entrar.">
            <Reading>
              {a.avoid.length ? <><b>{a.avoid[0].category}</b> es el terreno más hostil: {a.avoid[0].candidate_negative_pct}% de las reacciones a quienes lo tocaron fueron negativas. Entrar ahí exige ángulo propio y propuesta concreta, no opinión general.</>
                : "Ningún tema resultó hostil para los candidatos en el período."}
            </Reading>
            <div className="grid gap-3">{a.avoid.length ? a.avoid.map((t) => <AvoidCard key={t.category} t={t} />) : <Empty>Ningún tema muestra rechazo mayoritario hacia los candidatos que lo tocaron.</Empty>}</div>
          </Panel>
        </div>
      )}

      <Panel icon={Users} tone="green" title="Cómo ve la gente a cada candidato" hint="Solo comentarios y respuestas de ciudadanos a sus publicaciones (no incluye notas de prensa). Es la reacción directa del público.">
        {!perception.data ? <Skeleton className="h-80" /> : (
          <>
            <Reading>
              {carlos ? <>A <b>Carlos Arias</b> la gente le responde {carlos.positive_pct}% a favor y {carlos.negative_pct}% en contra sobre {carlos.comments} comentarios.{" "}
                {worst && worst.name !== CARLOS && <>El más golpeado es <b>{worst.name}</b>, con {worst.negative_pct}% de reacciones en contra ({worst.comments} comentarios).</>}</>
                : "Aún no hay comentarios ciudadanos sobre las publicaciones de Carlos en el período."}
            </Reading>
            <HBar100 categories={withComments.map((r) => `${r.name} (${r.comments})`)} colors={SENT_COLORS} label="Cómo ve la gente a cada candidato"
              series={[{ name: "A favor", data: withComments.map((r) => r.positive_pct) }, { name: "Neutral", data: withComments.map((r) => pct(r.neutral, r.comments)) }, { name: "En contra", data: withComments.map((r) => r.negative_pct) }]} />
            <div className="mt-4 grid gap-3">
              {withComments.length ? withComments.map((r) => (
                <div key={r.name} className="flex gap-3.5 rounded-2xl border border-slate-200/80 bg-white p-4">
                  <Avatar name={r.name} src={r.avatar} size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-3"><b className="text-slate-900">{r.name}</b>
                      <span className="text-xs text-slate-500">{r.comments} comentarios · {r.positive_pct}% a favor · {r.negative_pct}% en contra</span></div>
                    {r.topics.length > 0 && <div className="my-2 flex flex-wrap gap-1.5">{r.topics.map((t) => <Tag key={t.topic}>{t.topic} · {t.count}</Tag>)}</div>}
                    <Quotes rows={r.samples.slice(0, 2)} />
                  </div>
                </div>
              )) : <Empty>Sin comentarios ciudadanos en el período.</Empty>}
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}
