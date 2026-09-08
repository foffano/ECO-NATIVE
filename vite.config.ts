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
    proxy: {
      "/api": "http://127.0.0.1:18765",
      "/health": "http://127.0.0.1:18765"
    }
  },
  build: {
    outDir: "dist/frontend"
  }
});
