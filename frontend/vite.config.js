import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// El build sale directo a src/static/app, que FastAPI ya sirve en /static (detrás del mismo login
// que la API). En desarrollo (npm run dev) las llamadas /api se reenvían a uvicorn en el 8000.
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/app/" : "/",
  plugins: [react(), tailwindcss()],
  build: { outDir: "../src/static/app", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 900 },
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000", "/health": "http://127.0.0.1:8000", "/static/avatars": "http://127.0.0.1:8000" } },
}));
