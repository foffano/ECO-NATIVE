import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import pkg from "./package.json";

export default defineConfig({
  base: "./",
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
    __APP_NAME__: JSON.stringify(pkg.build?.productName ?? "ECO Native Studio"),
  },
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    // The shorthand form would rewrite Host to the backend's, and the backend
    // refuses writes whose Origin differs from Host; keep the browser's Host.
    proxy: {
      "/api": { target: "http://127.0.0.1:18765", changeOrigin: false },
      "/health": { target: "http://127.0.0.1:18765", changeOrigin: false }
    }
  },
  build: {
    outDir: "dist/frontend"
  }
});
