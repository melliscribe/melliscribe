// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Vocabulary values for the pickers. The catalogue holds a label for every
 * value (CI-enforced), so its keys are the list of values to offer.
 */
import fr from "../i18n/fr.json";

export const VOCABULARY_FIELDS = ["queen_seen", "brood", "stores", "temperament"] as const;
export type VocabularyField = (typeof VOCABULARY_FIELDS)[number];

export function listValues(field: VocabularyField): string[] {
  return Object.keys(fr.vocabulary[field]);
}
