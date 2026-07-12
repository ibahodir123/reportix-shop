import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// В dev /api и /admin проксируются на backend-контейнер, чтобы куки-сессия
// и CSRF работали в рамках одного origin.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: "http://backend:8000", changeOrigin: true },
      "/admin": { target: "http://backend:8000", changeOrigin: true },
      "/static": { target: "http://backend:8000", changeOrigin: true },
    },
  },
});
