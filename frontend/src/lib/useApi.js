import { useEffect, useState } from "react";
import { getJSON } from "./api";
import { cache, inflight } from "./cache";
import { useApp } from "./app";

/* Datos de la API con "mostrar lo guardado y refrescar detrás": al volver a una pestaña se ve de
   una vez lo último que se tenía, y se vuelve a pedir si pasaron más de 2 minutos o si alguien
   tocó "Actualizar". Las peticiones iguales en vuelo se comparten. `url` null = no pedir aún. */
const STALE_MS = 120000;

function fetchOnce(url, token) {
  if (inflight.has(url)) return inflight.get(url);
  const p = getJSON(url).then((data) => { cache.set(url, { data, at: Date.now(), token }); return data; })
    .finally(() => inflight.delete(url));
  inflight.set(url, p);
  return p;
}

function initial(url) {
  const hit = url ? cache.get(url) : null;
  return { url, data: hit?.data, error: null, loading: !!url && !hit };
}

export function useApi(url) {
  const { refreshToken } = useApp();
  const [state, setState] = useState(() => initial(url));

  useEffect(() => {
    if (!url) { setState({ url, data: undefined, error: null, loading: false }); return undefined; }
    const cached = cache.get(url);
    setState(cached ? { url, data: cached.data, error: null, loading: false } : { url, data: undefined, error: null, loading: true });
    if (cached && cached.token === refreshToken && Date.now() - cached.at < STALE_MS) return undefined;
    let cancelled = false;
    fetchOnce(url, refreshToken)
      .then((data) => { if (!cancelled) setState({ url, data, error: null, loading: false }); })
      .catch((error) => { if (!cancelled) setState((s) => ({ ...s, url, error, loading: false })); });
    return () => { cancelled = true; };
  }, [url, refreshToken]);

  // Si el período cambia, no se enseña el dato de la URL anterior como si fuera el nuevo.
  return state.url === url ? state : { url, data: undefined, error: null, loading: !!url };
}

/* Varias consultas a la vez: loading mientras falte alguna; error si falla alguna. */
export function useApis(urls) {
  const results = urls.map((u) => useApi(u)); // eslint-disable-line react-hooks/rules-of-hooks -- cantidad fija por llamada
  return {
    data: results.map((r) => r.data),
    loading: results.some((r) => r.loading),
    error: results.find((r) => r.error)?.error || null,
    ready: results.every((r) => r.data !== undefined),
  };
}
