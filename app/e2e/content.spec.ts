import { expect, test } from '@playwright/test';

// Phase 5d — Content API + library/reader. These specs pin the behaviour that
// was manually verified when 5d shipped; extend them as 5e+ add interactivity.

test('library lists the grouped corpus', async ({ page }) => {
  await page.goto('/library');
  await expect(page.getByRole('heading', { name: 'Library' })).toBeVisible();
  await expect(page.getByText(/\d+ pages\./)).toBeVisible();
  // Category groups render.
  await expect(page.getByText('Course', { exact: true })).toBeVisible();
  await expect(page.getByText('Entry Models', { exact: true })).toBeVisible();
  await expect(page.getByText('Frontier / Advanced', { exact: true })).toBeVisible();
});

test('reader renders markdown (headings + GFM table)', async ({ page }) => {
  await page.goto('/concepts/quarterly-theory');
  await expect(
    page.getByRole('heading', { name: /Quarterly Theory/, level: 1 })
  ).toBeVisible();
  // remark-gfm table cells from the "Daily quarters" table.
  await expect(page.getByRole('cell', { name: 'Accumulation' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'Q1' })).toBeVisible();
});

test('frontier concept shows its TIER/label + watch-only enforcement', async ({ page }) => {
  await page.goto('/concepts/quarterly-theory');
  await expect(page.getByText('EMERGING', { exact: true })).toBeVisible();
  await expect(page.getByText('Tier 2', { exact: true })).toBeVisible();
  await expect(page.getByText(/Study & watch/)).toBeVisible();
  await expect(page.getByText(/Never gate-eligible/)).toBeVisible();
});

test('wikilink click-through navigates within the SPA', async ({ page }) => {
  await page.goto('/concepts/quarterly-theory');
  await page.getByRole('link', { name: /Power of Three/ }).first().click();
  await expect(page).toHaveURL(/\/concepts\/power-of-three$/);
  await expect(
    page.getByRole('heading', { name: /Power of Three/, level: 1 })
  ).toBeVisible();
});

test('unresolved wikilink renders inert (not a link)', async ({ page }) => {
  await page.goto('/concepts/swing-points');
  // The [[entities/people/doomer]] ref is outside the corpus → inert span.
  const inert = page.locator('.prose span[title="Not in the ingested course corpus"]');
  await expect(inert.first()).toBeVisible();
  // And it is NOT rendered as a navigable link.
  await expect(page.getByRole('link', { name: 'entities/people/doomer' })).toHaveCount(0);
});

test('search filters the corpus', async ({ page }) => {
  await page.goto('/library');
  await page.getByRole('textbox', { name: 'Search content' }).fill('silver bullet');
  await expect(
    page.getByRole('link', { name: /Silver Bullet/ })
  ).toBeVisible();
  // A non-matching course lesson drops out of the results.
  await expect(page.getByRole('link', { name: 'Module 1, Lesson 1: What Moves the Market' })).toHaveCount(0);
});
