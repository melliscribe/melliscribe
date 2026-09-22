// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Storage pressure (FR-021): warn before unprocessed recordings exhaust the
 * device's quota, rather than let the browser evict data quietly.
 */

export const WARN_AT_FRACTION = 0.8;

export interface StorageStatus {
  usedFraction: number;
  shouldWarn: boolean;
}

export function assessStorage(estimate: StorageEstimate): StorageStatus | null {
  const { usage, quota } = estimate;
  if (usage === undefined || quota === undefined || quota === 0) return null;
  const usedFraction = usage / quota;
  return { usedFraction, shouldWarn: usedFraction >= WARN_AT_FRACTION };
}

export async function checkStorage(): Promise<StorageStatus | null> {
  if (!navigator.storage?.estimate) return null;
  return assessStorage(await navigator.storage.estimate());
}

/** Ask the browser not to evict our data under pressure. Best effort. */
export async function requestPersistence(): Promise<boolean> {
  return navigator.storage?.persist ? navigator.storage.persist() : false;
}
