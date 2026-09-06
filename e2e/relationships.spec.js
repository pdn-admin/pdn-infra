// @ts-check
const { test, expect } = require('@playwright/test');

// Same UserManager seed credentials as Binat
const USER_EMAIL    = 'tomergur@gmail.com';
const USER_PASSWORD = 'pdn';
const USER_PDN_CODE = 'e5';
const PARTNER_CODE  = 'a7';
const REL_TYPE      = 'partner';

// ── Login page ────────────────────────────────────────────────────────────────

test.describe('Relationships - login page', () => {

  test('renders login form', async ({ page }) => {
    await page.goto('/pdn-relationships/');
    await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"], input[name="password"]')).toBeVisible();
  });

  test('page has partner code and relationship type inputs', async ({ page }) => {
    await page.goto('/pdn-relationships/');
    // Should have a selector/input for partner PDN code
    const hasPartnerInput = await page.locator(
      'input[name="partner_code"], select[name="partner_code"], [id*="partner"], [placeholder*="קוד"]'
    ).count();
    expect(hasPartnerInput).toBeGreaterThan(0);
  });

});

// ── Login API ─────────────────────────────────────────────────────────────────

test.describe('Relationships - login API', () => {

  test('POST /pdn-relationships/login with valid data returns success', async ({ page }) => {
    const resp = await page.request.post('/pdn-relationships/login', {
      data: {
        email:             USER_EMAIL,
        password:          USER_PASSWORD,
        partner_code:      PARTNER_CODE,
        relationship_type: REL_TYPE,
      },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.success).toBe(true);
    expect(body).toHaveProperty('pdn_code');
    expect(body).toHaveProperty('partner_code', PARTNER_CODE);
    expect(body).toHaveProperty('relationship_type', REL_TYPE);
  });

  test('POST /pdn-relationships/login with wrong password returns 401', async ({ page }) => {
    const resp = await page.request.post('/pdn-relationships/login', {
      data: {
        email:             USER_EMAIL,
        password:          'wrongpassword',
        partner_code:      PARTNER_CODE,
        relationship_type: REL_TYPE,
      },
    });
    expect(resp.status()).toBe(401);
  });

  test('POST /pdn-relationships/login with invalid partner_code returns 400', async ({ page }) => {
    const resp = await page.request.post('/pdn-relationships/login', {
      data: {
        email:             USER_EMAIL,
        password:          USER_PASSWORD,
        partner_code:      'xx99',          // invalid code
        relationship_type: REL_TYPE,
      },
    });
    expect(resp.status()).toBe(400);
  });

  test('POST /pdn-relationships/login with invalid relationship_type returns 400', async ({ page }) => {
    const resp = await page.request.post('/pdn-relationships/login', {
      data: {
        email:             USER_EMAIL,
        password:          USER_PASSWORD,
        partner_code:      PARTNER_CODE,
        relationship_type: 'enemy',         // invalid type
      },
    });
    expect(resp.status()).toBe(400);
  });

  test('relationship types colleague / friend also work', async ({ page }) => {
    for (const relType of ['colleague', 'friend']) {
      const resp = await page.request.post('/pdn-relationships/login', {
        data: {
          email:             USER_EMAIL,
          password:          USER_PASSWORD,
          partner_code:      PARTNER_CODE,
          relationship_type: relType,
        },
      });
      expect(resp.status()).toBe(200);
    }
  });

  test('all 12 PDN codes accepted as partner_code', async ({ page }) => {
    const codes = ['a3','a7','a11','e1','e5','e9','p2','p6','p10','t4','t8','t12'];
    for (const code of codes) {
      const resp = await page.request.post('/pdn-relationships/login', {
        data: {
          email:             USER_EMAIL,
          password:          USER_PASSWORD,
          partner_code:      code,
          relationship_type: REL_TYPE,
        },
      });
      expect(resp.status()).toBe(200);
    }
  });

});

// ── Chat page ─────────────────────────────────────────────────────────────────

test.describe('Relationships - chat page', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/pdn-relationships/');
    // Log in via UI - find form fields generically
    await page.locator('input[type="email"], input[name="email"]').first().fill(USER_EMAIL);
    await page.locator('input[type="password"], input[name="password"]').first().fill(USER_PASSWORD);

    // Fill partner_code - could be input or select
    const partnerEl = page.locator('input[name="partner_code"], select[name="partner_code"]').first();
    const tagName = await partnerEl.evaluate(el => el.tagName.toLowerCase());
    if (tagName === 'select') {
      await partnerEl.selectOption(PARTNER_CODE);
    } else {
      await partnerEl.fill(PARTNER_CODE);
    }

    // Fill relationship type
    const relEl = page.locator('input[name="relationship_type"], select[name="relationship_type"]').first();
    const relTag = await relEl.evaluate(el => el.tagName.toLowerCase());
    if (relTag === 'select') {
      await relEl.selectOption(REL_TYPE);
    } else {
      await relEl.fill(REL_TYPE);
    }

    await page.locator('button[type="submit"], button:has-text("כניסה"), button:has-text("התחברות")').first().click();
    await page.waitForURL('**/pdn-relationships/chat-page**', { timeout: 10_000 });
  });

  test('chat page renders after login', async ({ page }) => {
    await expect(page).toHaveURL(/pdn-relationships\/chat-page/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('chat page shows PDN codes', async ({ page }) => {
    // The page should reference the user's and partner's codes somewhere
    const body = await page.locator('body').textContent();
    expect(body).toContain(USER_PDN_CODE.toUpperCase());
  });

  test('chat page has message input', async ({ page }) => {
    const chatInput = page.locator(
      'input[type="text"], textarea, [contenteditable="true"], input[placeholder*="הודעה"]'
    );
    await expect(chatInput.first()).toBeVisible({ timeout: 8_000 });
  });

});
