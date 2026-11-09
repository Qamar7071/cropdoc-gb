import { defineConfig, devices } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// The e2e run starts the REAL backend (with the real model) serving the built frontend,
// with a fresh empty database in a temporary folder.
const PORT = Number(process.env.E2E_PORT ?? 8765);
const PYTHON = process.env.CROPDOC_PYTHON ?? "../.venv/bin/python";
const dataDir = mkdtempSync(join(tmpdir(), "cropdoc-e2e-"));

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: "off" },
  webServer: {
    command: `${PYTHON} ../backend/run.py --no-browser --port ${PORT}`,
    env: { CROPDOC_DATA_DIR: join(dataDir, "app"), CROPDOC_INBOX_DIR: join(dataDir, "inbox") },
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
