// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Submit an existing audio file (US2, FR-005): a voice memo or a handheld
 * recorder's file goes through the same durable queue as a live dictation, so
 * it is never lost either. An unsupported format is refused by the server with
 * a 415 and the file stays on the phone, marked for the beekeeper.
 */
import { useState } from "react";

import { useI18n } from "../i18n";
import type { CaptureDb, Language } from "../offline/db";
import type { UploadQueue } from "../offline/queue";
import { formatCapturedAt } from "./recorder";

export function FileImport({
  db,
  queue,
  language,
  onSaved,
}: {
  db: CaptureDb;
  queue: UploadQueue;
  language: Language;
  onSaved: () => void;
}) {
  const { t } = useI18n();
  const [saved, setSaved] = useState(false);

  const onFile = async (file: File) => {
    await db.saveRecording({
      id: crypto.randomUUID(),
      capturedAt: formatCapturedAt(new Date(file.lastModified || Date.now())),
      durationSeconds: 0,
      language,
      audioFormat: file.type || "application/octet-stream",
      audio: file,
    });
    setSaved(true);
    onSaved();
    void queue.flush();
  };

  return (
    <div className="stack">
      <label className="notice">
        {t("ui.capture.import")}
        <input
          type="file"
          accept="audio/*"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void onFile(file);
          }}
        />
      </label>
      {saved && <p className="notice ok" role="status">{t("ui.capture.import_saved")}</p>}
    </div>
  );
}
