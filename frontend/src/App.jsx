import { Suspense, lazy } from "react";
import { AppProvider, useApp } from "./lib/app";
import { Shell } from "./components/Shell";
import { Toaster, PanelSkeleton } from "./components/ui";
import Resumen from "./pages/Resumen";
import Perfil from "./pages/Perfil";

/* Las pestañas se cargan bajo demanda: el primer paso solo baja el Resumen. */
const PAGES = {
  resumen: Resumen,
  perfil: Perfil,
  candidatos: lazy(() => import("./pages/Candidatos")),
  publicaciones: lazy(() => import("./pages/Publicaciones")),
  meta: lazy(() => import("./pages/Meta")),
  analisis: lazy(() => import("./pages/Analisis")),
  ciudad: lazy(() => import("./pages/Ciudad")),
  historico: lazy(() => import("./pages/Historico")),
  agenda: lazy(() => import("./pages/Agenda")),
  reporte: lazy(() => import("./pages/Reporte")),
};

function Router() {
  const { route } = useApp();
  const Page = PAGES[route.tab] || Resumen;
  return (
    <Suspense fallback={<div className="grid gap-5"><PanelSkeleton /><PanelSkeleton /></div>}>
      <Page key={route.tab + (route.profileId || "")} />
    </Suspense>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Shell><Router /></Shell>
      <Toaster />
    </AppProvider>
  );
}
