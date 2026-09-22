// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * The upload queue (ADR-0004, FR-003).
 *
 * The foreground retry with backoff is the guarantee: it runs on start-up, on
 * the `online` event, when the app becomes visible and on a timer. A local
 * copy is dropped only on a 201 or 200. Anything else keeps it.
 */
import type { CaptureDb, PendingUpload } from "./db";

export interface UploadRequest {
  id: string;
  capturedAt: string;
  durationSeconds: number;
  language: string;
  audioFormat: string;
  audio: Blob;
}

/** Sends one recording; resolves with the HTTP status, rejects on network failure. */
export type Uploader = (request: UploadRequest) => Promise<{ status: number }>;

const BASE_DELAY_MS = 5_000;
const MAX_DELAY_MS = 10 * 60_000;

export function computeBackoff(attempts: number): number {
  return Math.min(BASE_DELAY_MS * 2 ** Math.max(0, attempts - 1), MAX_DELAY_MS);
}

export class UploadQueue {
  private flushing: Promise<void> | null = null;

  constructor(
    private readonly db: CaptureDb,
    private readonly upload: Uploader,
    private readonly now: () => number = Date.now,
  ) {}

  /** Try every due recording once. Concurrent calls share one pass. */
  flush(): Promise<void> {
    this.flushing ??= this.flushOnce().finally(() => {
      this.flushing = null;
    });
    return this.flushing;
  }

  private async flushOnce(): Promise<void> {
    for (const entry of await this.db.listPending()) {
      if (entry.state !== "pending_upload" || entry.nextAttemptAt > this.now()) continue;
      await this.send(entry);
    }
  }

  private async send(entry: PendingUpload): Promise<void> {
    const audio = await this.db.getAudio(entry.id);
    if (audio === undefined) return;
    let status: number;
    try {
      ({ status } = await this.upload({ ...entry, audio }));
    } catch (error) {
      await this.retryLater(entry, error instanceof Error ? error.message : String(error));
      return;
    }
    if (status === 201 || status === 200) {
      await this.db.removeAcknowledged(entry.id);
    } else if (status === 415 || status === 413) {
      await this.db.updatePending({ ...entry, state: "rejected", lastError: `HTTP ${status}` });
    } else {
      await this.retryLater(entry, `HTTP ${status}`);
    }
  }

  private async retryLater(entry: PendingUpload, reason: string): Promise<void> {
    const attempts = entry.attempts + 1;
    await this.db.updatePending({
      ...entry,
      attempts,
      lastError: reason,
      nextAttemptAt: this.now() + computeBackoff(attempts),
    });
  }

  /** Retry on every occasion the browser offers. Returns a stop function. */
  start(intervalMs = 30_000): () => void {
    const trigger = () => void this.flush();
    const onVisible = () => {
      if (document.visibilityState === "visible") trigger();
    };
    window.addEventListener("online", trigger);
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(trigger, intervalMs);
    trigger();
    return () => {
      window.removeEventListener("online", trigger);
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
    };
  }
}
