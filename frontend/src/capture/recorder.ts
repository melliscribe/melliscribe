// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Audio capture with MediaRecorder (D9).
 *
 * Browsers differ in what they record, so the format is chosen from what the
 * browser supports and then read back from the recorder — detected, never
 * assumed. The recording's id is generated here, on the device, at capture:
 * it is the upload idempotency key and the batch `custom_id` (FR-020, ADR-0004).
 */

/** Preferred first: Opus is the right codec for speech at low bitrate. */
export const PREFERRED_TYPES = [
  "audio/webm;codecs=opus",
  "audio/ogg;codecs=opus",
  "audio/mp4;codecs=mp4a.40.2",
  "audio/mp4",
  "audio/webm",
];

export function pickMimeType(isTypeSupported: (type: string) => boolean): string | undefined {
  return PREFERRED_TYPES.find((type) => isTypeSupported(type));
}

/** Format a capture time with the device's UTC offset, so the server knows its local day. */
export function formatCapturedAt(date: Date): string {
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, "0");
  const local = new Date(date.getTime() + offset * 60_000).toISOString().slice(0, 19);
  return `${local}${sign}${pad(offset / 60)}:${pad(offset % 60)}`;
}

export interface FinishedRecording {
  id: string;
  capturedAt: string;
  durationSeconds: number;
  audioFormat: string;
  audio: Blob;
}

export class Recorder {
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private startedAt = 0;
  private id = "";
  private capturedAt = "";

  async start(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = pickMimeType((type) => MediaRecorder.isTypeSupported(type));
    this.recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    this.chunks = [];
    this.id = crypto.randomUUID();
    const now = new Date();
    this.capturedAt = formatCapturedAt(now);
    this.startedAt = performance.now();
    this.recorder.ondataavailable = (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    };
    // Timeslices keep data flowing, so a crash mid-dictation loses seconds, not minutes.
    this.recorder.start(1000);
  }

  get elapsedSeconds(): number {
    return this.recorder ? (performance.now() - this.startedAt) / 1000 : 0;
  }

  stop(): Promise<FinishedRecording> {
    const recorder = this.recorder;
    if (recorder === null) return Promise.reject(new Error("not recording"));
    return new Promise((resolve) => {
      recorder.onstop = () => {
        recorder.stream.getTracks().forEach((track) => track.stop());
        const audioFormat = recorder.mimeType || this.chunks[0]?.type || "audio/webm";
        resolve({
          id: this.id,
          capturedAt: this.capturedAt,
          durationSeconds: Math.round(((performance.now() - this.startedAt) / 1000) * 10) / 10,
          audioFormat,
          audio: new Blob(this.chunks, { type: audioFormat }),
        });
        this.recorder = null;
      };
      recorder.stop();
    });
  }
}
