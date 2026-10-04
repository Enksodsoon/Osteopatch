import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /v1 to the local backend (127.0.0.1 only).
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/v1": "http://127.0.0.1:8137",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
