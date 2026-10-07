import { useState } from "react";
import { Camera, Newspaper, PlayCircle, Share2, Users2 } from "lucide-react";
import { useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { CARLOS } from "../lib/format";
import { BLUE, CARLOS_GRAY } from "../lib/palette";
import { Empty, Loading, Panel, Segmented, Select, Skeleton } from "../components/ui";
import { FeedPanel } from "../components/FeedPanel";
import { MoreButton, SocialPost } from "../components/Feed";
import { HBar } from "../charts/Chart";

/* Candidatos a la Alcaldía vs. concejales: un concejal muy activo aplastaba la escala y no se
   distinguía nada entre los candidatos. Carlos Arias y Roberto Ortiz cuentan solo como candidatos. */
export function useCouncilorNames() {
  const { data } = useApi("/api/social/candidates");
  return { people: data, names: data ? new Set(data.filter((r) => r.is_councilor).map((r) => r.name)) : null };
}
export const splitByCouncil = (rows, names, key = "candidate") => [rows.filter((r) => !names.has(r[key])), rows.filter((r) => names.has(r[key]))];

function PostList({ rows }) {
  const [shown, setShown] = useState(20);
  return (
    <div className="grid gap-2.5">
      {rows.slice(0, shown).map((r, i) => <SocialPost key={`${r.url ?? i}-${i}`} r={r} />)}
      <MoreButton shown={shown} total={rows.length} onMore={() => setShown(shown + 20)} />
    </div>
  );
}

function RedesSociales() {
  const { days } = useApp();
  const { people, names } = useCouncilorNames();
  const [f, setF] = useState({ candidate: "", platform: "", sort: "engagement" });
  const set = (k) => (v) => setF((p) => ({ ...p, [k]: v }));
  const kpis = useApi(`/api/social/kpis?days=${days}`);
  const p = new URLSearchParams({ days });
  if (f.candidate) p.set("candidate_id", f.candidate);
  if (f.platform) p.set("platform", f.platform);
  if (f.sort) p.set("sort", f.sort);
  const posts = useApi(`/api/social/posts?${p}`);

  const [byCand, byCouncil] = kpis.data && names ? splitByCouncil(kpis.data.by_candidate, names) : [[], []];
  const filters = (
    <>
      <Select label="Filtrar por candidato o concejal" value={f.candidate} onChange={set("candidate")}>
        <option value="">Todos (candidatos y concejales)</option>
        {(people || []).map((r) => <option key={r.candidate_id} value={r.candidate_id}>{r.name}{r.is_councilor ? " (concejal)" : ""}</option>)}
      </Select>
      <Select label="Filtrar por red" value={f.platform} onChange={set("platform")}
        options={[["", "Todas las redes"], ["instagram", "Instagram"], ["facebook", "Facebook"], ["x", "X"]]} />
      <Select label="Ordenar" value={f.sort} onChange={set("sort")} options={[["engagement", "Más alcance"], ["views", "Más vistas"], ["recent", "Más recientes"]]} />
    </>
  );
  return (
    <div className="grid gap-5">
      <Panel icon={Users2} title="Publicaciones por candidato a la Alcaldía" hint="Instagram, Facebook y X — solo posts, no comentarios">
        {!kpis.data || !names ? <Skeleton className="h-72" /> : (
          <HBar categories={byCand.map((c) => c.candidate)} data={byCand.map((c) => c.count)} colors={byCand.map((c) => (c.candidate === CARLOS ? BLUE : CARLOS_GRAY))} label="Publicaciones por candidato" />
        )}
      </Panel>
      <Panel icon={Users2} tone="violet" title="Publicaciones por concejal" hint="Instagram, Facebook y X — solo posts, no comentarios. No incluye a Carlos Arias ni a Roberto Ortiz, ya están en la gráfica de candidatos de arriba.">
        {!kpis.data || !names ? <Skeleton className="h-72" /> : (
          <HBar categories={byCouncil.map((c) => c.candidate)} data={byCouncil.map((c) => c.count)} colors={byCouncil.map(() => CARLOS_GRAY)} label="Publicaciones por concejal" />
        )}
      </Panel>
      <Panel icon={Camera} tone="amber" title="Publicaciones" hint="ordenadas por alcance (likes + comentarios); toca «ver original» para abrirla" actions={filters}>
        {!posts.data ? <Loading rows={4} /> : posts.data.length
          ? <PostList rows={posts.data} />
          : <Empty>Sin publicaciones con esos filtros en el período.</Empty>}
      </Panel>
    </div>
  );
}

export default function Publicaciones() {
  const [sub, setSub] = useState("prensa");
  return (
    <div className="grid gap-5">
      <Segmented value={sub} onChange={setSub} label="Tipo de publicación" className="justify-self-start"
        options={[["prensa", "Prensa", Newspaper], ["social", "Redes sociales", Share2], ["youtube", "YouTube", PlayCircle]]} />
      {sub === "prensa" && (
        <FeedPanel icon={Newspaper} title="Prensa" hint="Google News y RSS — una fila por nota; despliega sus comentarios si los tiene"
          fixed={{ source_type: "prensa" }} fields={["candidate", "label", "emotion", "category", "sort"]} showCandidate />
      )}
      {sub === "social" && <RedesSociales />}
      {sub === "youtube" && (
        <FeedPanel icon={PlayCircle} tone="amber" title="YouTube" hint="videos y comentarios"
          fixed={{ source_type: "youtube" }} fields={["candidate", "label", "emotion", "category"]} showCandidate />
      )}
    </div>
  );
}
