// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * US1 at the hive: airplane mode, dictate, and get an explicit confirmation
 * that the recording is safe — with the recording actually in IndexedDB.
 */
import { expect, test } from "@playwright/test";

test("a dictation is stored and confirmed with no network", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByTestId("active-language")).toBeVisible();
  await context.setOffline(true);

  const record = page.getByRole("button", { name: /Commencer la dictée|Start dictating/ });
  await record.click();
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: /Terminer|Finish/ }).click();

  await expect(page.getByTestId("saved-confirmation")).toBeVisible();
  const queued = await page.evaluate(
    () =>
      new Promise<number>((resolve, reject) => {
        const open = indexedDB.open("melliscribe");
        open.onerror = () => reject(open.error);
        open.onsuccess = () => {
          const count = open.result.transaction("queue").objectStore("queue").count();
          count.onsuccess = () => resolve(count.result);
        };
      }),
  );
  expect(queued).toBe(1);
});

test("starting a recording asks no language question (FR-026a)", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Commencer la dictée|Start dictating/ }).click();
  await expect(page.getByRole("button", { name: /Terminer|Finish/ })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
