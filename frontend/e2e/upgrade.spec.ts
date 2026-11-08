import { test, expect, type Page } from '@playwright/test';
import { fileURLToPath } from 'node:url';

// UI-only synthetic fixture. Runtime API security is covered separately against Mongo.
async function fixture(page: Page, role: string) {
  const calls: string[] = [];
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
    calls.push(path);
    const user = { id: 'TEST-' + role, username: 'TEST-' + role, role };
    const meta = { dataset_version: 'TEST-SYNTHETIC', sample_size: 100, eligible_count: 80, missing_salary_rate: .2, is_demo: true, source: 'TEST FIXTURE', reference_period: {}, warnings: [], updated_at: '2026-01-01' };
    let body: any = { data: [] };
    if (path === '/auth/refresh') body = { data: { access_token: 'TEST-ONLY', user }, csrf_token: 'TEST-ONLY' };
    else if (path === '/auth/me') body = { data: user };
    else if (path === '/auth/profile') body = { data: { ...user, display_name: user.username, avatar_color: 'cyan', email: '', organization: '', bio: '' } };
    else if (path === '/auth/sessions') body = { data: [], meta: { page: 1, page_size: 10, total: 0 } };
    else if (path === '/datasets') body = { data: [{ _id: 'TEST-SYNTHETIC', is_demo: true, source: 'TEST FIXTURE', status: 'PUBLISHED', row_counts: { raw: 100, clean: 100 } }] };
    else if (path === '/jobs/filters/options') body = { data: { provinces: ['Hà Nội', 'HCM'], industries: ['IT'] } };
    else if (path === '/analytics/overview') body = { data: { total_jobs: 100, total_companies: 10, total_industries: 2, total_provinces: 1, salary_sample_size: 80, median_salary_vnd: 20e6 }, meta };
    else if (path === '/analytics/job-years') body = { data: [{ posted_year: 2024, count: 100 }], meta };
    else if (path.startsWith('/analytics/')) body = { data: [], meta };
    else if (path === '/users') body = { data: [{ id: 'TEST-USER', username: 'sample-viewer', role: 'VIEWER', enabled: true }], meta: { page: 1, page_size: 25, total: 1 } };
    else if (path === '/jobs') body = { data: [{ _id: 'TEST-JOB', job_title: 'SYNTHETIC Engineer', company_name: 'SYNTHETIC Co', province: 'Hà Nội', salary_mid_vnd: 20e6, required_skills: [] }], meta: { ...meta, total: 1 } };
    else if (path === '/jobs/TEST-JOB') body = { data: { _id: 'TEST-JOB', job_title: 'SYNTHETIC Engineer', company_name: 'SYNTHETIC Co', province: 'Hà Nội', salary_mid_vnd: 20e6, required_skills: [], job_description: 'Nội dung từ API chi tiết' }, meta };
    else if (path === '/audit-logs') body = { data: [], meta: { page: 1, page_size: 25, total: 0 } };
    else if (path === '/sources') body = { data: [{ id: 'tinix', dataset: 'tinixai/vietnamese-job-descriptions', permission_status: 'NEEDS_REVIEW', license: 'CC-BY-NC-4.0', adapter_version: 'public-jobs-v1', url: 'https://huggingface.co/datasets/tinixai/vietnamese-job-descriptions' }] };
    await route.fulfill({ json: body });
  });
  return calls;
}

