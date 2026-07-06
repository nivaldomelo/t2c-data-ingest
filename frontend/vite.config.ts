import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      // Dev convenience: proxy API calls to the ingest backend.
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8010",
        changeOrigin: true,
      },
    },
  },
});
