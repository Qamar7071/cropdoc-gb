/* Farmer features end-to-end (real backend + model): dashboard, bilingual report, treatment guide,
   assistant (knowledge-base mode: no AI key in tests), crops, tips and the "take another photo" gate. */
import { expect, test, type Browser, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOTS = resolve(HERE, "../../results/ui");
const EXAMPLE = resolve(HERE, "../public/examples/early-blight.jpg");
mkdirSync(SHOTS, { recursive: true });
test.describe.configure({ mode: "serial" });

async function openPage(browser: Browser, width: number, height: number): Promise<Page> {
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 2 });
  return context.newPage();
}

async function shot(page: Page, name: string) {
  await page.waitForLoadState("networkidle");
  await page.addStyleTag({ content: "body{position:relative} nav.fixed.bottom-0{position:absolute !important} header.sticky{position:relative !important}" });
  await page.screenshot({ path: `${SHOTS}/${name}.jpg`, fullPage: true, type: "jpeg", quality: 78 });
}

test("farmer dashboard: big tiles, weather card, tips, language switch", async ({ browser }) => {
  for (const [w, h] of [[1440, 900], [390, 844]] as const) {
    const page = await openPage(browser, w, h);
    await page.goto("/");
    const dashboard = page.getByTestId("farmer-dashboard");
    for (const id of ["home-live-cta", "home-cta", "tile-history", "tile-crops", "tile-assistant", "tile-tips", "tile-language"]) {
      await expect(dashboard.getByTestId(id)).toBeVisible();
    }
    await expect(page.getByTestId("weather-card")).toBeVisible();
    await expect(page.getByTestId("tip").first()).toBeVisible();
    await shot(page, `home-dashboard-${w}`);
    if (w === 390) {
      await page.getByTestId("tile-language").click();
      await expect(page.locator("html")).toHaveAttribute("lang", "ur");
      await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
      await shot(page, "home-dashboard-ur-390");
    }
    await page.context().close();
  }
});

test("bilingual plant analysis report, treatment guide and assistant hand-off", async ({ browser }) => {
  for (const [w, h] of [[1440, 900], [390, 844]] as const) {
    const page = await openPage(browser, w, h);
    await page.goto("/scanner");
    await page.getByTestId("file-input").setInputFiles(EXAMPLE);
    await page.getByTestId("analyze-button").click();
    const table = page.getByTestId("report-table");
    await expect(table).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("disease-name")).toHaveText("Early blight");
    await expect(table).toContainText("آلو"); // Urdu crop name next to the English one
    await expect(page.getByTestId("risk-badge").first()).toBeVisible();
    for (const id of ["report-symptoms", "report-causes", "report-actions", "report-buttons", "disclaimer"]) {
      await expect(page.getByTestId(id)).toBeVisible();
    }
    await expect(page.getByTestId("report-actions").locator('[lang="ur"]').first()).toBeVisible();
    await shot(page, `report-${w}`);
    if (w === 390) {
      // README picture: just the report card as a farmer sees it on a phone
      await page.getByTestId("result-card").screenshot({ path: `${SHOTS}/report-card-390.jpg`, type: "jpeg", quality: 80 });
    }
    if (w === 1440) {
      await page.getByRole("link", { name: "Treatment guide" }).click();
      await expect(page).toHaveURL(/\/library\/Potato___Early_blight#treatment$/);
      await expect(page.getByTestId("treatment-guide")).toBeVisible();
      await expect(page.getByTestId("treatment-guide")).toContainText("علاج کی رہنمائی");
      await shot(page, "treatment-guide-1440");
      await page.goBack();
      await page.getByTestId("ask-assistant").click();
      await expect(page).toHaveURL(/\/assistant\?class_id=Potato___Early_blight$/);
      await expect(page.getByTestId("assistant-context")).toContainText("Early blight");
    }
    await page.context().close();
  }
});

test("assistant answers in the farmer's language from the knowledge base (no AI key configured)", async ({ browser }) => {
  const page = await openPage(browser, 1440, 900);
  await page.goto("/assistant");
  await expect(page.getByTestId("assistant-mode")).toContainText("Knowledge base");
  await page.getByTestId("assistant-suggestion").nth(1).click(); // گندم کی فصل کو بیماری سے کیسے بچاؤں؟
  const reply = page.getByTestId("chat-assistant").last();
  await expect(reply).toContainText("گندم", { timeout: 20_000 });
  await expect(reply.locator('p[lang="ur"]')).toBeVisible();
  await expect(page.getByTestId("assistant-kb-notice")).toBeVisible();
  await page.getByTestId("assistant-input").fill("How do I protect tomato plants from late blight?");
  await page.getByTestId("assistant-send").click();
  await expect(page.getByTestId("chat-assistant").last()).toContainText("Late blight", { timeout: 20_000 });
  await shot(page, "assistant-1440");
  await page.context().close();

  const phone = await openPage(browser, 390, 844);
  await phone.goto("/assistant");
  await phone.getByTestId("assistant-suggestion").nth(1).click();
  await expect(phone.getByTestId("chat-assistant").last()).toContainText("گندم", { timeout: 20_000 });
  await shot(phone, "assistant-390");
  await phone.context().close();
});

test("crop information and farming tips are bilingual and sourced", async ({ browser }) => {
  const page = await openPage(browser, 1440, 900);
  await page.goto("/crops");
  for (const id of ["wheat", "rice", "cotton", "sugarcane", "tomato", "potato", "maize", "mango", "citrus"]) {
    await expect(page.getByTestId(`crop-${id}`)).toBeVisible();
  }
  await shot(page, "crops-1440");
  await page.getByTestId("crop-wheat").click();
  await expect(page.getByTestId("crop-detail")).toContainText("Yellow (stripe) rust");
  await expect(page.getByTestId("crop-detail")).toContainText("پیلی کنگی");
  await expect(page.getByRole("link", { name: /fao\.org/ }).first()).toBeVisible();
  await shot(page, "crop-wheat-1440");
  await page.goto("/tips");
  await expect(page.getByTestId("tip")).toHaveCount(9);
  await page.context().close();
});

test("a very dark photo asks for a new photo and shows no disease", async ({ browser }) => {
  const dark = join(mkdtempSync(join(tmpdir(), "cropdoc-dark-")), "dark.jpg");
  execFileSync(process.env.CROPDOC_PYTHON ?? "../.venv/bin/python", [resolve(HERE, "make_dark_photo.py"), EXAMPLE, dark]);
  const page = await openPage(browser, 1280, 900);
  await page.goto("/scanner");
  await page.getByTestId("file-input").setInputFiles(dark);
  await page.getByTestId("analyze-button").click();
  await expect(page.getByTestId("retake-advice")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("retake-advice")).toContainText("too dark");
  await expect(page.getByTestId("status-pill")).toHaveAttribute("data-view", "retake");
  await expect(page.getByTestId("disease-name")).toHaveCount(0);
  await expect(page.getByTestId("disclaimer")).toBeVisible();
  await shot(page, "retake-1280");
  await page.getByTestId("scan-another").click();
  await expect(page.getByTestId("result-empty")).toBeVisible();
  await page.context().close();
});
