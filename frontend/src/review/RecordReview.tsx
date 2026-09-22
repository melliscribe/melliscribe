// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Review one record (FR-022): every field's status and source phrase, one-tap
 * corrections, hive resolution, language correction, whole-record confirmation.
 * Review is optional — an unconfirmed record is a valid saved state (FR-024).
 */
import { useCallback, useEffect, useState } from "react";

import { api, ApiError, type RecordPatch, type RecordView, type Recording } from "../api/client";
import { useI18n } from "../i18n";
import { FieldEditor } from "./FieldEditor";
import { FieldRow } from "./FieldRow";
import { HiveResolver } from "./HiveResolver";
import { VOCABULARY_FIELDS, type VocabularyField } from "./vocabulary";

export function RecordReview({ recordId, onBack }: { recordId: string; onBack: () => void }) {
  const { t, formatDate, language } = useI18n();
  const [record, setRecord] = useState<RecordView | null>(null);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [hiveNames, setHiveNames] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const loaded = await api.getRecord(recordId);
    setRecord(loaded);
    setRecording(await api.getRecording(loaded.recording_id));
    const hives = await api.listHives();
    setHiveNames(Object.fromEntries(hives.map((h) => [h.id, h.identifier])));
  }, [recordId]);

  useEffect(() => {
    load().catch((error: unknown) => setMessage(describe(error)));
  }, [load]);

  const describe = (error: unknown) =>
    error instanceof ApiError && error.body ? error.body.message : t("ui.error.network");

  const run = async (action: () => Promise<RecordView | void>) => {
    setMessage(null);
    try {
      const updated = await action();
      if (updated) setRecord(updated);
      setEditing(null);
    } catch (error) {
      setMessage(describe(error));
    }
  };

  if (record === null) return <p>{message ?? "…"}</p>;

  const patch = (changes: Omit<RecordPatch, "version">) =>
    run(() => api.patchRecord(record.id, { version: record.version, ...changes }));

  const detected = record.detected_language;
  const mismatch = detected && detected !== record.language;

  return (
    <section className="stack">
      <button type="button" onClick={onBack}>
        {t("ui.review.back")}
      </button>
      {message && <p className="notice warn" role="alert">{message}</p>}
      {recording?.reprocess_failed && <p className="notice warn">{t("ui.review.reprocess_failed")}</p>}
      {mismatch && (
        <div className="notice warn stack">
          <p>
            {t("ui.review.language_mismatch", {
              detected: t(`language.${detected}`),
              language: t(`language.${record.language}`),
            })}
          </p>
          <button
            type="button"
            onClick={() =>
              void run(async () => {
                await api.reprocessRecording(record.recording_id, detected);
                setMessage(t("ui.review.reprocess_started"));
              })
            }
          >
            {t("ui.review.reprocess_in", { language: t(`language.${detected}`) })}
          </button>
        </div>
      )}

      <FieldRow
        label={t("field.hive")}
        field={record.hive}
        renderValue={(id) => hiveNames[String(id)] ?? String(id)}
        recordingId={record.recording_id}
        audioAvailable={record.audio_available}
      >
        {record.hive.value == null && (
          <HiveResolver
            spokenIdentifier={record.spoken_hive_identifier}
            onResolve={(choice) => void run(() => api.resolveHive(record.id, choice))}
          />
        )}
      </FieldRow>

      <FieldRow
        label={t("field.inspection_date")}
        field={record.inspection_date}
        renderValue={(value) => formatDate(String(value))}
        recordingId={record.recording_id}
        audioAvailable={record.audio_available}
      >
        <p>{t("ui.review.captured_on", { date: formatDate(record.captured_on) })}</p>
        {editing === "inspection_date" ? (
          <input
            type="date"
            lang={language}
            defaultValue={String(record.inspection_date.value ?? record.inspection_date.proposal ?? "")}
            onChange={(event) => void patch({ inspection_date: event.target.value || null })}
          />
        ) : (
          <FieldActions
            status={record.inspection_date.status}
            onAccept={() =>
              void patch({
                inspection_date: (record.inspection_date.value ??
                  record.inspection_date.proposal ??
                  null) as string | null,
              })
            }
            onEdit={() => setEditing("inspection_date")}
          />
        )}
      </FieldRow>

      {VOCABULARY_FIELDS.map((name: VocabularyField) => {
        const field = record[name];
        return (
          <FieldRow
            key={name}
            label={t(`field.${name}`)}
            field={field}
            renderValue={(value) => t(`vocabulary.${name}.${String(value)}`)}
            recordingId={record.recording_id}
            audioAvailable={record.audio_available}
          >
            {editing === name ? (
              <FieldEditor
                field={name}
                onChoose={(value) => void patch({ [name]: value })}
                onCancel={() => setEditing(null)}
              />
            ) : (
              <FieldActions
                status={field.status}
                onAccept={() => void patch({ [name]: field.value ?? field.proposal ?? null })}
                onEdit={() => setEditing(name)}
              />
            )}
          </FieldRow>
        );
      })}

      <TreatmentsAndActions record={record} onSave={(changes) => void patch(changes)} />

      <button
        type="button"
        className="primary"
        onClick={() => void run(() => api.confirmRecord(record.id))}
        disabled={record.confirmed_at != null}
      >
        {record.confirmed_at != null ? t("ui.review.confirmed") : t("ui.review.confirm_record")}
      </button>

      <details>
        <summary>{t("ui.review.transcript")}</summary>
        {record.transcript.segments.map((segment, index) => (
          <p key={index}>{segment.text}</p>
        ))}
      </details>

      {recording && (
        <label className="row">
          <input
            type="checkbox"
            style={{ minWidth: "var(--target)" }}
            checked={recording.eval_consent_at != null}
            onChange={(event) =>
              void api
                .setEvalConsent(recording.id, event.target.checked)
                .then(setRecording, (error: unknown) => setMessage(describe(error)))
            }
          />
          <span>
            {t("ui.review.eval_consent")}
            {recording.eval_consent_at != null &&
              ` — ${t("ui.review.eval_consent_given", { date: formatDate(recording.eval_consent_at) })}`}
          </span>
        </label>
      )}

      {record.audio_available && (
        <button
          type="button"
          onClick={() => {
            if (window.confirm(t("ui.review.delete_audio_confirm"))) {
              void run(async () => {
                await api.deleteRecordingAudio(record.recording_id);
                await load();
              });
            }
          }}
        >
          {t("ui.review.delete_audio")}
        </button>
      )}
    </section>
  );
}

