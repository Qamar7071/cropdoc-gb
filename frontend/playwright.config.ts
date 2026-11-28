import { defineConfig, devices } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// The e2e run starts the REAL backend (with the real model) serving the built frontend,
// with a fresh empty database in a temporary folder.
const PORT = Number(process.env.E2E_PORT ?? 8765);
const PYTHON = process.env.CROPDOC_PYTHON ?? "../.venv/bin/python";
const dataDir = mkdtempSync(join(tmpdir(), "cropdoc-e2e-"));

// Fake webcam for the live-scanner test: a real PlantVillage test photo shown as a looping video.
const fakeCamera = join(dataDir, "leaf.y4m");
execFileSync(PYTHON, ["e2e/make_fake_camera.py", "public/examples/early-blight.jpg", fakeCamera]);
const fakePhoneCamera = join(dataDir, "leaf-portrait.y4m");
execFileSync(PYTHON, ["e2e/make_fake_camera.py", "public/examples/early-blight.jpg", fakePhoneCamera, "720", "1280", "contain"]);
const cameraArgs = (file: string) => [
  "--use-fake-device-for-media-stream",
  "--use-fake-ui-for-media-stream",
  `--use-file-for-fake-video-capture=${file}`,
];

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: "off" },
  webServer: {
    command: `${PYTHON} ../backend/run.py --no-browser --port ${PORT}`,
    // no AI key and no weather calls in tests: the assistant answers from the knowledge base, weather says "off"
    env: { CROPDOC_DATA_DIR: join(dataDir, "app"), CROPDOC_INBOX_DIR: join(dataDir, "inbox"), ANTHROPIC_API_KEY: "", CROPDOC_WEATHER: "off" },
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] }, testIgnore: /live\.spec\.ts/ },
    {
      name: "live-camera",
      testMatch: /live\.spec\.ts/,
      grepInvert: /@phone/,
      use: { ...devices["Desktop Chrome"], permissions: ["camera"], launchOptions: { args: cameraArgs(fakeCamera) } },
    },
    {
      // a phone held upright: portrait camera frames
      name: "live-camera-phone",
      testMatch: /live\.spec\.ts/,
      grep: /@phone/,
      use: { ...devices["Desktop Chrome"], permissions: ["camera"], launchOptions: { args: cameraArgs(fakePhoneCamera) } },
    },
  ],
});
