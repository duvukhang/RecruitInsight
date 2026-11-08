import { test, expect, request as playwrightRequest } from '@playwright/test';
import fs from 'node:fs';
import { randomBytes } from 'node:crypto';
let cleanupUsers: any[] = [];
let cleanupHeaders: Record<string, string> = {};
test.afterEach(async () => {
  const cleanup = await playwrightRequest.newContext({ baseURL: 'http://localhost:8080', extraHTTPHeaders: cleanupHeaders });
  try { for (const user of cleanupUsers) await cleanup.patch('/api/v1/users/' + user.id, { data: { enabled: false } }); }
  finally { cleanupUsers = []; await cleanup.dispose(); }
});

test('live theme: real charts, light tables/profile, mobile and saved preference', async ({ page }) => {
  const env = Object.fromEntries(fs.readFileSync('../.env', 'utf8').split(/\r?\n/).filter(l => l.includes('=') && !l.startsWith('#')).map(l => { const at = l.indexOf('='); return [l.slice(0, at), l.slice(at + 1)]; }));
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill(env.ADMIN_USERNAME);
  await page.getByLabel('Mật khẩu', { exact: true }).fill(env.ADMIN_PASSWORD);
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await expect(page.locator('.chart canvas')).toHaveCount(5);
  await page.getByRole('button', { name: 'Chuyển sang giao diện sáng' }).click();
  await expect(page.locator('.stat').first()).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await expect(page.locator('.stat').first()).not.toContainText('—');
  await expect(page.locator('.chart canvas')).toHaveCount(5);
  await page.screenshot({ path: '../artifacts/theme-live-light-dashboard.png', fullPage: true });
  await page.getByRole('link', { name: 'Danh sách việc làm', exact: true }).click();
  await expect(page.locator('tbody tr').first()).toBeVisible();
  await expect(page.locator('table')).toHaveCSS('color', 'rgb(48, 75, 105)');
  await page.screenshot({ path: '../artifacts/theme-live-light-jobs.png', fullPage: true });
  await page.locator('.account-chip').click();
  await expect(page.locator('.profile-content')).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.getByRole('heading', { name: 'Thông tin của bạn', exact: true })).toBeVisible();
  await page.screenshot({ path: '../artifacts/theme-live-light-profile.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('button', { name: 'Chuyển sang giao diện tối' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../artifacts/theme-live-light-mobile.png', fullPage: true });
  await page.getByRole('button', { name: 'Chuyển sang giao diện tối' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('.profile-content')).toHaveCSS('background-color', 'rgb(16, 28, 48)');
});

