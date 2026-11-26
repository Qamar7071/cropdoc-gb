/* End-to-end tests against the REAL backend + model, plus screenshots at 1440 / 768 / 390 px
   saved to results/ui/ for comparison with the design references. */
import { expect, test, type Browser, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOTS = resolve(HERE, "../../results/ui");
const EXAMPLE = resolve(HERE, "../public/examples/early-blight.jpg");
const FIELD_PHOTO = resolve(HERE, "fixtures/field-low-confidence.jpg");
const WIDTHS = [
  { name: "1440", width: 1440, height: 900 },
  { name: "768", width: 768, height: 1024 },
  { name: "390", width: 390, height: 844 },
];

mkdirSync(SHOTS, { recursive: true });
test.describe.configure({ mode: "serial" });

async function openPage(browser: Browser, width: number, height: number): Promise<Page> {
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 2 });
  return context.newPage();
}

/* Full-page captures keep fixed elements at the first screen's position; for review screenshots we pin
   the phone bottom-nav to the bottom of the page instead (no effect on the real app). */
async function pinMobileNav(page: Page) {
  await page.addStyleTag({ content: "body{position:relative} nav.fixed.bottom-0{position:absolute !important}" });
}

async function shot(page: Page, name: string) {
  await page.waitForLoadState("networkidle");
  await pinMobileNav(page);
  await page.screenshot({ path: `${SHOTS}/${name}.jpg`, fullPage: true, type: "jpeg", quality: 80 });
}

async function analyze(page: Page, file: string) {
  await page.getByTestId("file-input").setInputFiles(file);
  await page.getByTestId("analyze-button").click();
}

test("empty states before any scan (scanner, dashboard, history) and static pages", async ({ browser }) => {
  for (const { name, width, height } of WIDTHS) {
    const page = await openPage(browser, width, height);
    await page.goto("/scanner");
    await expect(page.getByTestId("example-early-blight")).toBeVisible();
    await expect(page.getByTestId("result-empty")).toBeVisible();
    await shot(page, `scanner-empty-${name}`);

    await page.goto("/dashboard");
    await expect(page.getByTestId("empty-state")).toContainText("No scans yet");
    await expect(page.getByTestId("stat-tiles")).toHaveCount(0);
    await shot(page, `dashboard-empty-${name}`);

    await page.goto("/library");
    await expect(page.getByTestId("library-grid")).toBeVisible();
    await shot(page, `library-${name}`);

    await page.goto("/");
    await expect(page.getByTestId("key-facts")).toBeVisible();
    await shot(page, `home-${name}`);

    await page.goto("/field-intelligence");
    await expect(page.getByTestId("section-field_gap")).toContainText("PENDING");
    await shot(page, `field-intelligence-${name}`);
    await page.context().close();
  }
});

test("upload → prediction + Grad-CAM → saved in history → visible on dashboard", async ({ browser }) => {
  const page = await openPage(browser, 1440, 900);
  await page.goto("/scanner");
  await analyze(page, EXAMPLE);
  await expect(page.getByTestId("disease-name")).toHaveText("Early blight");
  await expect(page.getByTestId("gradcam-thumb")).toBeVisible();
  await expect(page.getByTestId("disclaimer")).toBeVisible();
  await expect(page.getByTestId("saved-indicator")).toBeVisible();

  await page.getByTestId("gradcam-thumb").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await shot(page, "scanner-gradcam-modal-1440");
  await page.keyboard.press("Escape");

  await page.goto("/history");
  await expect(page.getByTestId("scan-row").first()).toContainText("Early blight");

  await page.goto("/dashboard");
  await expect(page.getByTestId("stat-tiles")).toContainText("1");
  await expect(page.getByText("Early blight (Potato)")).toBeVisible();
  await page.context().close();
});

