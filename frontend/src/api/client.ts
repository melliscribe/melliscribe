// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * A small typed client. Every type comes from `generated/schema.ts`, which is
 * generated from the backend's OpenAPI schema — never hand-written (Principle IV).
 */
import type { UploadRequest } from "../offline/queue";
import type { components } from "./generated/schema";

type Schemas = components["schemas"];
export type RecordView = Schemas["RecordView"];
export type RecordPatch = Schemas["RecordPatch"];
export type Hive = Schemas["Hive"];
export type Recording = Schemas["Recording"];
export type AccountSettings = Schemas["AccountSettings"];
export type AccountSettingsUpdate = Schemas["AccountSettingsUpdate"];
export type ErrorResponse = Schemas["ErrorResponse"];
export type FieldStatus = Schemas["FieldStatus"];
export type Language = Schemas["Language"];
export type RecordingState = Schemas["RecordingState"];
export type ExpiringRecording = Schemas["ExpiringRecording"];

export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

/** An API error, carrying the server's message in the account language. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ErrorResponse | null,
  ) {
    super(body?.message ?? `HTTP ${status}`);
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init.body instanceof FormData ? init.headers : {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ErrorResponse | null;
    throw new ApiError(response.status, body);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

export const api = {
  getSettings: () => call<AccountSettings>("/settings"),
  updateSettings: (update: AccountSettingsUpdate) =>
    call<AccountSettings>("/settings", { method: "PATCH", ...json(update) }),
  listHives: () => call<Hive[]>("/hives"),
  createHive: (identifier: string) =>
    call<Hive>("/hives", { method: "POST", ...json({ identifier }) }),
  listRecords: () => call<RecordView[]>("/records"),
  getRecord: (id: string) => call<RecordView>(`/records/${id}`),
  patchRecord: (id: string, patch: RecordPatch) =>
    call<RecordView>(`/records/${id}`, { method: "PATCH", ...json(patch) }),
  confirmRecord: (id: string) => call<RecordView>(`/records/${id}/confirm`, { method: "POST" }),
  resolveHive: (id: string, choice: { hive_id: string } | { identifier: string }) =>
    call<RecordView>(`/records/${id}/resolve-hive`, { method: "POST", ...json(choice) }),
  listRecordings: (state?: RecordingState) =>
    call<Recording[]>(`/recordings${state ? `?state=${state}` : ""}`),
  getRecording: (id: string) => call<Recording>(`/recordings/${id}`),
  retryRecording: (id: string) => call<Recording>(`/recordings/${id}/retry`, { method: "POST" }),
  reprocessRecording: (id: string, language?: Language) =>
    call<Recording>(`/recordings/${id}/reprocess`, {
      method: "POST",
      ...json(language ? { language } : {}),
    }),
  deleteRecordingAudio: (id: string) => call<void>(`/recordings/${id}`, { method: "DELETE" }),
  listExpiring: (withinDays: number) =>
    call<ExpiringRecording[]>(`/recordings/expiring?within_days=${withinDays}`),
  setEvalConsent: (id: string, consented: boolean) =>
    call<Recording>(`/recordings/${id}/eval-consent`, { method: "POST", ...json({ consented }) }),
  audioUrl: (id: string) => `${API_BASE}/recordings/${id}/audio`,
};

/** The queue's uploader: multipart POST, status only; network errors reject. */
export async function uploadRecording(request: UploadRequest): Promise<{ status: number }> {
  const form = new FormData();
  form.set("id", request.id);
  form.set("captured_at", request.capturedAt);
  form.set("duration_seconds", String(request.durationSeconds));
  form.set("language", request.language);
  form.set("audio_format", request.audioFormat);
  form.set("audio", request.audio, `${request.id}`);
  const response = await fetch(`${API_BASE}/recordings`, { method: "POST", body: form });
  return { status: response.status };
}
