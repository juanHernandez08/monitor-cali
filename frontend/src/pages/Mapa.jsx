import { useEffect, useMemo, useRef, useState } from "react";
import { Globe2, Info, Layers, MapPinned, Maximize2, Minus, MousePointerClick, Plus } from "lucide-react";
import { useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { fmtNum } from "../lib/format";
import { Button, Empty, Intro, Panel, Reading, Segmented, Select, Skeleton, Tag, cx } from "../components/ui";
import { ZoneDetail } from "../components/ZoneDetail";

/* Núcleos territoriales de la campaña (los mismos del mapa «Núcleos Territoriales de Cali»): cada
   comuna pertenece a uno; el Núcleo Rural son los 15 corregimientos. Colores del mismo mapa. */
export const NUCLEOS = [
  { id: "occidente", name: "Núcleo Occidente", color: "#F2DD3D", ink: "#8a7a00", comunas: [2, 3, 9] },
  { id: "norte", name: "Núcleo Norte", color: "#2F6FD0", ink: "#2F6FD0", comunas: [4, 5, 6, 7] },
  { id: "oriente", name: "Núcleo Oriente", color: "#C8302E", ink: "#C8302E", comunas: [13, 14, 15, 16, 21] },
  { id: "centro", name: "Núcleo Centro", color: "#9EA3DA", ink: "#5b60a8", comunas: [8, 10, 11, 12] },
  { id: "ladera", name: "Núcleo Ladera", color: "#EE8A2B", ink: "#b85d0c", comunas: [1, 18, 19, 20] },
  { id: "sur", name: "Núcleo Sur", color: "#2A9A86", ink: "#1f7a6a", comunas: [17, 22] },
  { id: "rural", name: "Núcleo Rural", color: "#A2A7AF", ink: "#5f6570", comunas: [], rural: true },
];
const comunaId = (n) => `comuna:${String(n).padStart(2, "0")}`;
const NUC_OF = Object.fromEntries(NUCLEOS.flatMap((n) => n.comunas.map((c) => [comunaId(c), n])));
const RURAL = NUCLEOS.find((n) => n.rural);
const nucleoOf = (zoneId, parent) => {
  if (zoneId.startsWith("corregimiento:") || zoneId.startsWith("vereda:")) return RURAL;
  return NUC_OF[zoneId] || NUC_OF[parent] || null;
};

/* ---------- formas (frontend/public/geo, generadas por scripts/build_geo.py) ---------- */
const shapeCache = new Map();
function useShapes(names) {
  const key = names.join(",");
  const [data, setData] = useState(() => (names.every((n) => shapeCache.has(n)) ? Object.fromEntries(names.map((n) => [n, shapeCache.get(n)])) : null));
  useEffect(() => {
    let alive = true;
    Promise.all(names.map((n) => shapeCache.get(n) || fetch(`${import.meta.env.BASE_URL}geo/${n}.json`).then((r) => r.json()).then((j) => { shapeCache.set(n, j); return j; })))
      .then((arr) => alive && setData(Object.fromEntries(names.map((n, i) => [n, arr[i]]))));
    return () => { alive = false; };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  // al pasar de Colombia a Cali, el estado aún trae las formas anteriores: no se entregan hasta tener las pedidas
  return data && names.every((n) => data[n]) ? data : null;
}

/* Proyección equirectangular corregida por latitud: para una ciudad (o un país) es suficiente y no
   necesita librería. */
function makeProjection(features, width = 1000) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const walk = (c) => (typeof c[0] === "number" ? (minX = Math.min(minX, c[0]), maxX = Math.max(maxX, c[0]), minY = Math.min(minY, c[1]), maxY = Math.max(maxY, c[1])) : c.forEach(walk));
  features.forEach((f) => walk(f.geometry.coordinates));
  const k = Math.cos(((minY + maxY) / 2) * Math.PI / 180);
  const s = width / ((maxX - minX) * k);
  const height = (maxY - minY) * s;
  const pt = ([x, y]) => `${((x - minX) * k * s).toFixed(1)},${((maxY - y) * s).toFixed(1)}`;
  const ring = (r) => "M" + r.map(pt).join("L") + "Z";
  const path = (g) => (g.type === "Polygon" ? g.coordinates.map(ring).join("") : g.coordinates.map((p) => p.map(ring).join("")).join(""));
  const centroid = (g) => {
    const r = g.type === "Polygon" ? g.coordinates[0] : g.coordinates.reduce((a, p) => (p[0].length > a.length ? p[0] : a), []);
    const [sx, sy] = r.reduce(([a, b], [x, y]) => [a + x, b + y], [0, 0]);
    const [cx, cy] = pt([sx / r.length, sy / r.length]).split(",").map(Number);
    return { x: cx, y: cy };
  };
  return { width, height: Math.max(1, height), path, centroid };
}

/* ---------- zoom y arrastre (rueda, pellizco, botones) ----------
   Se transforma un <g> en unidades del SVG. Un arrastre de más de 5 px no cuenta como clic (no
   cambia la selección). Sin zoom, en el teléfono el dedo sigue desplazando la página (touch-action
   pan-y); con zoom, el dedo mueve el mapa. */
const MAX_ZOOM = 14;
function usePanZoom(width, height, resetKey) {
  const svgRef = useRef(null);
  const [t, setT] = useState({ k: 1, x: 0, y: 0 });
  const pointers = useRef(new Map());
  const gesture = useRef(null);
  const moved = useRef(false);
  useEffect(() => setT({ k: 1, x: 0, y: 0 }), [resetKey, width, height]);

  const clamp = (n) => {
    const k = Math.min(MAX_ZOOM, Math.max(1, n.k));
    return { k, x: Math.min(0, Math.max(width - width * k, n.x)), y: Math.min(0, Math.max(height - height * k, n.y)) };
  };
  const toSvg = (cx, cy) => {
    const r = svgRef.current.getBoundingClientRect();
    return [((cx - r.left) * width) / r.width, ((cy - r.top) * height) / r.height];
  };
  const zoomAt = (px, py, factor) => setT((p) => {
    const k = Math.min(MAX_ZOOM, Math.max(1, p.k * factor));
    const f = k / p.k;
    return clamp({ k, x: px - (px - p.x) * f, y: py - (py - p.y) * f });
  });

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return undefined;
    const onWheel = (e) => {
      e.preventDefault();
      const [px, py] = toSvg(e.clientX, e.clientY);
      zoomAt(px, py, e.deltaY < 0 ? 1.25 : 1 / 1.25);
    };
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }); // eslint-disable-line react-hooks/exhaustive-deps

  const onPointerDown = (e) => {
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    moved.current = false;
    gesture.current = { start: { x: e.clientX, y: e.clientY }, last: { x: e.clientX, y: e.clientY }, dist: null };
    const move = (ev) => {
      if (!pointers.current.has(ev.pointerId)) return;
      pointers.current.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
      const pts = [...pointers.current.values()];
      const g = gesture.current;
      if (pts.length >= 2) {  // pellizco
        const d = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
        if (g.dist) {
          const [px, py] = toSvg((pts[0].x + pts[1].x) / 2, (pts[0].y + pts[1].y) / 2);
          zoomAt(px, py, d / g.dist);
        }
        g.dist = d;
        moved.current = true;
        return;
      }
      if (Math.hypot(ev.clientX - g.start.x, ev.clientY - g.start.y) > 5) moved.current = true;
      const r = svgRef.current.getBoundingClientRect();
      const dx = ((ev.clientX - g.last.x) * width) / r.width, dy = ((ev.clientY - g.last.y) * height) / r.height;
      g.last = { x: ev.clientX, y: ev.clientY };
      setT((p) => (p.k > 1 ? clamp({ k: p.k, x: p.x + dx, y: p.y + dy }) : p));
    };
    const up = (ev) => {
      pointers.current.delete(ev.pointerId);
      if (gesture.current) gesture.current.dist = null;
      if (!pointers.current.size) {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        window.removeEventListener("pointercancel", up);
      }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  };
  const onClickCapture = (e) => {
    if (moved.current) { e.stopPropagation(); e.preventDefault(); moved.current = false; }
  };
  const btn = (factor) => zoomAt(width / 2, height / 2, factor);
  return {
    t, svgRef,
    svgProps: { ref: svgRef, onPointerDown, onClickCapture, style: { touchAction: t.k > 1 ? "none" : "pan-y", cursor: t.k > 1 ? "grab" : undefined } },
    transform: `translate(${t.x.toFixed(1)} ${t.y.toFixed(1)}) scale(${t.k.toFixed(3)})`,
    zoomIn: () => btn(1.6), zoomOut: () => btn(1 / 1.6), reset: () => setT({ k: 1, x: 0, y: 0 }),
  };
}

function ZoomControls({ pz }) {
  const b = "grid size-8 place-items-center rounded-lg bg-white text-slate-700 shadow ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-40";
  return (
    <div className="absolute right-2 top-2 z-10 grid gap-1">
      <button type="button" className={b} onClick={pz.zoomIn} disabled={pz.t.k >= MAX_ZOOM} aria-label="Acercar"><Plus className="size-4" /></button>
      <button type="button" className={b} onClick={pz.zoomOut} disabled={pz.t.k <= 1} aria-label="Alejar"><Minus className="size-4" /></button>
      <button type="button" className={b} onClick={pz.reset} disabled={pz.t.k <= 1} aria-label="Ver todo el mapa"><Maximize2 className="size-4" /></button>
    </div>
  );
}

/* ---------- escalas de color (una sola tonalidad, de claro a oscuro) ---------- */
const BLUES = ["#e8f0fb", "#c4d8f4", "#8fb5e8", "#4f86d4", "#1f5fb8"];
const REDS = ["#fbeceb", "#f4c7c3", "#e8928b", "#d55a50", "#a8322a"];
const NO_DATA = "#eef0f4";
const step = (v, max, ramp) => (v == null || !max ? NO_DATA : ramp[Math.min(ramp.length - 1, Math.floor((v / max) * ramp.length * 0.999))]);

function Legend({ mode, max, minMentions }) {
  if (mode === "nucleo") return null;
  const ramp = mode === "neg" ? REDS : BLUES;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500">
      <span className="flex items-center gap-1">{mode === "neg" ? "% negativo" : "Menciones"}: 0
        {ramp.map((c) => <span key={c} className="inline-block h-2.5 w-5" style={{ background: c }} />)}{mode === "neg" ? "100 %" : fmtNum(max)}</span>
      <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-5 border border-dashed border-slate-300" style={{ background: NO_DATA }} />sin datos o menos de {minMentions} menciones</span>
    </div>
  );
}

