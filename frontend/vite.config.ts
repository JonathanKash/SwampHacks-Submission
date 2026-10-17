import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API runs on 8010 locally (8000 was taken on the dev machine); override with BACKEND.
const backend = process.env.BACKEND ?? "http://localhost:8010";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
  },
  server: {
    proxy: {
      "/api": backend,
      "/images": backend,
      "/thumbs": backend,
    },
  },
});
