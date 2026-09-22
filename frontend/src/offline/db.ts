// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * The device-durable capture store (ADR-0004).
 *
 * Audio and the pending-upload queue live in separate object stores. A
 * recording is written to both in a single transaction, and the UI confirms
 * only once that transaction has completed (FR-002).
 *
 * Audio is stored as an ArrayBuffer with its media type rather than as a Blob:
 * Blob storage in IndexedDB has been unreliable on some mobile browsers, and
 * this is the one path that must not lose data.
 */

export type Language = "fr" | "en";

/** A recording as captured, before upload. */
export interface CapturedRecording {
  id: string;
  capturedAt: string;
  durationSeconds: number;
  language: Language;
  audioFormat: string;
  audio: Blob;
}

/** The queue entry: explicit state, not implicit intent. */
export interface PendingUpload {
  id: string;
  capturedAt: string;
  durationSeconds: number;
  language: Language;
  audioFormat: string;
  sizeBytes: number;
  /** `pending_upload` retries; `rejected` needs the beekeeper (e.g. a 415). */
  state: "pending_upload" | "rejected";
  attempts: number;
  nextAttemptAt: number;
  lastError: string | null;
}

interface StoredAudio {
  data: ArrayBuffer;
  type: string;
}

const DB_NAME = "melliscribe";
const DB_VERSION = 1;
const AUDIO = "audio";
const QUEUE = "queue";
const SETTINGS = "settings";

function request<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function done(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error ?? new Error("transaction aborted"));
  });
}

/** A thin, application-owned wrapper over the capture database. */
export class CaptureDb {
  constructor(private readonly db: IDBDatabase) {}

  /** Persist a recording durably; resolves only once the write is committed. */
  async saveRecording(recording: CapturedRecording): Promise<void> {
    // Read the blob first: an IndexedDB transaction commits as soon as it has
    // no pending request, so nothing asynchronous may happen inside it.
    const stored: StoredAudio = {
      data: await recording.audio.arrayBuffer(),
      type: recording.audio.type,
    };
    const tx = this.db.transaction([AUDIO, QUEUE], "readwrite", {
      durability: "strict",
    });
    const entry: PendingUpload = {
      id: recording.id,
      capturedAt: recording.capturedAt,
      durationSeconds: recording.durationSeconds,
      language: recording.language,
      audioFormat: recording.audioFormat,
      sizeBytes: recording.audio.size,
      state: "pending_upload",
      attempts: 0,
      nextAttemptAt: 0,
      lastError: null,
    };
    tx.objectStore(AUDIO).put(stored, recording.id);
    tx.objectStore(QUEUE).put(entry, recording.id);
    await done(tx);
  }

  async getAudio(id: string): Promise<Blob | undefined> {
    const tx = this.db.transaction(AUDIO, "readonly");
    const stored = await request(
      tx.objectStore(AUDIO).get(id) as IDBRequest<StoredAudio | undefined>,
    );
    return stored === undefined ? undefined : new Blob([stored.data], { type: stored.type });
  }

  async listPending(): Promise<PendingUpload[]> {
    const tx = this.db.transaction(QUEUE, "readonly");
    const entries = await request(tx.objectStore(QUEUE).getAll() as IDBRequest<PendingUpload[]>);
    return entries.sort((a, b) => a.capturedAt.localeCompare(b.capturedAt));
  }

  async updatePending(entry: PendingUpload): Promise<void> {
    const tx = this.db.transaction(QUEUE, "readwrite");
    tx.objectStore(QUEUE).put(entry, entry.id);
    await done(tx);
  }

  /** Drop the local copy. Called only after a 201 or 200 (FR-003). */
  async removeAcknowledged(id: string): Promise<void> {
    const tx = this.db.transaction([AUDIO, QUEUE], "readwrite");
    tx.objectStore(AUDIO).delete(id);
    tx.objectStore(QUEUE).delete(id);
    await done(tx);
  }

  async getSetting<T>(key: string): Promise<T | undefined> {
    const tx = this.db.transaction(SETTINGS, "readonly");
    return request(tx.objectStore(SETTINGS).get(key) as IDBRequest<T | undefined>);
  }

  async putSetting<T>(key: string, value: T): Promise<void> {
    const tx = this.db.transaction(SETTINGS, "readwrite");
    tx.objectStore(SETTINGS).put(value, key);
    await done(tx);
  }
}

export async function openCaptureDb(): Promise<CaptureDb> {
  const req = indexedDB.open(DB_NAME, DB_VERSION);
  req.onupgradeneeded = () => {
    const db = req.result;
    for (const store of [AUDIO, QUEUE, SETTINGS]) {
      if (!db.objectStoreNames.contains(store)) db.createObjectStore(store);
    }
  };
  return new CaptureDb(await request(req));
}
