// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Play the passage a field was heard in (US3, FR-023): playback starts at the
 * segment the phrase came from, not at the beginning of the recording. Once the
 * audio is gone, say so honestly instead of offering a broken control (FR-027d).
 */
import { useRef } from "react";

import { api } from "../api/client";
import { useI18n } from "../i18n";

export function FieldPlayback({
  recordingId,
  audioAvailable,
  startSeconds,
  endSeconds,
}: {
  recordingId: string;
  audioAvailable: boolean;
  startSeconds: number;
  endSeconds: number;
}) {
  const { t } = useI18n();
  const audio = useRef<HTMLAudioElement | null>(null);
  if (!audioAvailable) {
    return <p className="verbatim" data-testid="audio-gone">{t("ui.review.audio_gone")}</p>;
  }
  const play = () => {
    const element = audio.current ?? new Audio(api.audioUrl(recordingId));
    audio.current = element;
    element.currentTime = startSeconds;
    const stopAtEnd = () => {
      if (element.currentTime >= endSeconds) {
        element.pause();
        element.removeEventListener("timeupdate", stopAtEnd);
      }
    };
    element.addEventListener("timeupdate", stopAtEnd);
    void element.play();
  };
  return (
    <button type="button" onClick={play}>
      {t("ui.review.play")}
    </button>
  );
}
