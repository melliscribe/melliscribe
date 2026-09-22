// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Gloved-hands correction (FR-004, SC-006): every choice is a large button,
 * so a correction is one tap — no dropdown, no typing, no precision.
 */
import { useI18n } from "../i18n";
import { listValues, type VocabularyField } from "./vocabulary";

export function FieldEditor({
  field,
  onChoose,
  onCancel,
}: {
  field: VocabularyField;
  onChoose: (value: string | null) => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="stack">
      <div className="choices">
        {listValues(field).map((value) => (
          <button key={value} type="button" onClick={() => onChoose(value)}>
            {t(`vocabulary.${field}.${value}`)}
          </button>
        ))}
        <button type="button" onClick={() => onChoose(null)}>
          {t("ui.review.not_observed")}
        </button>
      </div>
      <button type="button" onClick={onCancel}>
        {t("ui.review.cancel")}
      </button>
    </div>
  );
}
