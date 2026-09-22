// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

const API_PROXY = {
  "/api": { target: "http://localhost:8000", rewrite: (p: string) => p.replace(/^\/api/, "") },
};

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Melliscribe",
        short_name: "Melliscribe",
        start_url: "/",
        display: "standalone",
        background_color: "#fffaf0",
        theme_color: "#b8860b",
        icons: [],
      },
    }),
  ],
  server: { proxy: API_PROXY },
  preview: { proxy: API_PROXY },
  test: {
    environment: "jsdom",
    include: ["tests/unit/**/*.test.ts", "tests/unit/**/*.test.tsx"],
    setupFiles: ["tests/unit/setup.ts"],
  },
});