function FieldActions({
  status,
  onAccept,
  onEdit,
}: {
  status: string;
  onAccept: () => void;
  onEdit: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="row">
      {status !== "confirmed" && (
        <button type="button" onClick={onAccept}>
          {t("ui.review.accept")}
        </button>
      )}
      <button type="button" onClick={onEdit}>
        {t("ui.review.edit")}
      </button>
    </div>
  );
}

function TreatmentsAndActions({
  record,
  onSave,
}: {
  record: RecordView;
  onSave: (changes: Omit<RecordPatch, "version">) => void;
}) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [treatments, setTreatments] = useState(
    (record.treatments ?? []).map((tr) => ({
      product: String(tr.product.value ?? tr.product.proposal ?? ""),
      dose: String(tr.dose.value ?? tr.dose.proposal ?? ""),
    })),
  );
  const [actions, setActions] = useState(
    (record.actions_to_do ?? []).map((a) => String(a.text.value ?? a.text.proposal ?? "")),
  );
  const shared = { recordingId: record.recording_id, audioAvailable: record.audio_available };
  if (!editing) {
    return (
      <div className="stack">
        <h2>{t("field.treatments")}</h2>
        {(record.treatments ?? []).map((treatment, index) => (
          <div key={index} className="stack">
            <FieldRow label={t("field.treatment_product")} field={treatment.product} renderValue={String} {...shared} />
            <FieldRow label={t("field.treatment_dose")} field={treatment.dose} renderValue={String} {...shared} />
          </div>
        ))}
        <h2>{t("field.actions_to_do")}</h2>
        {(record.actions_to_do ?? []).map((action, index) => (
          <FieldRow key={index} label={t("ui.review.action_text")} field={action.text} renderValue={String} {...shared} />
        ))}
        <button type="button" onClick={() => setEditing(true)}>
          {t("ui.review.edit")}
        </button>
      </div>
    );
  }
  return (
    <div className="stack">
      <h2>{t("field.treatments")}</h2>
      {treatments.map((treatment, index) => (
        <div key={index} className="row">
          <input
            aria-label={t("field.treatment_product")}
            value={treatment.product}
            onChange={(e) =>
              setTreatments(treatments.map((x, i) => (i === index ? { ...x, product: e.target.value } : x)))
            }
          />
          <input
            aria-label={t("field.treatment_dose")}
            value={treatment.dose}
            onChange={(e) =>
              setTreatments(treatments.map((x, i) => (i === index ? { ...x, dose: e.target.value } : x)))
            }
          />
          <button type="button" onClick={() => setTreatments(treatments.filter((_, i) => i !== index))}>
            {t("ui.review.remove")}
          </button>
        </div>
      ))}
      <button type="button" onClick={() => setTreatments([...treatments, { product: "", dose: "" }])}>
        {t("ui.review.add_treatment")}
      </button>
      <h2>{t("field.actions_to_do")}</h2>
      {actions.map((action, index) => (
        <div key={index} className="row">
          <input
            aria-label={t("ui.review.action_text")}
            value={action}
            onChange={(e) => setActions(actions.map((x, i) => (i === index ? e.target.value : x)))}
          />
          <button type="button" onClick={() => setActions(actions.filter((_, i) => i !== index))}>
            {t("ui.review.remove")}
          </button>
        </div>
      ))}
      <button type="button" onClick={() => setActions([...actions, ""])}>
        {t("ui.review.add_action")}
      </button>
      <div className="row">
        <button
          type="button"
          className="primary"
          onClick={() => {
            onSave({
              treatments: treatments.filter((x) => x.product.trim()),
              actions_to_do: actions.filter((x) => x.trim()),
            });
            setEditing(false);
          }}
        >
          {t("ui.review.save")}
        </button>
        <button type="button" onClick={() => setEditing(false)}>
          {t("ui.review.cancel")}
        </button>
      </div>
    </div>
  );
}
