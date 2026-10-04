import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server binds 127.0.0.1 only and proxies the enterprise API (port 8140).
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5174,
    proxy: {
      "/v1": "http://127.0.0.1:8140",
      "/api": "http://127.0.0.1:8140",
      "/auth": "http://127.0.0.1:8140",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
