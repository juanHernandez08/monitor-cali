export const CARLOS = "Carlos Arias";

export const SRC = { google_news: "Prensa", rss: "Prensa", reddit: "Reddit", youtube: "YouTube", social: "Instagram / Facebook", google_cse: "Redes", serp: "Redes" };
export const SRC_LABEL = { google_news: "Prensa", rss: "Prensa", reddit: "Reddit", youtube: "YouTube", social: "Instagram / Facebook", instagram: "Instagram", facebook: "Facebook", x: "X", google_cse: "Redes (búsqueda)", serp: "Redes (búsqueda)" };
export const LABEL = { negative: "Negativo", positive: "Positivo", neutral: "Neutral" };
export const KIND = { post: "Post", video: "Video", comments: "Publicación", news: "Nota" };

export const CATEGORY_OPTIONS = ["seguridad y convivencia", "movilidad y transporte", "terremoto y reconstrucción", "servicios públicos",
  "salud pública", "educación", "economía y empleo", "vivienda", "medioambiente y gestión de riesgo", "cultura y eventos", "deporte",
  "corrupción y gobierno", "política y elecciones", "orden público y protestas", "infraestructura y obras", "animales", "otro"];
export const EMOTION_OPTIONS = [["ira", "Ira"], ["miedo", "Miedo"], ["asco", "Asco / repulsión"], ["tristeza", "Tristeza"],
  ["felicidad", "Felicidad"], ["sorpresa", "Sorpresa"], ["sin emoción marcada", "Sin emoción marcada"]];
export const EMOTIONS_ORDER = ["ira", "miedo", "asco", "tristeza", "felicidad", "sorpresa", "sin emoción marcada"];

export const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
export const pct = (n, t) => (t ? Math.round((n / t) * 100) : 0);
export const scored = (r) => r.positive + r.negative + r.neutral;
export const share = (r, k) => pct(r[k], scored(r));
export const ordinal = (i) => `${i + 1}.º`;
export const fmtNum = (x) => (x || 0).toLocaleString("es-CO");
export const initials = (name) => String(name || "").split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

/* Para los tooltips de ApexCharts (HTML en texto): todo lo que viene de la base se escapa. */
export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
/* Solo http/https: nunca javascript: ni data:. Devuelve "" si no es válida. */
export function safeUrl(u) {
  if (!u) return "";
  try { const url = new URL(String(u), location.origin); return /^https?:$/.test(url.protocol) ? url.href : ""; }
  catch { return ""; }
}
export function clip(s, n) { const t = String(s ?? ""); return t.length > n ? t.slice(0, n) + "…" : t; }

const asDate = (iso) => new Date(String(iso).endsWith("Z") ? iso : iso + "Z");
export function ago(iso) {
  if (!iso) return "sin datos";
  const m = Math.round((Date.now() - asDate(iso)) / 60000);
  if (m < 1) return "hace un momento";
  return m < 60 ? `hace ${m} min` : m < 1440 ? `hace ${Math.round(m / 60)} h` : `hace ${Math.round(m / 1440)} d`;
}
export function fmtDate(iso) {
  if (!iso) return "";
  return asDate(iso).toLocaleString("es-CO", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}
export const srcName = (m) => (m.platform ? (SRC_LABEL[m.platform] || m.platform) : (SRC[m.source_type] || m.source));
/* Google News y RSS son ambos "Prensa": sin esto salían como dos chips con el mismo nombre. */
export function mergedSources(sources = {}) {
  const out = {};
  for (const [src, n] of Object.entries(sources)) {
    const label = SRC_LABEL[src] || SRC[src] || src;
    out[label] = (out[label] || 0) + n;
  }
  return out;
}
/* "sin emoción marcada" es una clasificación real (texto informativo), no un hueco en los datos. */
export function emotionLine(m) {
  if (!m.emotion) return null;
  const marked = m.emotion !== "sin emoción marcada";
  const text = marked ? (m.emotion_nuance ? `${m.emotion} (${m.emotion_nuance})` : m.emotion) : "sin emoción marcada (texto neutro o informativo)";
  return { text, lever: marked ? m.apalancador : null };
}
