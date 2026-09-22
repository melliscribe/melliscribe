// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
// @vitest-environment node
/**
 * FR-002, FR-003 on the device: a recording is durable before the UI confirms,
 * and it is never dropped before the server acknowledges it with 201 or 200.
 */
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { openCaptureDb, type CaptureDb } from "../../src/offline/db";
import { UploadQueue, type Uploader } from "../../src/offline/queue";

function recording(id = crypto.randomUUID()) {
  return {
    id,
    capturedAt: "2026-05-12T09:30:00+02:00",
    durationSeconds: 42,
    language: "fr" as const,
    audioFormat: "audio/webm;codecs=opus",
    audio: new Blob(["Ruche trois."], { type: "audio/webm" }),
  };
}

let db: CaptureDb;

beforeEach(async () => {
  globalThis.indexedDB = new IDBFactory();
  db = await openCaptureDb();
});

describe("capture storage", () => {
  it("keeps the audio and the queue entry in separate stores", async () => {
    const rec = recording();
    await db.saveRecording(rec);
    expect(await db.getAudio(rec.id)).toBeInstanceOf(Blob);
    const [pending] = await db.listPending();
    expect(pending?.id).toBe(rec.id);
    expect(pending?.state).toBe("pending_upload");
  });
});

describe("upload queue", () => {
  it.each([201, 200])("drops the local copy only on %i", async (status) => {
    const rec = recording();
    await db.saveRecording(rec);
    const upload: Uploader = vi.fn(async () => ({ status }));
    await new UploadQueue(db, upload).flush();
    expect(await db.listPending()).toEqual([]);
    expect(await db.getAudio(rec.id)).toBeUndefined();
  });

  it("keeps the recording when the network fails", async () => {
    const rec = recording();
    await db.saveRecording(rec);
    const upload: Uploader = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    await new UploadQueue(db, upload).flush();
    const [pending] = await db.listPending();
    expect(pending?.attempts).toBe(1);
    expect(pending?.nextAttemptAt).toBeGreaterThan(Date.now());
    expect(await db.getAudio(rec.id)).toBeInstanceOf(Blob);
  });

  it("keeps the recording on a server error", async () => {
    const rec = recording();
    await db.saveRecording(rec);
    await new UploadQueue(db, async () => ({ status: 503 })).flush();
    expect(await db.getAudio(rec.id)).toBeInstanceOf(Blob);
  });

  it("keeps an unsupported file and marks it rejected, never retrying blindly", async () => {
    const rec = recording();
    await db.saveRecording(rec);
    const upload = vi.fn(async () => ({ status: 415 }));
    const queue = new UploadQueue(db, upload);
    await queue.flush();
    await queue.flush();
    expect(upload).toHaveBeenCalledTimes(1);
    const [pending] = await db.listPending();
    expect(pending?.state).toBe("rejected");
    expect(await db.getAudio(rec.id)).toBeInstanceOf(Blob);
  });

  it("backs off before retrying", async () => {
    const rec = recording();
    await db.saveRecording(rec);
    const upload = vi.fn(async () => ({ status: 503 }));
    const queue = new UploadQueue(db, upload);
    await queue.flush();
    await queue.flush();
    expect(upload).toHaveBeenCalledTimes(1);
  });

  it("sends the client-generated id as the idempotency key", async () => {
    const rec = recording();
    await db.saveRecording(rec);
    const upload = vi.fn<Uploader>(async () => ({ status: 201 }));
    await new UploadQueue(db, upload).flush();
    expect(upload.mock.calls[0]?.[0]).toMatchObject({ id: rec.id });
  });
});
