import { ArrowLeft, ListTree, Newspaper } from "lucide-react";
import { useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { Button, Empty, Panel, Reading, Skeleton } from "../components/ui";
import { Hero } from "../components/Hero";
import { FeedList, TopicCards } from "../components/Feed";
import { NAV } from "../components/Shell";

export default function Perfil() {
  const { days, route, lastTab, go } = useApp();
  const summary = useApi(`/api/summary?days=${days}`);
  const rows = summary.data;
  const r = rows?.find((x) => x.candidate_id === route.profileId);
  const topics = useApi(r ? `/api/candidate/topics?name=${encodeURIComponent(r.name)}&days=${days}` : null);
  const feed = useApi(r ? `/api/feed?candidate_id=${r.candidate_id}&days=${days}&limit=80` : null);
  const back = NAV.find((n) => n.id === lastTab)?.label.toLowerCase() || "resumen";

  return (
    <div className="grid gap-5">
      <div><Button variant="ghost" icon={ArrowLeft} onClick={() => go(lastTab)}>Volver a {back}</Button></div>
      {!rows ? <Skeleton className="h-64 rounded-3xl" /> : !r ? <Empty>Sin datos de este candidato en el período.</Empty> : (
        <>
          <Hero r={r} rivals={rows.filter((x) => x !== r)} />
          <Panel icon={ListTree} title={`${r.name}, tema por tema`} hint="de qué se habla sobre esta persona y qué dice la gente en cada asunto: publicaciones, prensa y comentarios">
            {!topics.data ? <Skeleton className="h-32" /> : (
              <>
                {topics.data[0] && (
                  <Reading>El tema del que más se habla es <b>{topics.data[0].topic}</b> ({topics.data[0].count} menciones, {topics.data[0].positive_pct}% a favor).
                    {topics.data[1] && <> Le siguen <b>{topics.data[1].topic}</b>{topics.data[2] && <> y <b>{topics.data[2].topic}</b></>}.</>}</Reading>
                )}
                <TopicCards rows={topics.data} idPrefix="perfil-t" />
              </>
            )}
          </Panel>
          <Panel icon={Newspaper} title="Sus publicaciones y notas" hint="una fila por publicación; despliega sus comentarios">
            {!feed.data ? <Skeleton className="h-40" /> : <FeedList rows={feed.data} />}
          </Panel>
        </>
      )}
    </div>
  );
}