test('live profile security: wrong password, change password, revoke all devices', async ({ page, request }) => {
  const env = Object.fromEntries(fs.readFileSync('../.env', 'utf8').split(/\r?\n/).filter(l => l.includes('=') && !l.startsWith('#')).map(l => { const at = l.indexOf('='); return [l.slice(0, at), l.slice(at + 1)]; }));
  const admin = await request.post('/api/v1/auth/login', { data: { username: env.ADMIN_USERNAME, password: env.ADMIN_PASSWORD } });
  expect(admin.status()).toBe(200);
  cleanupHeaders = { Authorization: 'Bearer ' + (await admin.json()).data.access_token };
  const username = 'TEST-PROFILE-' + randomBytes(6).toString('hex'), oldPassword = 'Test-' + randomBytes(18).toString('hex') + '9!';
  const password = 'New-' + randomBytes(18).toString('hex') + '9!';
  const created = await request.post('/api/v1/users', { headers: cleanupHeaders, data: { username, password: oldPassword, role: 'VIEWER' } });
  expect(created.status()).toBe(201);
  cleanupUsers = [(await created.json()).data];
  async function login(secret: string) {
    await page.getByLabel('Tên đăng nhập', { exact: true }).fill(username);
    await page.getByLabel('Mật khẩu', { exact: true }).fill(secret);
    await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
    await expect(page.locator('.account-chip')).toBeVisible();
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Dashboard tổng quan' })).toBeVisible();
  }
  await page.goto('/');
  await login(oldPassword);
  await page.locator('.account-chip').click();
  await page.getByRole('tab', { name: 'Bảo mật & phiên' }).click();
  await page.getByLabel('Mật khẩu hiện tại', { exact: true }).fill('wrong');
  await page.getByLabel('Mật khẩu mới', { exact: true }).fill(password);
  await page.getByLabel('Xác nhận mật khẩu mới', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Đổi mật khẩu', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Mật khẩu hiện tại không đúng');
  await page.getByLabel('Mật khẩu hiện tại', { exact: true }).fill(oldPassword);
  await page.getByRole('button', { name: 'Đổi mật khẩu', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Đã đổi mật khẩu');
  await login(password);
  await page.locator('.account-chip').click();
  await page.getByRole('tab', { name: 'Bảo mật & phiên' }).click();
  await page.getByRole('button', { name: 'Đăng xuất mọi thiết bị', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Xác nhận', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Đã đăng xuất mọi thiết bị');
  await login(password);
});
test('live roles: real login/API, direct route guards, users/quality and desktop/mobile captures', async ({ browser, request }) => {
  test.setTimeout(120000);
  const env = Object.fromEntries(fs.readFileSync('../.env', 'utf8').split(/\r?\n/).filter(l => l.includes('=') && !l.startsWith('#')).map(l => { const at = l.indexOf('='); return [l.slice(0, at), l.slice(at + 1)]; }));
  const login = await request.post('/api/v1/auth/login', { data: { username: env.ADMIN_USERNAME, password: env.ADMIN_PASSWORD } });
  expect(login.status()).toBe(200);
  const token = (await login.json()).data.access_token;
  const headers = { Authorization: 'Bearer ' + token };
  const users: any[] = [];
  cleanupUsers = users; cleanupHeaders = headers;
    for (const role of ['ANALYST', 'VIEWER']) {
      const username = 'TEST-BROWSER-' + randomBytes(6).toString('hex'), password = 'Test-' + randomBytes(24).toString('base64url') + '9!';
      const created = await request.post('/api/v1/users', { headers, data: { username, password, role } });
      expect(created.status()).toBe(201);
      users.push({ ...(await created.json()).data, password });
    }
    for (const account of [{ role: 'ADMIN', username: env.ADMIN_USERNAME, password: env.ADMIN_PASSWORD }, ...users]) {
      const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.goto('http://localhost:8080/');
      await page.getByLabel('Tên đăng nhập', { exact: true }).fill(account.username);
      await page.getByLabel('Mật khẩu', { exact: true }).fill(account.password);
      await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Dashboard tổng quan' })).toBeVisible();
      await expect(page.locator('.stat').first()).not.toContainText('—');
      if (account.role === 'ADMIN') {
        await page.getByRole('link', { name: 'Người dùng', exact: true }).click();
        await expect(page.getByRole('button', { name: 'Tạo người dùng' })).toBeVisible();
        await page.screenshot({ path: '../artifacts/upgrade-2-live-users.png', fullPage: true });
        await page.getByRole('link', { name: 'Chất lượng dữ liệu', exact: true }).click();
        await expect(page.getByLabel('Dataset cần kiểm tra')).toBeVisible();
        await page.getByLabel('Dataset cần kiểm tra').selectOption({ index: 1 });
        await expect(page.getByText('Đạt quality gate', { exact: false })).toBeVisible();
        await page.screenshot({ path: '../artifacts/upgrade-2-live-quality.png', fullPage: true });
        await page.getByRole('link', { name: 'Nguồn dữ liệu', exact: true }).click();
        await expect(page.getByText('NEEDS_REVIEW', { exact: true }).first()).toBeVisible();
        await page.getByRole('combobox', { name: 'Phiên bản 1', exact: true }).selectOption({ index: 1 });
        await page.getByRole('combobox', { name: 'Phiên bản 2', exact: true }).selectOption({ index: 2 });
        await expect(page.getByRole('button', { name: 'Tải báo cáo JSON' }).first()).toBeEnabled();
        const exported = page.waitForEvent('download');
        await page.getByRole('button', { name: 'Tải báo cáo JSON' }).first().click();
        expect((await exported).suggestedFilename()).toMatch(/report-.+\.json/);
        await page.screenshot({ path: '../artifacts/upgrade-2-live-sources.png', fullPage: true });
        await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
      } else {
        await page.goto('http://localhost:8080/users');
        await expect(page.getByRole('alert')).toContainText('403');
        await page.getByRole('link', { name: 'Về tổng quan' }).click();
      }
      await expect(page.locator('.chart canvas')).toHaveCount(5);
      await page.evaluate(() => { document.scrollingElement?.scrollTo(0, 0); const sidebar = document.querySelector('aside'); if (sidebar) sidebar.scrollTop = 0; });
      await page.screenshot({ path: `../artifacts/upgrade-2-live-${account.role.toLowerCase()}-desktop.png`, fullPage: true });
      await page.locator('.account-chip').click();
      await expect(page.getByRole('heading', { name: 'Thông tin của bạn', exact: true })).toBeVisible();
      if (account.role !== 'ADMIN') {
        await page.getByLabel('Tên hiển thị', { exact: true }).fill('DEMO ' + account.role);
        await page.getByLabel('Tổ chức', { exact: true }).fill('Kiểm thử hồ sơ');
        await page.getByRole('button', { name: 'Lưu thay đổi', exact: true }).click();
        await expect(page.getByRole('status')).toContainText('Đã lưu hồ sơ');
        await page.reload();
        await expect(page.getByLabel('Tên hiển thị', { exact: true })).toHaveValue('DEMO ' + account.role);
      }
      await page.screenshot({ path: `../artifacts/profile-${account.role.toLowerCase()}-desktop.png`, fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: `../artifacts/profile-${account.role.toLowerCase()}-mobile.png`, fullPage: true });
      await page.getByRole('tab', { name: 'Bảo mật & phiên' }).click();
      await expect(page.getByRole('button', { name: 'Đăng xuất mọi thiết bị', exact: true })).toBeVisible();
      await page.screenshot({ path: `../artifacts/profile-${account.role.toLowerCase()}-security.png`, fullPage: true });
      await page.goto('http://localhost:8080/');
      await expect(page.locator('.chart canvas')).toHaveCount(5);
      await page.setViewportSize({ width: 390, height: 844 });
      await page.getByRole('button', { name: 'Menu', exact: true }).click();
      await expect(page.getByRole('navigation')).toBeVisible();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: `../artifacts/upgrade-2-live-${account.role.toLowerCase()}-mobile.png`, fullPage: true });
      await page.close();
    }
});
