import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The new MarketNavi app (beta): a static site at marketnavi.ai/new/, built and copied there by
// .github/workflows/deploy-new-app.yml. It talks to the same database as the classic app, with the member's own
// sign-in, so the database's row rules apply exactly as they do today.
export default defineConfig({
  plugins: [react()],
  base: "/new/",
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 900 },
});
