import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development, /api/* is proxied to the FastAPI server, so no CORS setup is needed locally.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { chunkSizeWarningLimit: 900 }, // Recharts alone is ~500 kB; fine for this app
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
