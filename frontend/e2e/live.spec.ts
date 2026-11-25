/* Live scanner end-to-end: a fake webcam shows a real PlantVillage test photo (early blight);
   the REAL backend + model answer each frame. Screenshots go to results/ui/. */
import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOTS = resolve(HERE, "../../results/ui");
mkdirSync(SHOTS, { recursive: true });
test.describe.configure({ mode: "serial" });

test("live scan: camera frames get a stable answer, then a saved full report", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, permissions: ["camera"] });
  const page = await context.newPage();
  const frames: number[] = [];
  page.on("response", (response) => {
    if (response.url().endsWith("/api/predict/live")) frames.push(response.status());
  });

  await page.goto("/live");
  await expect(page.getByRole("heading", { name: "Live Scan" })).toBeVisible();
  await expect(page.getByTestId("live-video")).toBeVisible();

  // several frames are sent automatically and the answer locks on the photo's disease
  await expect(page.getByTestId("live-disease")).toHaveText("Early blight", { timeout: 30_000 });
  await expect(page.getByTestId("live-message")).toContainText("Early blight");
  await expect(page.getByTestId("live-warning")).toHaveCount(0); // locked = confident on agreeing frames
  await expect(page.getByTestId("live-stability")).toBeVisible();
  await expect(page.getByTestId("live-heatmap")).toBeVisible();
  await expect(page.getByTestId("disclaimer")).toBeVisible();
  expect(frames.length).toBeGreaterThanOrEqual(2);
  expect(frames.every((status) => status === 200)).toBe(true);
  await page.waitForTimeout(600); // let the sweep line move off the edge for a clean picture
  await page.screenshot({ path: `${SHOTS}/live-1440.jpg`, type: "jpeg", quality: 80 });

  // pausing stops sending frames
  await page.getByTestId("live-pause").click();
  await expect(page.getByTestId("live-message")).toHaveText("Paused");
  const pausedAt = frames.length;
  await page.waitForTimeout(1500);
  expect(frames.length - pausedAt).toBeLessThanOrEqual(1); // at most one frame already in flight
  await page.getByTestId("live-pause").click();

  // the round button saves a full report (with Grad-CAM) to history and opens it
  await page.getByTestId("live-capture").click();
  await page.waitForURL(/\/history\/[0-9a-f]{32}$/, { timeout: 30_000 });
  await expect(page.getByText("Early blight").first()).toBeVisible();
  await expect(page.getByTestId("disclaimer")).toBeVisible();
  await context.close();
});

test("live scan on a phone screen (390 px) @phone", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    permissions: ["camera"],
  });
  const page = await context.newPage();
  await page.goto("/");
  await page.getByTestId("mobile-live").click();
  await expect(page).toHaveURL(/\/live$/);
  await expect(page.getByTestId("live-disease")).toHaveText("Early blight", { timeout: 30_000 });
  await expect(page.getByTestId("live-message")).toContainText("Early blight"); // locked, not just a best guess
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${SHOTS}/live-390.jpg`, type: "jpeg", quality: 80 });
  // scrolling down shows the details and the disclaimer below the camera
  await page.getByTestId("disclaimer").scrollIntoViewIfNeeded();
  await expect(page.getByTestId("disclaimer")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/live-390-details.jpg`, type: "jpeg", quality: 80 });
  await context.close();
});

test("without camera access the page offers a photo instead and still answers", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1024, height: 800 }, permissions: [] });
  const page = await context.newPage();
  // simulate a browser that refuses the camera
  await page.addInitScript(() => {
    const nav = (globalThis as unknown as { navigator: { mediaDevices: { getUserMedia: () => Promise<never> } } }).navigator;
    nav.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("denied", "NotAllowedError"));
  });
  await page.goto("/live");
  await expect(page.getByTestId("live-camera-problem")).toContainText("Camera permission is blocked");
  await page.getByTestId("live-photo-input").setInputFiles(resolve(HERE, "../public/examples/early-blight.jpg"));
  await expect(page.getByTestId("live-disease")).toHaveText("Early blight", { timeout: 30_000 });
  await context.close();
});
