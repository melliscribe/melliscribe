// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Set a frame count with gloves on (FR-004, FR-006j): one tap on a whole
 * number, then large half-frame steps. A flagged count starts from nothing —
 * no suggested number is offered for an approximate count (FR-006k).
 */
import { useState } from "react";

import { useI18n } from "../i18n";
import { MAX_FRAMES } from "./vocabulary";

const QUICK_VALUES = Array.from({ length: 13 }, (_, i) => i);

export function CountPicker({
  initial,
  onChoose,
  onCancel,
}: {
  initial: number | null;
  onChoose: (value: number | null) => void;
  onCancel: () => void;
}) {
  const { t, formatNumber } = useI18n();
  const [value, setValue] = useState<number | null>(initial);
  const step = (delta: number) =>
    setValue((current) => Math.min(MAX_FRAMES, Math.max(0, (current ?? 0) + delta)));
  return (
    <div className="stack">
      <p className="value" aria-live="polite" data-testid="count-value">
        {value === null ? "—" : t("ui.review.frames", { count: formatNumber(value) })}
      </p>
      <div className="row">
        <button type="button" onClick={() => step(-0.5)} disabled={value === null || value <= 0}>
          {t("ui.review.count_less")}
        </button>
        <button type="button" onClick={() => step(0.5)} disabled={value !== null && value >= MAX_FRAMES}>
          {t("ui.review.count_more")}
        </button>
      </div>
      <div className="choices">
        {QUICK_VALUES.map((n) => (
          <button key={n} type="button" aria-pressed={value === n} onClick={() => setValue(n)}>
            {formatNumber(n)}
          </button>
        ))}
      </div>
      <div className="row">
        <button type="button" className="primary" disabled={value === null} onClick={() => onChoose(value)}>
          {t("ui.review.save")}
        </button>
        <button type="button" onClick={() => onChoose(null)}>
          {t("ui.review.not_observed")}
        </button>
        <button type="button" onClick={onCancel}>
          {t("ui.review.cancel")}
        </button>
      </div>
    </div>
  );
}
