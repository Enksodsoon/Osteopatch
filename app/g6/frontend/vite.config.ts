import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /v1 to the local backend (127.0.0.1 only).
//
// VITE_API_TARGET lets scripts/e2e_ui.py point this at a throwaway backend on a
// free port. That matters: 8137 is a fixed port, and a stale server left running
// there will happily answer the SPA while the intended backend sits elsewhere —
// so a test run would silently exercise the wrong code.
const apiTarget = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8137";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/v1": apiTarget,
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Playwright browser specs live under e2e/ and are run by scripts/e2e_ui.py.
    // Keep Vitest focused on component/unit specs so the two runners never
    // attempt to execute each other's test API.
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
