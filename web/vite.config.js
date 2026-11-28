import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The MarketNavi app: a static site, built and copied to HostGator by .github/workflows/deploy-new-app.yml. Built
// twice: for marketnavi.ai/new/ (base /new/, the default) and for app.marketnavi.ai (VITE_BASE=/). It talks to the same database as the classic app, with the member's own
// sign-in, so the database's row rules apply exactly as they do today.
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE || "/new/",
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 900 },
});
