import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { useApp } from "../lib/app";
import { useApi } from "../lib/useApi";
import { Loading, Segmented } from "./ui";
import { FeedList } from "./Feed";

const TONE = { "": "menciones", positive: "menciones positivas", neutral: "menciones neutrales", negative: "menciones negativas" };

/* Ventana con las menciones que hay detrás de un número del Hero (281 menciones, 234 positivas...).
   Misma lista de publicaciones que el Perfil, filtrada por sentimiento; se puede cambiar el sentimiento
   sin cerrarla. Va en un portal: el Hero tiene overflow/transform y recortaría una capa fija. */
export function MentionsModal({ r, initial = "", onClose }) {
  const { days } = useApp();
  const [label, setLabel] = useState(initial);
  const p = new URLSearchParams({ candidate_id: r.candidate_id, days, limit: 300 });
  if (label) p.set("label", label);
  const feed = useApi(`/api/feed?${p}`);

  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") closeRef.current(); };
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, []);

  // Lo que se cuenta son menciones (publicaciones o notas y comentarios), no filas: así el total cuadra con el número del Hero.
  const rows = feed.data;
  const mentions = rows ? rows.reduce((a, x) => a + (x.id != null && (!label || x.label === label) ? 1 : 0) + (x.comments?.length || 0), 0) : null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/60 p-3 backdrop-blur-sm sm:p-8"
      onClick={onClose} role="presentation">
      <div role="dialog" aria-modal="true" aria-label={`${r.name}: ${TONE[label]}`} onClick={(e) => e.stopPropagation()}
        className="w-full max-w-4xl rounded-3xl bg-slate-50 p-4 shadow-2xl ring-1 ring-slate-200 sm:p-6">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-lg font-bold tracking-tight text-slate-900 sm:text-xl">{r.name}</h3>
            <p className="mt-0.5 text-[13px] text-slate-500">
              {mentions == null ? "Cargando…" : <><b className="text-slate-700">{mentions}</b> {TONE[label]} · últimos {days} días · una fila por publicación; despliega sus comentarios</>}
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Cerrar" autoFocus
            className="grid size-9 shrink-0 place-items-center rounded-xl bg-white text-slate-500 ring-1 ring-slate-200 transition hover:bg-slate-100 hover:text-slate-800">
            <X className="size-5" />
          </button>
        </div>
        <div className="mt-4">
          <Segmented size="sm" value={label} onChange={setLabel} label="Sentimiento"
            options={[["", `Todas (${r.mentions})`], ["positive", `Positivas (${r.positive})`], ["neutral", `Neutrales (${r.neutral})`], ["negative", `Negativas (${r.negative})`]]} />
        </div>
        <div className="mt-4">
          {!rows ? <Loading rows={4} /> : <FeedList rows={rows} empty="Sin menciones con este filtro en el período." />}
        </div>
      </div>
    </div>,
    document.body,
  );
}
