// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/** Principle VIII: both catalogues hold the same keys, and formatting follows the locale. */
import { describe, expect, it } from "vitest";

import en from "../../src/i18n/en.json";
import fr from "../../src/i18n/fr.json";
import { formatDate, formatNumber, translate } from "../../src/i18n";

function keys(node: unknown, prefix = ""): string[] {
  if (typeof node !== "object" || node === null) return [prefix];
  return Object.entries(node).flatMap(([k, v]) => keys(v, prefix ? `${prefix}.${k}` : k));
}

describe("catalogues", () => {
  it("hold exactly the same keys in both languages", () => {
    expect(keys(fr).sort()).toEqual(keys(en).sort());
  });

  it("interpolate parameters", () => {
    expect(translate("en", "ui.capture.pending_count", { count: 2 })).toBe(
      "2 recording(s) waiting to be sent",
    );
  });

  it("never fall back silently to the other language", () => {
    expect(translate("fr", "ui.nope")).toBe("ui.nope");
  });
});

describe("locale formatting (FR-025a)", () => {
  it("formats dates per language", () => {
    expect(formatDate("fr", "2026-05-12")).toBe("12 mai 2026");
    expect(formatDate("en", "2026-05-12")).toBe("12 May 2026");
  });

  it("formats numbers per language", () => {
    expect(formatNumber("fr", 1234.5)).toMatch(/1\s234,5/);
    expect(formatNumber("en", 1234.5)).toBe("1,234.5");
  });
});
