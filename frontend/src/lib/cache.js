/* Caché en memoria por URL: se muestra lo ya guardado de una vez y se refresca detrás. */
export const cache = new Map(); // url -> { data, at, token }
export const inflight = new Map();
export function clearCache() { cache.clear(); inflight.clear(); }
