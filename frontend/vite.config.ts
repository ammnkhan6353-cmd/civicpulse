import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// No API URL is baked into the bundle. The app only ever calls relative /api/...
// paths; nginx (Compose) or the Ingress (Kubernetes) routes them to the backend.
// For `npm run dev` the Vite dev server proxies /api the same way.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.tsx"],
  },
});
