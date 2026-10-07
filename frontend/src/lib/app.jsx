import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { clearCache } from "./cache";

export const TABS = ["resumen", "candidatos", "publicaciones", "meta", "analisis", "ciudad", "historico", "agenda", "reporte"];
export const PERIODS = [[1, "24 h"], [7, "7 días"], [30, "30 días"], [60, "60 días"], [90, "90 días"], [180, "180 días"]];

const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

function parseHash() {
  const h = location.hash.slice(1);
  if (h.startsWith("perfil/")) return { tab: "perfil", profileId: Number(h.split("/")[1]) || null };
  return { tab: TABS.includes(h) ? h : "resumen", profileId: null };
}

export function AppProvider({ children }) {
  const [days, setDaysState] = useState(() => {
    try { const s = Number(localStorage.getItem("monitor.days")); if (PERIODS.some(([d]) => d === s)) return s; } catch { /* modo privado */ }
    return 30;
  });
  const [refreshToken, setRefreshToken] = useState(0);
  const [route, setRoute] = useState(() => {
    // Link directo desde una notificación (?perfil=<candidate_id>): abre de una vez ese perfil.
    const id = Number(new URLSearchParams(location.search).get("perfil"));
    if (id) { history.replaceState(null, "", `${location.pathname}#perfil/${id}`); return { tab: "perfil", profileId: id }; }
    return parseHash();
  });
  const [lastTab, setLastTab] = useState("resumen");

  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => { window.scrollTo({ top: 0 }); }, [route.tab, route.profileId]);

  const setDays = useCallback((d) => {
    setDaysState(d);
    try { localStorage.setItem("monitor.days", String(d)); } catch { /* sin almacenamiento */ }
  }, []);
  const refresh = useCallback(() => { clearCache(); setRefreshToken((t) => t + 1); }, []);

  // Auto-actualización: solo si la ventana está a la vista; cada pestaña vuelve a pedir lo suyo.
  useEffect(() => {
    const id = setInterval(() => { if (document.visibilityState === "visible") setRefreshToken((t) => t + 1); }, 120000);
    return () => clearInterval(id);
  }, []);

  const go = useCallback((tab) => {
    if (tab !== "perfil") setLastTab(tab);
    history.replaceState(null, "", `#${tab}`);
    setRoute({ tab, profileId: null });
  }, []);
  const openProfile = useCallback((id) => {
    setLastTab((t) => (route.tab === "perfil" ? t : route.tab));
    history.replaceState(null, "", `#perfil/${id}`);
    setRoute({ tab: "perfil", profileId: id });
  }, [route.tab]);

  const value = useMemo(() => ({ days, setDays, refreshToken, refresh, route, go, openProfile, lastTab }),
    [days, setDays, refreshToken, refresh, route, go, openProfile, lastTab]);
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export const periodLabel = (d) => (d === 1 ? "las últimas 24 horas" : `los últimos ${d} días`);
