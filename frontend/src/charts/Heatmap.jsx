import { useRef } from "react";
import { MousePointerClick } from "lucide-react";
import { Chart } from "./Chart";
import { BLUE, INK, MUTED } from "../lib/palette";
import { EMOTIONS_ORDER, cap } from "../lib/format";
import { Empty, Skeleton } from "../components/ui";
import { Quotes } from "../components/Feed";
import { useApi } from "../lib/useApi";

const emoLabel = (e) => (e === "sin emoción marcada" ? "Sin emoción" : cap(e));

/* Mapa de calor fila x emoción. `rows` = [{ name, emotions: { ira: n, ... } }]. Al tocar una celda
   avisa con (fila, emoción) para mostrar el apalancador concreto detrás de ese número. */
export function EmotionHeatmap({ rows, onCell, label }) {
  const cb = useRef(onCell);
  cb.current = onCell;
  const options = {
    chart: { type: "heatmap", events: onCell ? { dataPointSelection: (_e, _c, cfg) => {
      const row = rows[cfg.seriesIndex], emo = EMOTIONS_ORDER[cfg.dataPointIndex];
      if (row && emo) cb.current?.(row, emo);
    } } : {} },
    series: rows.map((r) => ({ name: cap(r.name), data: EMOTIONS_ORDER.map((e) => ({ x: emoLabel(e), y: r.emotions[e] || 0 })) })),
    colors: [BLUE],
    plotOptions: { heatmap: { radius: 6, colorScale: { ranges: [{ from: 0, to: 0, color: "#eef1f6" }] } } },
    stroke: { width: 3, colors: ["#fff"] },
    dataLabels: { enabled: true, style: { colors: [INK], fontWeight: 600 } },
    xaxis: { labels: { style: { colors: MUTED } }, position: "top" },
    legend: { show: false },
  };
  return <Chart options={options} height={Math.max(220, rows.length * 38 + 40)} label={label} clickable={!!onCell} minWidth={540} />;
}

/* Ejemplos (citas) detrás de una celda: carga al elegir una combinación. */
export function SamplesDetail({ title, url }) {
  const { data, loading } = useApi(url);
  if (!url) {
    return <Empty icon={MousePointerClick} className="mt-3 py-5">Toca una celda para ver qué está generando concretamente esa emoción.</Empty>;
  }
  return (
    <div className="mt-3 animate-fade-in rounded-2xl border border-slate-200 bg-white p-4">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[15px] font-semibold text-slate-900">{title}</h3>
        {data && <span className="text-sm text-slate-500">{data.length} ejemplo{data.length === 1 ? "" : "s"}</span>}
      </div>
      {loading ? <Skeleton className="h-20" /> : data?.length ? <Quotes rows={data} /> : <div className="py-3 text-sm text-slate-500">Sin ejemplos de muestra para esta combinación.</div>}
    </div>
  );
}

