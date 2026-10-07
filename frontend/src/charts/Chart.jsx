import { useEffect, useMemo, useRef } from "react";
import ApexCharts from "apexcharts";
import { CRITICAL, GOOD, GRID, INK, MUTED, NEUTRAL_TONE, YELLOW } from "../lib/palette";

function deepMerge(a, b) {
  const out = { ...a };
  for (const k in b) {
    out[k] = a[k] && typeof a[k] === "object" && !Array.isArray(a[k]) && typeof b[k] === "object" && b[k] !== null && !Array.isArray(b[k])
      ? deepMerge(a[k], b[k]) : b[k];
  }
  return out;
}

const BASE = {
  chart: { fontFamily: '"Inter Variable", Inter, system-ui, sans-serif', foreColor: MUTED, toolbar: { show: false }, animations: { speed: 350 }, background: "transparent" },
  grid: { borderColor: GRID, strokeDashArray: 3 },
  tooltip: { theme: "light" },
};

/* Gráfica ApexCharts como componente. Se vuelve a dibujar solo cuando cambian los DATOS de las
   opciones (se compara su JSON; las funciones no cuentan), así que quien la usa no necesita
   memorizar nada. Las pestañas inactivas se desmontan: ya no hay que medir contenedores ocultos
   (el problema que obligaba a diferir gráficas en el tablero anterior). */
export function Chart({ options, height = 300, label, clickable, className }) {
  const ref = useRef(null);
  const latest = useRef(options);
  latest.current = options;
  const key = useMemo(() => JSON.stringify(options), [options]);
  useEffect(() => {
    if (!ref.current) return undefined;
    const merged = deepMerge(BASE, latest.current);
    merged.chart = { ...merged.chart, height };
    const c = new ApexCharts(ref.current, merged);
    c.render();
    return () => { try { c.destroy(); } catch { /* ya destruida */ } };
  }, [key, height]);
  return <div ref={ref} role="img" aria-label={label ? `Gráfica: ${label}` : undefined}
    className={className} style={{ height, minWidth: 0, cursor: clickable ? "pointer" : undefined }} />;
}

/* Alto según cuántas barras hay: 20+ candidatos en un cuadro fijo quedan ilegibles. */
export const barsHeight = (n) => Math.max(300, 40 + n * 32);

/* Barras horizontales, una sola serie. `colors` = array por barra o un color fijo. */
export function HBar({ categories, data, colors, labelFmt, onClick, label, minHeight }) {
  const h = Math.max(minHeight || 0, barsHeight(categories.length));
  const click = useRef(onClick);
  click.current = onClick;
  const options = {
    chart: { type: "bar", events: onClick ? { dataPointSelection: (_e, _c, cfg) => click.current?.(cfg.dataPointIndex) } : {} },
    series: [{ data }],
    xaxis: { categories, labels: { style: { colors: MUTED } } },
    yaxis: { labels: { maxWidth: 230 } },
    plotOptions: { bar: { horizontal: true, borderRadius: 5, borderRadiusApplication: "end", distributed: Array.isArray(colors), barHeight: "62%" } },
    colors: Array.isArray(colors) ? colors : [colors],
    dataLabels: { enabled: true, formatter: labelFmt || ((v) => v), style: { colors: [INK], fontWeight: 600 }, offsetX: 6 },
    legend: { show: false },
  };
  return <Chart options={options} height={h} label={label} clickable={!!onClick} />;
}

/* Barras horizontales apiladas al 100 % (ya como % 0-100). `colors` sigue el orden de `series`. */
export function HBar100({ categories, series, colors, label }) {
  const options = {
    chart: { type: "bar", stacked: true },
    series, xaxis: { categories, max: 100, labels: { formatter: (v) => Math.round(v) + "%" } },
    yaxis: { labels: { maxWidth: 230 } },
    plotOptions: { bar: { horizontal: true, borderRadius: 3, barHeight: "62%" } },
    colors,
    dataLabels: { enabled: true, formatter: (v) => (v >= 8 ? Math.round(v) + "%" : ""), style: { colors: ["#fff"], fontWeight: 600 } },
    legend: { position: "bottom" }, tooltip: { y: { formatter: (v) => v + "%" } },
  };
  return <Chart options={options} height={barsHeight(categories.length)} label={label} />;
}

export const SENT_COLORS = [GOOD, NEUTRAL_TONE, CRITICAL];

/* Medidor semicircular (0-100): verde si va bien, ámbar en zona media, rojo si va mal. */
export function Gauge({ value, height = 170 }) {
  const tone = value >= 60 ? GOOD : value >= 40 ? YELLOW : CRITICAL;
  const options = {
    chart: { type: "radialBar", sparkline: { enabled: true } },
    series: [value], colors: [tone],
    plotOptions: { radialBar: { startAngle: -90, endAngle: 90, hollow: { size: "64%" }, track: { background: "#e8ecf3", strokeWidth: "100%" },
      dataLabels: { name: { show: false }, value: { offsetY: -6, fontSize: "28px", fontWeight: 700, color: INK, formatter: (v) => v + "%" } } } },
    stroke: { lineCap: "round" },
  };
  // El semicírculo solo ocupa la mitad de arriba de su caja: se recorta la mitad vacía de abajo.
  return <div className="overflow-hidden" style={{ height: height * 0.66 }}><Chart options={options} height={height} label="Positividad" /></div>;
}
