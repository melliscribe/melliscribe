// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Translation and locale formatting (Principle VIII).
 *
 * Every beekeeper-facing string comes from `fr.json` / `en.json`. A missing key
 * fails CI (`melliscribe vocabulary check`), and at runtime renders the key
 * itself rather than silently falling back to the other language.
 */
import { createContext, useContext, useMemo, type ReactNode } from "react";

import en from "./en.json";
import fr from "./fr.json";

export type Language = "fr" | "en";
type Catalogue = Record<string, unknown>;

const CATALOGUES: Record<Language, Catalogue> = { fr, en };
const LOCALES: Record<Language, string> = { fr: "fr-FR", en: "en-GB" };

export function lookup(catalogue: Catalogue, key: string): string | undefined {
  let node: unknown = catalogue;
  for (const part of key.split(".")) {
    if (typeof node !== "object" || node === null) return undefined;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "string" ? node : undefined;
}

export function translate(
  language: Language,
  key: string,
  params: Record<string, string | number> = {},
): string {
  const template = lookup(CATALOGUES[language], key) ?? key;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

/** Format an ISO date (`YYYY-MM-DD`) for the active language (FR-025a). */
export function formatDate(language: Language, isoDate: string): string {
  const [year, month, day] = isoDate.slice(0, 10).split("-").map(Number);
  const date = new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1));
  return new Intl.DateTimeFormat(LOCALES[language], {
    dateStyle: "long",
    timeZone: "UTC",
  }).format(date);
}

export function formatNumber(language: Language, value: number): string {
  return new Intl.NumberFormat(LOCALES[language]).format(value);
}

export interface I18n {
  language: Language;
  t: (key: string, params?: Record<string, string | number>) => string;
  formatDate: (isoDate: string) => string;
  formatNumber: (value: number) => string;
}

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ language, children }: { language: Language; children: ReactNode }) {
  const value = useMemo<I18n>(
    () => ({
      language,
      t: (key, params) => translate(language, key, params),
      formatDate: (isoDate) => formatDate(language, isoDate),
      formatNumber: (n) => formatNumber(language, n),
    }),
    [language],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const i18n = useContext(I18nContext);
  if (i18n === null) throw new Error("useI18n outside I18nProvider");
  return i18n;
}
