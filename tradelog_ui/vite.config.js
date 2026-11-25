import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built into the app's static folder: Streamlit serves it at /app/static/tl2/ (same origin as the app, so the page
// can take the signed-in pass from the main page and its colours from the UI Colours settings).
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "../static/tl2", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 600 },
});