test("scanner loading, result and low-confidence states at 3 widths", async ({ browser }) => {
  for (const { name, width, height } of WIDTHS) {
    const page = await openPage(browser, width, height);
    await page.goto("/scanner");
    await page.route("**/api/predict", async (route) => {
      await new Promise((resolveDelay) => setTimeout(resolveDelay, 2500)); // hold the real request to show the skeleton
      await route.continue();
    });
    await analyze(page, EXAMPLE);
    await expect(page.getByTestId("result-loading")).toBeVisible();
    await pinMobileNav(page);
    await page.screenshot({ path: `${SHOTS}/scanner-loading-${name}.jpg`, fullPage: true, type: "jpeg", quality: 80 });
    await expect(page.getByTestId("disease-name")).toBeVisible({ timeout: 30_000 });
    await page.unroute("**/api/predict");
    await shot(page, `scanner-result-${name}`);

    await analyze(page, FIELD_PHOTO);
    await expect(page.getByTestId("uncertain-warning")).toBeVisible();
    await expect(page.getByTestId("disclaimer")).toBeVisible();
    await shot(page, `scanner-lowconf-${name}`);
    await page.context().close();
  }
});

test("history and dashboard with real saved scans, feedback flow", async ({ browser }) => {
  for (const { name, width, height } of WIDTHS) {
    const page = await openPage(browser, width, height);
    await page.goto("/history");
    await expect(page.getByTestId("scan-row").first()).toBeVisible();
    await shot(page, `history-${name}`);
    await page.goto("/dashboard");
    await expect(page.getByTestId("stat-tiles")).toBeVisible();
    await shot(page, `dashboard-${name}`);
    await page.context().close();
  }
  const page = await openPage(browser, 390, 844);
  await page.goto("/history");
  await page.getByTestId("scan-row").first().getByRole("link").first().click();
  await expect(page.getByTestId("scan-disease")).toBeVisible();
  await page.getByRole("button", { name: "Yes" }).click();
  await expect(page.getByText("Thank you!")).toBeVisible();
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByTestId("compare")).toBeVisible();
  await shot(page, "history-detail-390");
  await page.context().close();
});

test("Urdu toggle switches to right-to-left", async ({ browser }) => {
  const page = await openPage(browser, 1440, 900);
  await page.goto("/scanner");
  await page.getByTestId("lang-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ur");
  await analyze(page, EXAMPLE);
  await expect(page.getByTestId("disease-name")).toBeVisible();
  await shot(page, "scanner-result-ur-1440");
  await page.context().close();

  const phone = await openPage(browser, 390, 844);
  await phone.goto("/history");
  await phone.getByTestId("lang-toggle").click();
  await expect(phone.locator("html")).toHaveAttribute("dir", "rtl");
  await shot(phone, "history-ur-390");
  await phone.context().close();
});

test("large phone photos are shrunk in the browser before upload (hosts limit requests to 4.5 MB)", async ({ browser }) => {
  const big = join(mkdtempSync(join(tmpdir(), "cropdoc-big-")), "phone-photo.jpg");
  execFileSync(process.env.CROPDOC_PYTHON ?? "../.venv/bin/python", [resolve(HERE, "make_big_photo.py"), EXAMPLE, big]);
  expect(statSync(big).size).toBeGreaterThan(3.5 * 1024 * 1024);

  const page = await openPage(browser, 1280, 900);
  // record the size of the photo the app actually sends (runs in the browser)
  await page.addInitScript(() => {
    type Body = { get?: (name: string) => { size?: number } | null };
    const scope = globalThis as unknown as {
      fetch: (input: unknown, init?: { body?: Body }) => Promise<unknown>;
      sentBytes?: number;
    };
    const original = scope.fetch.bind(globalThis);
    scope.fetch = (input, init) => {
      const image = typeof init?.body?.get === "function" ? init.body.get("image") : null;
      if (image && typeof image.size === "number") scope.sentBytes = image.size;
      return original(input, init);
    };
  });
  await page.goto("/scanner");
  await page.getByTestId("file-input").setInputFiles(big);
  await page.getByTestId("analyze-button").click();
  await expect(page.getByTestId("disease-name")).toBeVisible({ timeout: 30_000 });
  const sentBytes = await page.evaluate(() => (globalThis as unknown as { sentBytes?: number }).sentBytes ?? 0);
  expect(sentBytes).toBeGreaterThan(0);
  expect(sentBytes).toBeLessThanOrEqual(3.5 * 1024 * 1024);
  await page.context().close();
});