/* ---------- el mapa ---------- */
function CityMap({ shapes, zonesBy, mode, detail, showRural, selected, isSelected, onPick, minMentions }) {
  const [tip, setTip] = useState(null);
  const box = useRef(null);
  const base = useMemo(() => [...shapes.comunas.features, ...(showRural ? shapes.corregimientos.features : [])], [shapes, showRural]);
  const proj = useMemo(() => makeProjection(base), [base]);
  const fine = detail === "barrios" ? shapes.barrios.features : shapes.comunas.features;
  const fineZones = detail === "barrios" ? zonesBy.barrio : zonesBy.comuna;
  const maxOf = (zs) => Math.max(1, ...Object.values(zs || {}).map((z) => z.mentions));
  const max = Math.max(maxOf(fineZones), showRural ? maxOf(zonesBy.corregimiento) : 1);
  const pz = usePanZoom(proj.width, proj.height, showRural);
  const k = pz.t.k;

  const fill = (f, zs) => {
    const z = zs?.[f.properties.id];
    if (mode === "nucleo") return (nucleoOf(f.properties.id, f.properties.parent) || RURAL).color;
    if (!z || (mode === "neg" && !z.conclusive)) return NO_DATA;
    return mode === "neg" ? step(z.negative_pct, 100, REDS) : step(z.mentions, max, BLUES);
  };
  const dimmed = (f) => selected && !isSelected(f.properties.id, f.properties.parent);
  const move = (e, f, zs) => {
    const r = box.current.getBoundingClientRect();
    const z = zs?.[f.properties.id];
    const n = nucleoOf(f.properties.id, f.properties.parent);
    setTip({ x: e.clientX - r.left, y: e.clientY - r.top, name: f.properties.name, nucleo: n?.name, z });
  };
  const layer = (features, zs, cls) => features.map((f) => (
    <path key={f.properties.id} d={proj.path(f.geometry)} fill={fill(f, zs)} tabIndex={0} role="button" aria-label={f.properties.name}
      className={cx("cursor-pointer outline-none transition-opacity duration-200 hover:brightness-105 focus-visible:stroke-slate-900", cls, dimmed(f) && "opacity-20")}
      stroke="#fff" strokeWidth={detail === "barrios" && cls === "fine" ? 0.6 : 1.4} vectorEffect="non-scaling-stroke"
      onClick={(e) => onPick(f.properties.id, f.properties.parent, e)} onKeyDown={(e) => e.key === "Enter" && onPick(f.properties.id, f.properties.parent, e)}
      onMouseMove={(e) => move(e, f, zs)} onMouseLeave={() => setTip(null)} />
  ));

  return (
    <div ref={box} className="relative">
      <ZoomControls pz={pz} />
      <svg viewBox={`0 0 ${proj.width} ${proj.height}`} className="block h-auto max-h-[78vh] w-full overflow-hidden rounded-xl select-none" role="img" aria-label="Mapa de Cali por zonas" {...pz.svgProps}>
        <g transform={pz.transform}>
        {showRural && layer(shapes.corregimientos.features, zonesBy.corregimiento, "rural")}
        {layer(fine, fineZones, "fine")}
        {detail === "barrios" && shapes.comunas.features.map((f) => (
          <path key={f.properties.id} d={proj.path(f.geometry)} fill="none" stroke="#1d2330" strokeOpacity={dimmed(f) ? 0.15 : 0.55} strokeWidth={1.6} vectorEffect="non-scaling-stroke" pointerEvents="none" />
        ))}
        {shapes.comunas.features.map((f) => {
          const c = proj.centroid(f.geometry);
          return <text key={f.properties.id} x={c.x} y={c.y} textAnchor="middle" dominantBaseline="central" pointerEvents="none"
            className={cx("select-none fill-slate-900 font-bold transition-opacity", dimmed(f) && "opacity-25")}
            style={{ fontSize: 22 / Math.sqrt(k), paintOrder: "stroke", stroke: "rgba(255,255,255,.85)", strokeWidth: 4 / Math.sqrt(k) }}>{f.properties.id.split(":")[1].replace(/^0/, "")}</text>;
        })}
        {detail === "barrios" && k >= 4 && shapes.barrios.features.map((f) => {
          // con bastante zoom, el nombre de cada barrio
          const c = proj.centroid(f.geometry);
          return <text key={`n-${f.properties.id}`} x={c.x} y={c.y + 16 / k} textAnchor="middle" pointerEvents="none"
            className={cx("select-none fill-slate-700", dimmed(f) && "opacity-25")}
            style={{ fontSize: 24 / k, paintOrder: "stroke", stroke: "rgba(255,255,255,.9)", strokeWidth: 3 / k }}>{f.properties.name}</text>;
        })}
        </g>
      </svg>
      {tip && (
        <div className="pointer-events-none absolute z-10 max-w-[260px] -translate-x-1/2 -translate-y-[115%] rounded-lg bg-slate-900 px-3 py-2 text-xs leading-snug text-white shadow-lg"
          style={{ left: tip.x, top: tip.y }}>
          <b className="block text-[13px]">{tip.name}</b>
          {tip.nucleo && <span className="text-slate-300">{tip.nucleo}</span>}
          <div className="mt-1">{tip.z ? <>{fmtNum(tip.z.mentions)} menciones · {tip.z.negative_pct} % negativas{!tip.z.conclusive && " (pocas: no concluyente)"}</> : "Sin menciones en el período"}</div>
        </div>
      )}
      <Legend mode={mode} max={max} minMentions={minMentions} />
      <p className="mt-1 text-[11px] text-slate-500">Acerca con la rueda del mouse, pellizcando o con «+»; arrastra para moverte. Con zoom en «Barrios» aparecen sus nombres.</p>
    </div>
  );
}

