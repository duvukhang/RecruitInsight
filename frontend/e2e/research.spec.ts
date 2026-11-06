import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";

// Explicit UI fixture. This suite does not verify MongoDB/Spark or use real credentials.
test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const meta = { dataset_version: "TEST-UI-dataset", sample_size: 40, eligible_count: 2,
      missing_salary_rate: 0.95, is_demo: true, reference_period: { from: "2026-01-01", to: "2026-02-01" },
      warnings: ["HIGH_MISSING_SALARY_LABEL_RATE"], method: "TEST FIXTURE", updated_at: "2026-02-01" };
    let body: any = { data: [] };
    if (path === "/auth/refresh") body = { data: { access_token: "TEST-ONLY", user: { id: "test", username: "test", role: "ADMIN" } }, csrf_token: "TEST-ONLY" };
    else if (path === "/datasets") body = { data: [{ _id: "TEST-UI-dataset", source: "TEST", status: "PUBLISHED", is_demo: true }] };
    else if (path === "/jobs/filters/options") body = { data: { provinces: ["HCM"], industries: ["IT"] } };
    else if (path === "/analytics/overview") body = { data: { total_jobs: 40, total_companies: 10, total_industries: 1, total_provinces: 1, salary_sample_size: 2, median_salary_vnd: 15e6 }, meta };
    else if (path === "/analytics/salary-by-industry" || path === "/analytics/salary-by-location") body = { data: [{ industry: "IT", province: "HCM", jobs: 40, salary_sample_size: 2, median_salary_vnd: 15e6, mean_salary_vnd: 15e6, p25: null, p75: null }], meta };
    else if (path === "/analytics/salary-distribution") body = { data: [{ lower_vnd: 15e6, count: 2 }], meta };
    else if (path.startsWith("/analytics/")) body = { data: [], meta };
    await route.fulfill({ json: body });
  });
});

test("salary context, small sample, filters and mobile layout with UI fixture", async ({ page }) => {
  await page.goto("/analytics/salary");
  await expect(page.getByText("Ít mẫu lương (<30)")).toBeVisible();
  await expect(page.getByText("Thiếu nhãn: 95.0%", { exact: false })).toBeVisible();
  await page.getByLabel("Địa phương", { exact: true }).selectOption("HCM");
  await expect(page.getByText("Địa phương: HCM", { exact: false })).toBeVisible();
  await page.screenshot({ path: fileURLToPath(new URL("../../artifacts/upgrade-salary-desktop.png", import.meta.url)), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: fileURLToPath(new URL("../../artifacts/upgrade-salary-mobile.png", import.meta.url)), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("analysis displays API failures and retry", async ({ page }) => {
  await page.route("**/api/v1/analytics/**", route => route.fulfill({ status: 503, json: { error: { message: "TEST: service unavailable" } } }));
  await page.goto("/analytics/salary");
  await expect(page.getByRole("alert").first()).toContainText("TEST: service unavailable", { timeout: 15000 });
  await expect(page.getByRole("button", { name: "Thử lại" }).first()).toBeVisible();
});
