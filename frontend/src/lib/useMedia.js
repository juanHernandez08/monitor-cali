import { useEffect, useState } from "react";

/* true mientras la ventana sea más angosta que `px` (teléfono por defecto). */
export function useNarrow(px = 640) {
  const q = `(max-width: ${px - 1}px)`;
  const [narrow, setNarrow] = useState(() => (typeof window !== "undefined" ? window.matchMedia(q).matches : false));
  useEffect(() => {
    const m = window.matchMedia(q);
    const on = () => setNarrow(m.matches);
    on();
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, [q]);
  return narrow;
}