function ColombiaMap({ shapes, zones, selected, onPick }) {
  const [tip, setTip] = useState(null);
  const box = useRef(null);
  const proj = useMemo(() => makeProjection(shapes.departamentos.features, 800), [shapes]);
  const max = Math.max(1, ...Object.values(zones).map((z) => z.mentions));
  const pz = usePanZoom(proj.width, proj.height, "co");
  return (
    <div ref={box} className="relative mx-auto max-w-[560px]">
      <ZoomControls pz={pz} />
      <svg viewBox={`0 0 ${proj.width} ${proj.height}`} className="block h-auto max-h-[78vh] w-full overflow-hidden rounded-xl select-none" role="img" aria-label="Mapa de Colombia por departamento" {...pz.svgProps}>
        <g transform={pz.transform}>
        {shapes.departamentos.features.map((f) => {
          const z = zones[f.properties.id];
          return <path key={f.properties.id} d={proj.path(f.geometry)} fill={z ? step(Math.log1p(z.mentions), Math.log1p(max), BLUES) : NO_DATA} stroke="#fff" strokeWidth={1.2} vectorEffect="non-scaling-stroke"
            className={cx("cursor-pointer transition-opacity hover:brightness-105", selected && selected !== f.properties.id && "opacity-30")}
            onClick={() => onPick(f.properties.id)}
            onMouseMove={(e) => { const r = box.current.getBoundingClientRect(); setTip({ x: e.clientX - r.left, y: e.clientY - r.top, name: f.properties.name, z }); }}
            onMouseLeave={() => setTip(null)} />;
        })}
        </g>
      </svg>
      {tip && (
        <div className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-[115%] rounded-lg bg-slate-900 px-3 py-2 text-xs text-white shadow-lg" style={{ left: tip.x, top: tip.y }}>
          <b className="block text-[13px]">{tip.name}</b>{tip.z ? `${fmtNum(tip.z.mentions)} menciones` : "Sin menciones"}
        </div>
      )}
      <Legend mode="vol" max={max} minMentions={5} />
      <p className="mt-1 text-[11px] text-slate-500">Escala logarítmica: cada paso de color es varias veces más menciones que el anterior, para que el Valle no deje al resto del país del mismo tono.</p>
    </div>
  );
}

