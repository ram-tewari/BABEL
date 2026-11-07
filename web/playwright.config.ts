import { defineConfig } from "@playwright/test";

const PORT = Number(process.env.BABEL_E2E_PORT ?? 18733);

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: `http://127.0.0.1:${PORT}` },
  webServer: {
    // fresh, throwaway library for every run
    command: `rm -rf .e2e-data && BABEL_DATA_DIR=.e2e-data BABEL_PROVIDERS=none ../.venv/bin/babel serve --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/status`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
