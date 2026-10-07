/* fetch con manejo de errores: antes un 401/500 terminaba en "Unexpected token" en consola y la
   pestaña quedaba a medio pintar sin aviso. */
const listeners = new Set();
export function onNotify(fn) { listeners.add(fn); return () => listeners.delete(fn); }
export function notify(msg, kind = "info") { listeners.forEach((fn) => fn({ msg, kind, id: Date.now() })); }

export async function getJSON(url, { signal } = {}) {
  const r = await fetch(url, { credentials: "same-origin", signal });
  if (r.status === 401) { notify("La sesión expiró: recarga la página para volver a entrar.", "error"); throw new Error("401"); }
  if (!r.ok) { notify(`No se pudo cargar ${url.split("?")[0]} (${r.status}).`, "error"); throw new Error(String(r.status)); }
  return r.json();
}
/* Todo POST lleva X-Requested-With: el servidor rechaza sin ella (protección CSRF). */
export async function post(url, body) {
  const opts = { method: "POST", credentials: "same-origin", headers: { "X-Requested-With": "monitor" } };
  if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  return fetch(url, opts);
}