/* ---------- tarjetas de núcleo (lista lateral, como en el mapa de núcleos) ---------- */
function NucleoCard({ n, stats, on, onClick }) {
  return (
    <button type="button" onClick={onClick}
      className={cx("grid w-full grid-cols-[14px_1fr_auto] items-center gap-x-3 gap-y-1 rounded-xl border bg-white px-3.5 py-3 text-left transition",
        on ? "border-slate-900 ring-1 ring-slate-900" : "border-slate-200 hover:border-slate-400")}>
      <span className="row-span-2 mt-1 size-3.5 self-start rounded" style={{ background: n.color }} />
      <span className="text-[15px] font-semibold text-slate-900">{n.name}</span>
      <span className="text-xs tabular-nums text-slate-500">{stats ? `${fmtNum(stats.mentions)} menc.` : "—"}</span>
      <span className="col-span-2 flex flex-wrap gap-1">
        {n.rural ? <Tag>15 corregimientos</Tag> : n.comunas.map((c) => <Tag key={c}>C{c}</Tag>)}
        {stats?.mentions > 0 && <Tag tone={stats.negative_pct >= 40 ? "negative" : "neutral"}>{stats.negative_pct} % negativo</Tag>}
      </span>
    </button>
  );
}

export default function Mapa() {
  const { days } = useApp();
  const [scope, setScope] = useState("cali");
  const [group, setGroup] = useState("nucleo"); // nucleo | comuna | custom
  const [mode, setMode] = useState("nucleo"); // nucleo | vol | neg
  const [detail, setDetail] = useState("comunas");
  const [showRural, setShowRural] = useState(false);
  const [selNucleo, setSelNucleo] = useState(null);
  const [selZone, setSelZone] = useState(null);
  const [custom, setCustom] = useState([]);
  const [selDpto, setSelDpto] = useState(null);

  const shapes = useShapes(scope === "cali" ? ["comunas", "barrios", "corregimientos"] : ["departamentos"]);
  // «De quién se habla»: toda la conversación o solo lo que se dice de un candidato (por defecto, todo)
  const candList = useApi("/api/social/candidates");
  const [cand, setCand] = useState("");
  const candQ = cand ? `&candidate_id=${cand}` : "";
  const candName = (candList.data || []).find((c) => String(c.candidate_id) === cand)?.name;
  const zc = useApi(`/api/geo/zones?days=${days}&level=comuna${candQ}`);
  const zb = useApi(scope === "cali" ? `/api/geo/zones?days=${days}&level=barrio${candQ}` : null);
  const zr = useApi(scope === "cali" ? `/api/geo/zones?days=${days}&level=corregimiento${candQ}` : null);
  const zd = useApi(scope === "colombia" ? `/api/geo/zones?days=${days}&level=departamento${candQ}` : null);
  const by = (r) => Object.fromEntries((r.data?.zones || []).map((z) => [z.id, z]));
  const zonesBy = { comuna: by(zc), barrio: by(zb), corregimiento: by(zr) };
  const cov = zc.data?.coverage;
  const minMentions = zc.data?.min_mentions || 5;

  // totales por núcleo: suma de sus comunas (una mención que nombra dos comunas del mismo núcleo cuenta dos veces
  // aquí; el detalle, que es el que vale para leer, la cuenta una sola vez)
  const nucStats = useMemo(() => Object.fromEntries(NUCLEOS.map((n) => {
    const zs = n.rural ? Object.values(zonesBy.corregimiento) : n.comunas.map((c) => zonesBy.comuna[comunaId(c)]).filter(Boolean);
    const mentions = zs.reduce((a, z) => a + z.mentions, 0), scored = zs.reduce((a, z) => a + z.scored, 0), neg = zs.reduce((a, z) => a + z.negative, 0);
    return [n.id, { mentions, negative_pct: scored ? Math.round((neg / scored) * 100) : 0 }];
  })), [zc.data, zr.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const nucIds = (n) => (n.rural ? (shapes?.corregimientos?.features || []).map((f) => f.properties.id) : n.comunas.map(comunaId));
  const nameOf = (id) => {
    for (const layer of ["comunas", "barrios", "corregimientos"]) {
      const f = shapes?.[layer]?.features.find((x) => x.properties.id === id);
      if (f) return f.properties.name;
    }
    return id;
  };

  let selIds = [], selTitle = "", selColor = null, isSelected = () => true, selected = false;
  if (group === "nucleo" && selNucleo) {
    const n = NUCLEOS.find((x) => x.id === selNucleo);
    selIds = nucIds(n); selTitle = n.name; selColor = n.color; selected = true;
    isSelected = (id, parent) => nucleoOf(id, parent)?.id === n.id;
  } else if (group === "comuna" && selZone) {
    selIds = [selZone]; selTitle = nameOf(selZone); selected = true;
    isSelected = (id, parent) => id === selZone || parent === selZone;
  } else if (group === "custom" && custom.length) {
    selIds = custom; selTitle = `Grupo personalizado (${custom.length} zonas)`; selected = true;
    isSelected = (id, parent) => custom.includes(id) || custom.includes(parent);
  }

  const onPick = (id, parent) => {
    if (group === "nucleo") {
      const n = nucleoOf(id, parent);
      if (n) { if (n.rural) setShowRural(true); setSelNucleo(selNucleo === n.id ? null : n.id); }
    } else if (group === "comuna") setSelZone(selZone === id ? null : id);
    else setCustom(custom.includes(id) ? custom.filter((x) => x !== id) : [...custom, id]);
  };
  const changeGroup = (g) => { setGroup(g); setSelNucleo(null); setSelZone(null); setCustom([]); if (g !== "nucleo" && mode === "nucleo") setMode("vol"); };

  return (
    <div className="grid gap-5">
      <Intro icon={MapPinned} title="De qué zona se habla">
        <p>Cada publicación, comentario o nota se ubica en la comuna, barrio, corregimiento o vereda que <b>nombra</b> (o, si es un comentario, en la del video o publicación que comenta). Mide <b>de qué zona se habla</b>, no desde dónde escribe la gente: las redes no entregan esa ubicación, y nunca se ubica a una persona. Los límites son los oficiales de Planeación (IDESC, Acuerdo 0636 de 2026).</p>
        {cov && <p className="mt-2 rounded-lg bg-white/10 px-3 py-2 text-white">En este período, <b>{fmtNum(cov.located_in_cali)} de {fmtNum(cov.mentions)} menciones ({cov.located_pct} %)</b> nombran una zona concreta de Cali{candName ? <> y hablan de <b>{candName}</b></> : null}. El mapa se lee con esa base: es lo que la conversación dice de cada zona, no una encuesta.</p>}
      </Intro>

      <Panel icon={Layers} title={scope === "cali" ? "Mapa de Cali" : "Mapa de Colombia"}
        hint={scope === "cali"
          ? (group === "nucleo" ? "Clic en una comuna (o en la lista) para ver su núcleo completo." : group === "comuna" ? "Clic en una zona para ver solo esa zona." : "Clic en varias zonas para armar tu propio grupo; clic de nuevo para quitarla.")
          : "Menciones por departamento. El Valle concentra casi todo: el monitor escucha a Cali."}
        actions={<>
          <Segmented size="sm" value={scope} onChange={(v) => { setScope(v); setSelDpto(null); }} options={[["cali", "Cali", MapPinned], ["colombia", "Colombia", Globe2]]} label="Alcance" />
          <Select value={cand} onChange={setCand} label="De quién se habla"
            options={[["", "Toda la conversación"], ...(candList.data || []).filter((c) => !c.is_councilor).map((c) => [String(c.candidate_id), `Solo ${c.name}`]),
              ...(candList.data || []).filter((c) => c.is_councilor).map((c) => [String(c.candidate_id), `Solo ${c.name} (concejal)`])]} />
          {scope === "cali" && <Select value={group} onChange={changeGroup} label="Agrupar" options={[["nucleo", "Agrupar por núcleo"], ["comuna", "Zona por zona"], ["custom", "Grupo personalizado"]]} />}
        </>}>
        {scope === "cali" ? (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Segmented size="sm" value={mode} onChange={setMode} label="Color"
                options={[...(group === "nucleo" ? [["nucleo", "Color por núcleo"]] : []), ["vol", "Menciones"], ["neg", "% negativo"]]} />
              <Segmented size="sm" value={detail} onChange={setDetail} label="Detalle" options={[["comunas", "Comunas"], ["barrios", "Barrios"]]} />
              <Button variant={showRural ? "soft" : "ghost"} className="h-8 px-3 text-xs" onClick={() => setShowRural(!showRural)}>{showRural ? "Ocultar" : "Mostrar"} Núcleo Rural</Button>
              {group === "custom" && custom.length > 0 && <Button variant="ghost" className="h-8 px-3 text-xs" onClick={() => setCustom([])}>Limpiar grupo</Button>}
            </div>
            <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(260px,1fr)]">
              {!shapes || !zc.data ? <Skeleton className="h-[520px]" /> : (
                <CityMap shapes={shapes} zonesBy={zonesBy} mode={mode} detail={detail} showRural={showRural}
                  selected={selected} isSelected={isSelected} onPick={onPick} minMentions={minMentions} />
              )}
              <aside className="grid gap-2">
                {group === "nucleo" ? NUCLEOS.map((n) => (
                  <NucleoCard key={n.id} n={n} stats={nucStats[n.id]} on={selNucleo === n.id}
                    onClick={() => { if (n.rural) setShowRural(true); setSelNucleo(selNucleo === n.id ? null : n.id); }} />
                )) : (
                  <>
                    <p className="flex items-center gap-2 text-[13px] text-slate-500"><MousePointerClick className="size-4" />{group === "custom" ? "Zonas del grupo:" : "Zonas más mencionadas:"}</p>
                    {(group === "custom" ? custom.map((id) => ({ id, name: nameOf(id), ...(zonesBy.comuna[id] || zonesBy.barrio[id] || zonesBy.corregimiento[id] || {}) }))
                      : [...Object.values(detail === "barrios" ? zonesBy.barrio : zonesBy.comuna)].slice(0, 12)).map((z) => (
                      <button key={z.id} type="button" onClick={() => onPick(z.id)}
                        className={cx("flex items-center justify-between gap-2 rounded-xl border bg-white px-3 py-2 text-left text-sm transition",
                          (selZone === z.id || custom.includes(z.id)) ? "border-slate-900 ring-1 ring-slate-900" : "border-slate-200 hover:border-slate-400")}>
                        <span className="truncate font-medium text-slate-800">{z.name}</span>
                        <span className="shrink-0 text-xs tabular-nums text-slate-500">{z.mentions ? `${fmtNum(z.mentions)} · ${z.negative_pct} % neg.` : "sin menciones"}</span>
                      </button>
                    ))}
                    {group === "custom" && !custom.length && <Empty icon={MousePointerClick}>Toca zonas en el mapa para sumarlas al grupo.</Empty>}
                  </>
                )}
              </aside>
            </div>
          </>
        ) : !shapes || !zd.data ? <Skeleton className="h-[520px]" /> : (
          <ColombiaMap shapes={shapes} zones={by(zd)} selected={selDpto} onPick={(id) => setSelDpto(selDpto === id ? null : id)} />
        )}
      </Panel>

      {scope === "cali" && !selected && (
        <Reading><Info className="mr-1 inline size-4" />Elige un núcleo, una zona o arma un grupo para ver sus menciones, temas y emociones.</Reading>
      )}
      {scope === "cali" && <ZoneDetail ids={selIds} title={candName ? `${selTitle} · ${candName}` : selTitle} days={days} color={selColor} candidateId={cand} />}
      {scope === "colombia" && selDpto && <ZoneDetail ids={[selDpto]} title={by(zd)[selDpto]?.name || "Departamento"} days={days} candidateId={cand} />}
    </div>
  );
}
