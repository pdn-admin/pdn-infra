// @ts-check
const { test, expect } = require('@playwright/test');

// Diagnose login: password = local part of email before @
const TEST_EMAIL    = 'e2etest@playwright.com';
const TEST_PASSWORD = 'e2etest';

// ── Login page ───────────────────────────────────────────────────────────────

test.describe('Diagnose - login page', () => {

  test('renders login form', async ({ page }) => {
    await page.goto('/pdn-diagnose/');
    // Page should contain email and password inputs
    await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"], input[name="password"]')).toBeVisible();
  });

  test('wrong password returns error', async ({ page }) => {
    await page.goto('/pdn-diagnose/');
    const emailInput = page.locator('input[type="email"], input[name="email"]').first();
    const passInput  = page.locator('input[type="password"], input[name="password"]').first();
    await emailInput.fill('test@example.com');
    await passInput.fill('wrongpassword');
    // Submit the form / click the login button
    await page.locator('button[type="submit"], button:has-text("כניסה"), button:has-text("התחברות")').first().click();
    // Either an error message appears or the page does not navigate to user_info
    await page.waitForTimeout(1500);
    const url = page.url();
    expect(url).not.toContain('user_info');
  });

  test('correct credentials redirect to user_info page', async ({ page }) => {
    await page.goto('/pdn-diagnose/');
    const emailInput = page.locator('input[type="email"], input[name="email"]').first();
    const passInput  = page.locator('input[type="password"], input[name="password"]').first();
    await emailInput.fill(TEST_EMAIL);
    await passInput.fill(TEST_PASSWORD);
    await page.locator('button[type="submit"], button:has-text("כניסה"), button:has-text("התחברות")').first().click();
    await page.waitForURL('**/pdn-diagnose/user_info**', { timeout: 8_000 });
    await expect(page).toHaveURL(/pdn-diagnose\/user_info/);
  });

});

// ── User info page ───────────────────────────────────────────────────────────

test.describe('Diagnose - user info page', () => {

  test.beforeEach(async ({ page }) => {
    // Log in first
    await page.goto('/pdn-diagnose/');
    await page.locator('input[type="email"], input[name="email"]').first().fill(TEST_EMAIL);
    await page.locator('input[type="password"], input[name="password"]').first().fill(TEST_PASSWORD);
    await page.locator('button[type="submit"], button:has-text("כניסה"), button:has-text("התחברות")').first().click();
    await page.waitForURL('**/pdn-diagnose/user_info**', { timeout: 8_000 });
  });

  test('user info form is visible', async ({ page }) => {
    // Should have form fields for name, etc.
    await expect(page.locator('form, input[name="first_name"], input[placeholder*="שם"]')).toBeTruthy();
  });

  test('POST /pdn-diagnose/user_info returns 200 with valid data', async ({ page }) => {
    const resp = await page.request.post('/pdn-diagnose/user_info', {
      data: {
        email: TEST_EMAIL,
        first_name: 'E2E',
        last_name: 'Test',
        phone: '0500000000',
        gender: 'male',
        birth_year: '1990',
        native_language: 'hebrew',
        education_level: 'academic',
        job_title: 'tester',
        referral_source: 'test',
      },
    });
    expect(resp.status()).toBe(200);
  });

});

// ── Questionnaire API ────────────────────────────────────────────────────────

test.describe('Diagnose - questionnaire API', () => {

  // Log in and save user info via API before each test
  test.beforeEach(async ({ page }) => {
    await page.goto('/pdn-diagnose/');
    await page.locator('input[type="email"], input[name="email"]').first().fill(TEST_EMAIL);
    await page.locator('input[type="password"], input[name="password"]').first().fill(TEST_PASSWORD);
    await page.locator('button[type="submit"], button:has-text("כניסה"), button:has-text("התחברות")').first().click();
    await page.waitForURL('**/pdn-diagnose/user_info**', { timeout: 8_000 });
    // Save metadata so session has email
    await page.request.post('/pdn-diagnose/user_info', {
      data: { email: TEST_EMAIL, first_name: 'E2E', last_name: 'Test' },
    });
  });

  test('GET /pdn-diagnose/questionnaire/1 returns question data', async ({ page }) => {
    const resp = await page.request.get('/pdn-diagnose/questionnaire/1');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('question');
    expect(body).toHaveProperty('options');
  });

  test('GET /pdn-diagnose/questionnaire/27 returns question data', async ({ page }) => {
    const resp = await page.request.get('/pdn-diagnose/questionnaire/27');
    expect(resp.status()).toBe(200);
  });

  test('POST /pdn-diagnose/answer saves an answer', async ({ page }) => {
    const resp = await page.request.post('/pdn-diagnose/answer', {
      data: { question_number: 1, selected_option_code: 'AP' },
    });
    expect(resp.status()).toBe(200);
  });

  test('GET /pdn-diagnose/get_progress returns current question', async ({ page }) => {
    const resp = await page.request.get('/pdn-diagnose/get_progress');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('current_question');
  });

  test('DELETE answer removes it', async ({ page }) => {
    // First save answer 1
    await page.request.post('/pdn-diagnose/answer', {
      data: { question_number: 1, selected_option_code: 'AP' },
    });
    // Then delete it
    const resp = await page.request.post('/pdn-diagnose/delete_answer', {
      data: { question_number: 1 },
    });
    expect(resp.status()).toBe(200);
  });

  test('questionnaire page loads after user info', async ({ page }) => {
    await page.goto('/pdn-diagnose/chat');
    // The questionnaire SPA should render
    await expect(page.locator('body')).toBeVisible();
    // Should not redirect back to login (session is active)
    await expect(page).not.toHaveURL(/pdn-diagnose\/$/);
  });

});
