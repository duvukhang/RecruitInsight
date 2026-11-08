import { test, expect } from "@playwright/test";
import fs from "node:fs";
const environment = Object.fromEntries(
  fs
    .readFileSync("../.env", "utf8")
    .split(/\r?\n/)
    .filter((line) => line.includes("="))
    .map((line) => {
      const i = line.indexOf("=");
      return [line.slice(0, i), line.slice(i + 1)];
    }),
);
const evidence = JSON.parse(
  fs.readFileSync("../artifacts/e2e-result.json", "utf8"),
);
const total = evidence.overview.data.total_jobs.toLocaleString("vi-VN");
test("login, real dashboard, filters, model prediction and history", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Tên đăng nhập").fill(environment.ADMIN_USERNAME);
  await page
    .getByLabel("Mật khẩu", { exact: true })
    .fill(environment.ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard tổng quan" }),
  ).toBeVisible();
  await page
    .getByLabel("Dataset version", { exact: true })
    .selectOption(evidence.dataset_version);
  await expect(page.locator('.stat').first()).toContainText(total);
  await page.getByLabel("Địa phương", { exact: true }).selectOption("Hà Nội");
  await expect(page.locator('.stat').first()).not.toContainText(total);
  await page
    .getByRole("link", { name: "Danh sách việc làm", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Khám phá việc làm" }),
  ).toBeVisible();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page
    .getByRole("link", { name: "Dự đoán mức lương", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Dự đoán mức lương", exact: true })
    .click();
  await expect(page.getByText("Lương ước lượng mỗi tháng")).toBeVisible();
  await expect(
    page.getByText("DEMO: mô hình học từ dữ liệu tổng hợp", { exact: false }),
  ).toBeVisible();
  await page.screenshot({
    path: "../artifacts/dashboard-prediction.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Quản lý dữ liệu", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Dataset versions" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Machine Learning", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Model registry" }),
  ).toBeVisible();
  await page
    .getByLabel("Dataset huấn luyện", { exact: true })
    .selectOption(evidence.dataset_version);
  await expect(
    page.getByText("random_forest", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("link", { name: "Dashboard", exact: true }).click();
  await page.screenshot({ path: "../artifacts/dashboard.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../artifacts/dashboard-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
