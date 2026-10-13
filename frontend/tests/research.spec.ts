import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { mkdirSync } from "node:fs";

const api = "http://localhost:8000/api/v1";
let workspace: string;
const title = "Log Anomaly Research";
test.beforeAll(async ({ request }) => {
  const python = path.resolve(
    "..",
    process.platform === "win32"
      ? ".venv/Scripts/python.exe"
      : ".venv/bin/python",
  );
  const payload = execFileSync(python, [
    "-c",
    "import pymupdf,sys; p=pymupdf.open(); page=p.new_page(); page.insert_text((72,72),'Fictional Log Study\\nMethods\\nWe detect anomalies in server logs with a neural network.\\nResults\\nThe neural model evaluates server log anomaly detection.'); sys.stdout.buffer.write(p.tobytes())",
  ]);
  const response = await request.post(`${api}/workspaces`, {
    data: { name: title },
  });
  expect(response.ok()).toBeTruthy();
  workspace = (await response.json()).id;
  const uploaded = await request.post(
    `${api}/workspaces/${workspace}/documents`,
    {
      multipart: {
        file: {
          name: "browser-study.pdf",
          mimeType: "application/pdf",
          buffer: payload,
        },
      },
    },
  );
  expect(uploaded.ok()).toBeTruthy();
  expect((await uploaded.json()).processing_status).toBe("ready");
});
test.afterAll(async ({ request }) => {
  if (workspace) await request.delete(`${api}/workspaces/${workspace}`);
});

test("workspace, source passages, semantic search and citation drawer", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`/workspace/${workspace}/papers`);
  await expect(
    page.getByRole("button", { name: "Fictional Log Study" }),
  ).toBeVisible();
  await page.getByLabel("Current workspace").selectOption(workspace);
  await expect(
    page.getByRole("button", { name: "Fictional Log Study" }),
  ).toBeVisible();
  mkdirSync(path.resolve("../.logs"), { recursive: true });
  await page.screenshot({
    path: "../.logs/researchlens-papers.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Fictional Log Study" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page
      .getByRole("dialog")
      .getByText(/Page 1/)
      .first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close paper" }).click();
  await page
    .getByRole("button", { name: "Semantic Search", exact: true })
    .click();
  await page
    .getByLabel("Search research concepts")
    .fill("server log anomaly detection");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".search-result").first()).toBeVisible();
  const excerpt = await page.locator(".search-result > p").first().innerText();
  await page.locator(".search-result .source-badges button").first().click();
  await expect(page.getByRole("dialog").locator("blockquote")).toHaveText(
    excerpt,
  );
  await page.getByRole("button", { name: "Close source" }).click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Semantic search", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  await page.screenshot({
    path: "../.logs/researchlens-search.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: /My papers/ }).click();
  await expect(
    page.getByRole("heading", { name: "Your paper collection" }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Semantic search", exact: true }),
  ).toBeVisible();
});

test("chat history and grounded citations", async ({ page }) => {
  test.setTimeout(150000);
  const health = await (await page.request.get(`${api}/health`)).json();
  test.skip(
    !health.llm_configured,
    "Live provider credentials are not configured",
  );
  await page.goto(`/workspace/${workspace}/chat`);
  await page
    .getByLabel("Your research question")
    .fill("What method detects anomalies in server logs?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.locator(".message.assistant")).toBeVisible({
    timeout: 120000,
  });
  await expect(
    page.locator(".message.assistant .source-badges button").first(),
  ).toBeVisible();
  await page.reload();
  await page.locator(".conversations button").first().click();
  await expect(page.locator(".message.assistant")).toBeVisible();
});

test("mobile layout and workspace creation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/workspace/${workspace}`);
  await expect(page.getByLabel("Current workspace")).toBeVisible();
  await page.getByRole("button", { name: "Start a new workspace" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByLabel("Workspace name")).toBeFocused();
  await page.keyboard.press("Escape");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
