import { chromium } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";

const root = path.resolve("..");
const python = path.join(
  root,
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);
const api = process.env.SCREENSHOT_API_URL || "http://localhost:8000/api/v1";
const site = process.env.SCREENSHOT_SITE_URL || "http://localhost:3000";
const destination = path.join(root, "docs/screenshots");
mkdirSync(destination, { recursive: true });
const token = execFileSync(
  python,
  [
    "-c",
    "from app.core.config import get_settings; print(get_settings().api_token.get_secret_value(),end='')",
  ],
  { cwd: path.join(root, "backend"), encoding: "utf8" },
);
const headers = token ? { Authorization: `Bearer ${token}` } : {};
async function request(route, options = {}) {
  const response = await fetch(`${api}${route}`, {
    ...options,
    headers: { ...headers, ...options.headers },
  });
  if (!response.ok)
    throw new Error(
      `Screenshot setup request failed: ${route} (${response.status})`,
    );
  return response.status === 204 ? null : response.json();
}
const workspace = await request("/workspaces", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    name: "Log Anomaly Research",
    description: "Comparing neural approaches to server log anomaly detection.",
  }),
});
let browser;
try {
  for (const [title, dataset, score] of [
    ["Fictional Log Study Alpha", "AlphaLogs", "98.4"],
    ["Fictional Log Study Beta", "BetaLogs", "94.2"],
  ]) {
    const payload = execFileSync(
      python,
      [
        "-c",
        "from scripts.verify_live import fictional_pdf; import sys; sys.stdout.buffer.write(fictional_pdf(sys.argv[1],sys.argv[2],sys.argv[3]))",
        title,
        dataset,
        score,
      ],
      { cwd: path.join(root, "backend") },
    );
    const body = new FormData();
    body.append(
      "file",
      new Blob([payload], { type: "application/pdf" }),
      `${title}.pdf`,
    );
    const paper = await request(`/workspaces/${workspace.id}/documents`, {
      method: "POST",
      body,
    });
    if (paper.processing_status !== "ready")
      throw new Error("Screenshot paper indexing failed.");
  }
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1,
  });
  if (token)
    await context.addInitScript(
      (value) => sessionStorage.setItem("researchlens-token", value),
      token,
    );
  const page = await context.newPage();
  async function screenshot(name) {
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({
      path: path.join(destination, `${name}.png`),
      fullPage: true,
      animations: "disabled",
    });
    console.log(`Captured ${name}.png`);
  }
  async function visit(section = "") {
    await page.goto(
      `${site}/workspace/${workspace.id}${section ? `/${section}` : ""}`,
    );
    await page.waitForFunction(
      (id) =>
        document.querySelector('select[aria-label="Current workspace"]')
          ?.value === id,
      workspace.id,
    );
    await page.waitForFunction(
      () => !document.body.innerText.includes("Loading your research library"),
    );
  }
  await visit();
  await page
    .getByRole("button", { name: /^Fictional Log Study Alpha/ })
    .waitFor();
  await screenshot("overview");
  await visit("papers");
  await page
    .getByRole("button", { name: /^Fictional Log Study Alpha/ })
    .waitFor();
  await screenshot("papers");
  await visit("search");
  await page
    .getByLabel("Search research concepts")
    .fill("server log anomaly detection methodology");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.locator(".search-result").first().waitFor();
  await screenshot("semantic-search");
  await visit("chat");
  await page
    .getByLabel("Your research question")
    .fill("What methodology is used to detect server log anomalies?");
  const chatResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/messages") &&
      response.request().method() === "POST",
    { timeout: 120000 },
  );
  await page.getByRole("button", { name: "Send question" }).click();
  if (!(await chatResponse).ok())
    throw new Error(
      "Live chat generation failed; no fabricated answer will be captured.",
    );
  await page
    .locator(".message.assistant .source-badges button")
    .first()
    .waitFor();
  await screenshot("chat");
  await page
    .locator(".message.assistant .source-badges button")
    .first()
    .click();
  await page.getByRole("dialog").locator("blockquote").waitFor();
  await screenshot("source-citation");
  await page.getByRole("button", { name: "Close source" }).click();
  await visit("analysis");
  await page
    .getByLabel("Select a paper")
    .selectOption({ label: "Fictional Log Study Alpha" });
  const analysisResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/analyze") &&
      response.request().method() === "POST",
    { timeout: 120000 },
  );
  await page
    .getByRole("button", { name: "Structured analysis", exact: true })
    .click();
  if (!(await analysisResponse).ok())
    throw new Error("Live paper analysis failed.");
  await page.locator(".analysis-grid").waitFor();
  await screenshot("analysis");
  await visit("compare");
  await page.getByRole("checkbox").nth(0).check();
  await page.getByRole("checkbox").nth(1).check();
  const comparisonResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/compare") &&
      response.request().method() === "POST",
    { timeout: 120000 },
  );
  await page.getByRole("button", { name: "Compare 2 papers" }).click();
  if (!(await comparisonResponse).ok())
    throw new Error("Live paper comparison failed.");
  await page.locator(".comparison-table").waitFor();
  await screenshot("comparison");
  await page.setViewportSize({ width: 390, height: 844 });
  await visit();
  await page
    .getByRole("button", { name: /^Fictional Log Study Alpha/ })
    .waitFor();
  await screenshot("mobile");
} finally {
  if (browser) await browser.close();
  await request(`/workspaces/${workspace.id}`, { method: "DELETE" });
  console.log("Disposable screenshot workspace removed.");
}
