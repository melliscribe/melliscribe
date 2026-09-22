// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * What is waiting and what failed (FR-018, US2): recordings still on the phone,
 * and the server's queue with each failure's stage and reason. A failed
 * recording is retried without re-recording (FR-019).
 */
import { useCallback, useEffect, useState } from "react";

import { api, type Recording } from "../api/client";
import { useI18n } from "../i18n";
import type { CaptureDb, PendingUpload } from "../offline/db";

const SERVER_STATES = new Set(["uploaded", "transcribing", "extracting", "failed", "no_inspection"]);

export function PendingList({ db }: { db: CaptureDb }) {
  const { t, formatDate } = useI18n();
  const [local, setLocal] = useState<PendingUpload[]>([]);
  const [remote, setRemote] = useState<Recording[] | null>(null);

  const load = useCallback(async () => {
    setLocal(await db.listPending());
    try {
      setRemote((await api.listRecordings()).filter((r) => SERVER_STATES.has(r.state)));
    } catch {
      setRemote(null);
    }
  }, [db]);

  useEffect(() => {
    void load();
  }, [load]);

  if (local.length === 0 && (remote ?? []).length === 0) return <p>{t("ui.pending.empty")}</p>;
  return (
    <ul className="stack" style={{ listStyle: "none", padding: 0 }}>
      {local.map((entry) => (
        <li key={entry.id} className={`field ${entry.state === "rejected" ? "flagged" : ""}`}>
          {formatDate(entry.capturedAt)} — {t(`ui.pending.state.pending_upload`)}
          {entry.state === "rejected" && <p>{t("ui.capture.rejected", { count: 1 })}</p>}
        </li>
      ))}
      {remote === null && <li className="notice warn">{t("ui.error.network")}</li>}
      {(remote ?? []).map((recording) => (
        <li key={recording.id} className={`field ${recording.state === "failed" ? "flagged" : ""}`}>
          <div>
            {formatDate(recording.captured_on)} — {t(`ui.pending.state.${recording.state}`)}
          </div>
          {recording.state === "failed" && recording.failure_stage && (
            <p>{t("ui.pending.failed_at", { stage: t(`ui.pending.stage.${recording.failure_stage}`) })}</p>
          )}
          {recording.state === "no_inspection" && <p>{t("ui.pending.no_inspection_help")}</p>}
          {recording.state === "failed" && (
            <button type="button" onClick={() => void api.retryRecording(recording.id).then(load)}>
              {t("ui.pending.retry")}
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
