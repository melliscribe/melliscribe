// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";

import { formatCapturedAt, pickMimeType } from "../../src/capture/recorder";
import { assessStorage } from "../../src/offline/quota";

describe("recorder format", () => {
  it("prefers Opus when the browser supports it", () => {
    expect(pickMimeType(() => true)).toBe("audio/webm;codecs=opus");
  });

  it("falls back to what the browser supports, e.g. Safari's mp4", () => {
    expect(pickMimeType((t) => t.startsWith("audio/mp4"))).toBe("audio/mp4;codecs=mp4a.40.2");
  });

  it("lets the browser choose when nothing preferred is supported", () => {
    expect(pickMimeType(() => false)).toBeUndefined();
  });

  it("stamps the capture time with the device offset", () => {
    expect(formatCapturedAt(new Date())).toMatch(/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$/);
  });
});

describe("storage pressure (FR-021)", () => {
  it("warns at 80% of the quota", () => {
    expect(assessStorage({ usage: 80, quota: 100 })?.shouldWarn).toBe(true);
    expect(assessStorage({ usage: 50, quota: 100 })?.shouldWarn).toBe(false);
  });

  it("stays silent when the browser does not report", () => {
    expect(assessStorage({})).toBeNull();
  });
});
