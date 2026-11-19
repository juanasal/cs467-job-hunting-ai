// GenAI attribution:
// Developed with assistance from ChatGPT (OpenAI).
// Prompt: Configure the Vite development server to proxy API
// requests to the FastAPI backend for the JH-019 profile form.
// Reviewed and adapted for the CS467 Job Hunting AI project.

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
