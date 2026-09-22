// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Vocabulary values for the pickers. The catalogue holds a label for every
 * value (CI-enforced), so its keys are the list of values to offer.
 */
import fr from "../i18n/fr.json";

export const VOCABULARY_FIELDS = [
  "queen_seen",
  "brood",
  "brood_pattern",
  "stores",
  "temperament",
] as const;
export type VocabularyField = (typeof VOCABULARY_FIELDS)[number];

export function listValues(field: VocabularyField): string[] {
  return Object.keys(fr.vocabulary[field]);
}

/** Frame counts: numbers in half-frame steps, no vocabulary (FR-006j). */
export const COUNT_FIELDS = ["brood_frames", "stores_frames", "bee_frames"] as const;
export type CountField = (typeof COUNT_FIELDS)[number];

/** The picker's range; the extraction limit above which a count is flagged. */
export const MAX_FRAMES = 40;
