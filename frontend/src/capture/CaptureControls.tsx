// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Gloved-hands capture controls (FR-004): one very large target that toggles,
 * so starting and stopping need no precision, no hover and no long press.
 */
import { useI18n } from "../i18n";

export function CaptureControls({
  recording,
  elapsedSeconds,
  disabled,
  onStart,
  onStop,
}: {
  recording: boolean;
  elapsedSeconds: number;
  disabled: boolean;
  onStart: () => void;
  onStop: () => void;
}) {
  const { t } = useI18n();
  return (
    <button
      type="button"
      className={`record-button ${recording ? "recording" : "primary"}`}
      disabled={disabled}
      onClick={recording ? onStop : onStart}
      aria-pressed={recording}
    >
      {recording
        ? `${t("ui.capture.stop")} — ${t("ui.capture.recording", { seconds: Math.floor(elapsedSeconds) })}`
        : t("ui.capture.start")}
    </button>
  );
}
