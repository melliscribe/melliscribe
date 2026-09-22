// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * One field under review: its status, value or proposal, why it is flagged,
 * and the words it was heard as (FR-006b, FR-009). The confidence score is
 * never shown as a number — the status is the beekeeper-facing signal (FR-009).
 */
import type { ReactNode } from "react";

import type { components } from "../api/generated/schema";
import { useI18n } from "../i18n";
import { FieldPlayback } from "./FieldPlayback";

type SegmentRef = components["schemas"]["SegmentRef"];

export interface ReviewedField {
  status: components["schemas"]["FieldStatus"];
  value?: unknown;
  proposal?: unknown;
  verbatim?: string[];
  segment_refs?: SegmentRef[];
  flag_reason?: components["schemas"]["FlagReason"] | null;
}

export function FieldRow({
  label,
  field,
  renderValue,
  recordingId,
  audioAvailable,
  children,
}: {
  label: string;
  field: ReviewedField;
  renderValue: (value: unknown) => string;
  recordingId: string;
  audioAvailable: boolean;
  children?: ReactNode;
}) {
  const { t } = useI18n();
  const flagged = field.status === "uncertain" || field.status === "unknown";
  const [firstRef] = field.segment_refs ?? [];
  return (
    <article className={`field ${flagged ? "flagged" : ""}`} data-testid={`field-${label}`}>
      <h3>
        {label} <span className={`status ${field.status}`}>{t(`status.${field.status}`)}</span>
      </h3>
      {field.value !== null && field.value !== undefined && (
        <p className="value">{renderValue(field.value)}</p>
      )}
      {field.proposal !== null && field.proposal !== undefined && (
        <p className="value">{t("ui.review.proposal", { value: renderValue(field.proposal) })}</p>
      )}
      {field.flag_reason && <p>{t(`flag_reason.${field.flag_reason}`)}</p>}
      {(field.verbatim ?? []).map((phrase) => (
        <p key={phrase} className="verbatim">
          {t("ui.review.heard_as", { phrase })}
        </p>
      ))}
      {firstRef && (
        <FieldPlayback
          recordingId={recordingId}
          audioAvailable={audioAvailable}
          startSeconds={firstRef.start_seconds}
          endSeconds={firstRef.end_seconds}
        />
      )}
      {children}
    </article>
  );
}