test('theme switches charts and profile, persists on reload and syncs between tabs', async ({ page, context }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await fixture(page, 'VIEWER');
  await page.route('**/api/v1/analytics/salary-by-industry**', route => route.fulfill({ json: { data: [{ industry: 'IT', jobs: 100 }] } }));
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('.chart canvas')).toHaveCount(2);
  await page.getByRole('button', { name: 'Chuyển sang giao diện sáng' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.locator('.panel').first()).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await expect(page.locator('.chart canvas')).toHaveCount(2);
  await expect(page.locator('.stat').first()).toContainText('100');
  await page.screenshot({ path: '../artifacts/theme-light-dashboard.png', fullPage: true });
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.locator('.account-chip').click();
  await expect(page.locator('.profile-content')).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await page.screenshot({ path: '../artifacts/theme-light-profile.png', fullPage: true });
  const second = await context.newPage();
  await fixture(second, 'VIEWER');
  await second.goto('/');
  await expect(second.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('button', { name: 'Chuyển sang giao diện tối' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(second.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('.profile-content')).toHaveCSS('background-color', 'rgb(16, 28, 48)');
  await second.close();
});

test('theme switch works on mobile login with keyboard and remembers selection', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({ status: 401, json: {} }));
  await page.goto('/');
  const toggle = page.getByRole('button', { name: 'Chuyển sang giao diện sáng' });
  await toggle.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.getByRole('button', { name: 'Chuyển sang giao diện tối' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../artifacts/theme-light-login-mobile.png', fullPage: true });
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('button', { name: 'Chuyển sang giao diện tối' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

for (const role of ['ADMIN', 'ANALYST', 'VIEWER']) {
  for (const width of [390, 768, 1366]) {
    test(`${role} at ${width}: navigation, API stats, responsive and reduced motion`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await fixture(page, role);
      await page.goto('/');
      await expect(page.locator('.stat').first()).toContainText('100');
      await expect(page.getByRole('heading', { name: 'Số tin theo năm quan sát' })).toBeVisible();
      if (width <= 768) await page.getByRole('button', { name: 'Menu', exact: true }).click();
      const nav = page.getByRole('navigation');
      if (role === 'VIEWER') await expect(nav.getByRole('link', { name: 'Dự đoán mức lương', exact: true })).toHaveCount(0);
      else await expect(nav.getByRole('link', { name: 'Dự đoán mức lương', exact: true })).toBeVisible();
      if (role !== 'ADMIN') await expect(nav.getByRole('link', { name: 'Người dùng', exact: true })).toHaveCount(0);
      const layout = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth,
        offenders: Array.from(document.querySelectorAll('*')).filter(el => el.getBoundingClientRect().right > innerWidth + 1).slice(0, 12).map(el => ({ tag: el.tagName, cls: el.className, right: el.getBoundingClientRect().right })) }));
      expect(layout.scroll <= layout.width, JSON.stringify(layout)).toBe(true);
      expect(await page.locator('.stat').first().evaluate(el => getComputedStyle(el).transform)).toBe('none');
      await page.screenshot({ path: fileURLToPath(new URL(`../../artifacts/upgrade-2-${role.toLowerCase()}-${width}.png`, import.meta.url)), fullPage: true });
    });
  }
}

test('direct forbidden routes never mount protected requests', async ({ page }) => {
  const calls = await fixture(page, 'VIEWER');
  for (const path of ['/users', '/USERS/', '/%75sers', '/datasets', '/settings', '/models', '/predictions', '/audit']) {
    await page.goto(path);
    await expect(page.getByRole('alert')).toContainText('403');
  }
  expect(calls.some(path => ['/users', '/audit-logs', '/models', '/predictions/history', '/system/status'].includes(path))).toBe(false);
});

test('admin confirmation traps focus, Escape cancels, and mutation connects to API', async ({ page }) => {
  const calls = await fixture(page, 'ADMIN');
  await page.goto('/users');
  await page.getByRole('button', { name: 'Đổi quyền', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  for (let i = 0; i < 8; i++) {
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => !!document.activeElement?.closest('dialog'))).toBe(true);
  }
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await page.getByRole('button', { name: 'Đặt lại mật khẩu', exact: true }).click();
  await dialog.getByLabel('Mật khẩu mới', { exact: false }).fill('TEST-Password-2026!');
  await dialog.getByRole('button', { name: 'Xác nhận', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(calls).toContain('/users/TEST-USER/reset-password');
  await page.screenshot({ path: fileURLToPath(new URL('../../artifacts/upgrade-2-admin-users.png', import.meta.url)), fullPage: true });
});

test('job detail loads its full API response and native dialog closes with Escape', async ({ page }) => {
  await fixture(page, 'VIEWER');
  await page.goto('/jobs');
  await page.getByRole('button', { name: 'SYNTHETIC Engineer', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Nội dung từ API chi tiết');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('current role changes clear protected view; revoked session returns to login', async ({ page }) => {
  await fixture(page, 'ADMIN');
  await page.goto('/users');
  await expect(page.getByRole('button', { name: 'Tạo người dùng' })).toBeVisible();
  await page.route('**/api/v1/auth/me', route => route.fulfill({ json: { data: { id: 'TEST-ADMIN', username: 'TEST-ADMIN', role: 'VIEWER' } } }));
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.getByRole('alert')).toContainText('403');
  await expect(page.getByRole('link', { name: 'Người dùng', exact: true })).toHaveCount(0);
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 401, json: { error: { message: 'Phiên bị thu hồi' } } }));
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.getByRole('button', { name: 'Đăng nhập', exact: true })).toBeVisible();
});

test('scope filters persist across navigation, reload and browser history', async ({ page }) => {
  await fixture(page, 'VIEWER');
  await page.goto('/');
  await page.getByLabel('Địa phương', { exact: true }).selectOption('Hà Nội');
  await expect(page).toHaveURL(/province=/);
  await page.getByLabel('Địa phương', { exact: true }).selectOption('HCM');
  await page.goBack();
  await expect(page.getByLabel('Địa phương', { exact: true })).toHaveValue('Hà Nội');
  await page.getByRole('link', { name: 'Phân tích mức lương', exact: true }).click();
  await expect(page.getByLabel('Địa phương', { exact: true })).toHaveValue('Hà Nội');
  await page.reload();
  await expect(page.getByLabel('Địa phương', { exact: true })).toHaveValue('Hà Nội');
});
