// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * The language setting, available offline (FR-026, FR-026a).
 *
 * The device copy is what capture uses, so starting a recording never needs
 * the network and never asks for a language. It is never inferred from the
 * browser or the network: the default is French until the beekeeper says
 * otherwise, and the server copy wins once reachable.
 */
import type { CaptureDb, Language } from "./db";

const KEY = "language";
export const DEFAULT_LANGUAGE: Language = "fr";

export async function loadLanguage(db: CaptureDb): Promise<Language> {
  return (await db.getSetting<Language>(KEY)) ?? DEFAULT_LANGUAGE;
}

export async function storeLanguage(db: CaptureDb, language: Language): Promise<void> {
  await db.putSetting(KEY, language);
}
