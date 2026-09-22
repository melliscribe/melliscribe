// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * The capture screen (US1).
 *
 * The confirmation is shown only after the recording has been committed to
 * IndexedDB (FR-002). The active language is on screen without any action
 * (FR-026d), and starting a recording asks no language question (FR-026a).
 */
import { useEffect, useRef, useState } from "react";

import { api, type ExpiringRecording } from "../api/client";
import { useI18n } from "../i18n";
import type { CaptureDb, Language, PendingUpload } from "../offline/db";
import { checkStorage } from "../offline/quota";
import type { UploadQueue } from "../offline/queue";
import { CaptureControls } from "./CaptureControls";
import { FileImport } from "./FileImport";
import { Recorder } from "./recorder";

/** Warn this far ahead of audio expiry (FR-027e). */
const EXPIRY_WARNING_DAYS = 14;

type Status = "idle" | "recording" | "saving" | "saved" | "save_failed" | "mic_denied";

export function CaptureScreen({
  db,
  queue,
  language,
}: {
  db: CaptureDb;
  queue: UploadQueue;
  language: Language;
}) {
  const { t } = useI18n();
  const recorder = useRef(new Recorder());
  const [status, setStatus] = useState<Status>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [pending, setPending] = useState<PendingUpload[]>([]);
  const [storageWarning, setStorageWarning] = useState<number | null>(null);
  const [expiring, setExpiring] = useState<ExpiringRecording[]>([]);

  const refresh = async () => {
    setPending(await db.listPending());
    const storage = await checkStorage();
    setStorageWarning(storage?.shouldWarn ? Math.round(storage.usedFraction * 100) : null);
  };

  useEffect(() => {
    api.listExpiring(EXPIRY_WARNING_DAYS).then(setExpiring, () => setExpiring([]));
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (status !== "recording") return;
    const timer = window.setInterval(() => setElapsed(recorder.current.elapsedSeconds), 250);
    return () => window.clearInterval(timer);
  }, [status]);

  const start = async () => {
    try {
      await recorder.current.start();
      setElapsed(0);
      setStatus("recording");
    } catch {
      setStatus("mic_denied");
    }
  };

  const stop = async () => {
    setStatus("saving");
    const finished = await recorder.current.stop();
    try {
      await db.saveRecording({ ...finished, language });
    } catch {
      setStatus("save_failed");
      return;
    }
    setStatus("saved");
    await refresh();
    void queue.flush().then(refresh);
  };

  const waiting = pending.filter((p) => p.state === "pending_upload").length;
  const rejected = pending.filter((p) => p.state === "rejected").length;

  return (
    <section className="stack" aria-labelledby="capture-title">
      <h1 id="capture-title" className="language-badge" data-testid="active-language">
        {t("ui.capture.language_active", { language: t(`language.${language}`) })}
      </h1>
      <CaptureControls
        recording={status === "recording"}
        elapsedSeconds={elapsed}
        disabled={status === "saving"}
        onStart={() => void start()}
        onStop={() => void stop()}
      />
      {status === "saved" && (
        <p className="notice ok" role="status" data-testid="saved-confirmation">
          {t("ui.capture.saved")}
        </p>
      )}
      {status === "save_failed" && <p className="notice warn" role="alert">{t("ui.capture.save_failed")}</p>}
      {status === "mic_denied" && <p className="notice warn" role="alert">{t("ui.capture.mic_denied")}</p>}
      {waiting > 0 && <p className="notice">{t("ui.capture.pending_count", { count: waiting })}</p>}
      {rejected > 0 && <p className="notice warn">{t("ui.capture.rejected", { count: rejected })}</p>}
      {storageWarning !== null && (
        <p className="notice warn" role="alert">
          {t("ui.capture.storage_warning", { percent: storageWarning })}
        </p>
      )}
      {expiring.length > 0 && (
        <div className="notice warn" role="status">
          <p>{t("ui.capture.expiring", { count: expiring.length, days: EXPIRY_WARNING_DAYS })}</p>
          {expiring.some((e) => e.needs_attention) && (
            <p>
              <strong>
                {t("ui.capture.expiring_attention", {
                  count: expiring.filter((e) => e.needs_attention).length,
                })}
              </strong>
            </p>
          )}
        </div>
      )}
      <FileImport db={db} queue={queue} language={language} onSaved={() => void refresh()} />
    </section>
  );
}
