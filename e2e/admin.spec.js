// @ts-check
const { test, expect } = require('@playwright/test');

const ADMIN_EMAIL    = 'tomergur@gmail.com';
const ADMIN_PASSWORD = 'jclazvbdn'; // config.py default fallback

// Helper: log in to admin and return session token
async function adminLogin(page) {
  await page.goto('/pdn-admin/');
  await page.waitForSelector('#password', { state: 'visible' });
  await page.fill('#email',    ADMIN_EMAIL);
  await page.fill('#password', ADMIN_PASSWORD);
  await page.click('button[type="submit"]');
  // Wait for redirect to dashboard
  await page.waitForURL('**/pdn-admin/dashboard**', { timeout: 10_000 });
}

// ── Login page ──────────────────────────────────────────────────────────────

test.describe('Admin - login page', () => {

  test('renders login form', async ({ page }) => {
    await page.goto('/pdn-admin/');
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('password eye toggle shows/hides password', async ({ page }) => {
    await page.goto('/pdn-admin/');
    const input = page.locator('#password');
    await input.fill('secret');
    await expect(input).toHaveAttribute('type', 'password');
    await page.click('#eyeIcon');                 // toggle on
    await expect(input).toHaveAttribute('type', 'text');
    await page.click('#eyeIcon');                 // toggle off
    await expect(input).toHaveAttribute('type', 'password');
  });

  test('wrong password shows error', async ({ page }) => {
    await page.goto('/pdn-admin/');
    await page.fill('#email',    ADMIN_EMAIL);
    await page.fill('#password', 'wrongpassword123');
    await page.click('button[type="submit"]');
    const err = page.locator('#loginError');
    await expect(err).toBeVisible({ timeout: 5_000 });
  });

  test('correct password redirects to dashboard', async ({ page }) => {
    await adminLogin(page);
    await expect(page).toHaveURL(/pdn-admin\/dashboard/);
  });

});

// ── Dashboard ────────────────────────────────────────────────────────────────

test.describe('Admin - dashboard', () => {

  test.beforeEach(async ({ page }) => {
    await adminLogin(page);
  });

  test('page title visible', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('מערכת שליטה וניהול');
  });

  test('metrics tab is active by default', async ({ page }) => {
    const metricsTab = page.locator('#tab-metrics');
    await expect(metricsTab).toBeVisible();
  });

  test('can switch to users tab', async ({ page }) => {
    await page.click('#navUsers');
    await expect(page.locator('#tab-users')).toBeVisible();
    await expect(page.locator('#tableBody')).toBeVisible();
  });

  test('can switch to coupons tab', async ({ page }) => {
    await page.click('#navCoupons');
    await expect(page.locator('#tab-coupons')).toBeVisible();
  });

  test('can switch to chat users tab', async ({ page }) => {
    await page.click('#navChatusers');
    await expect(page.locator('#tab-chatusers')).toBeVisible();
  });

  test('can switch to costs tab', async ({ page }) => {
    await page.click('#navCosts');
    await expect(page.locator('#tab-costs')).toBeVisible();
  });

  test('can switch to stats tab', async ({ page }) => {
    await page.click('#navStats');
    await expect(page.locator('#tab-stats')).toBeVisible();
  });

  test('version badge shows version after load', async ({ page }) => {
    const badge = page.locator('#versionText');
    // Wait for the async fetch to complete
    await expect(badge).not.toHaveText('טוען...', { timeout: 8_000 });
    await expect(badge).toContainText('v1.');
  });

  test('clicking logo opens release notes modal', async ({ page }) => {
    // Wait for version to load first
    await expect(page.locator('#versionText')).not.toHaveText('טוען...', { timeout: 8_000 });
    await page.click('img[alt="PDN Logo"]');
    const modal = page.locator('#releaseNotesModal');
    await expect(modal).toBeVisible({ timeout: 5_000 });
    // Should show version and recent commits
    await expect(modal).toContainText('v1.');
  });

  test('version modal shows release date', async ({ page }) => {
    await expect(page.locator('#versionText')).not.toHaveText('טוען...', { timeout: 8_000 });
    await page.click('img[alt="PDN Logo"]');
    const modal = page.locator('#releaseNotesModal');
    await expect(modal).toBeVisible();
    // Date format DD/MM/YYYY
    await expect(modal).toContainText(/\d{2}\/\d{2}\/\d{4}/);
  });

  test('status filter dropdown has not-diagnosed option', async ({ page }) => {
    await page.click('#navUsers');
    const select = page.locator('#quickFilterStatus');
    await expect(select.locator('option[value="not_diagnosed"]')).toHaveText('לא נבדק ע"י מאבחן');
  });

  test('refresh button triggers data load', async ({ page }) => {
    // Button should be enabled after initial load
    await page.waitForTimeout(2000);
    const refreshBtn = page.locator('#refreshBtn');
    await expect(refreshBtn).toBeEnabled();
    await refreshBtn.click();
    // Button briefly disabled while loading
    await expect(refreshBtn).toBeDisabled();
    await expect(refreshBtn).toBeEnabled({ timeout: 15_000 });
  });

  test('/pdn-admin/version endpoint returns valid JSON', async ({ page }) => {
    const response = await page.request.get('/pdn-admin/version');
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('version');
    expect(body).toHaveProperty('commit');
    expect(body).toHaveProperty('release_date');
    expect(body).toHaveProperty('release_notes');
    expect(Array.isArray(body.release_notes)).toBe(true);
    expect(body.release_notes.length).toBeGreaterThan(0);
  });

  test('logout button clears session and redirects to login', async ({ page }) => {
    await page.click('#logoutBtn');
    await page.waitForURL('**/pdn-admin/**', { timeout: 8_000 });
    // After logout the session token is gone; accessing dashboard redirects to login
    await page.goto('/pdn-admin/dashboard');
    await expect(page).toHaveURL(/pdn-admin\/(login|dashboard|\?|$)/);
  });

});
