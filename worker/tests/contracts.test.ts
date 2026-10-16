import { describe, expect, it } from "vitest";
import { logEventSchema, type LogEvent } from "../src/contracts/log-event";
import { transcriptResultSchema, type TranscriptResult } from "../src/contracts/transcript-result";
import { validator } from "../src/validate";

const validateResult = validator(transcriptResultSchema);
const validateLogEvent = validator(logEventSchema);

const result: TranscriptResult = {
  video_id: "dQw4w9WgXcQ",
  status: "ok",
  lang: "fr",
  source: "manual",
  word_count: 3,
  truncated: false,
  sponsor_ratio: 0.125,
  pages: ["un deux trois"],
};

const logLine: LogEvent = {
  ts: "2026-10-16T08:30:00.123Z",
  level: "info",
  service: "node",
  event: "sponsorblock.call",
  request_id: "req-1",
  video_id: "dQw4w9WgXcQ",
  attrs: { status: 200, segments: 2, duration_ms: 41 },
};

describe("transcript result contract", () => {
  it("accepts a valid result", () => {
    expect(validateResult(result)).toEqual([]);
  });

  it("rejects an extra field", () => {
    expect(validateResult({ ...result, text: "hello" })).not.toEqual([]);
  });

  it("rejects a bad video_id", () => {
    expect(validateResult({ ...result, video_id: "short" })).not.toEqual([]);
    expect(validateResult({ ...result, video_id: "dQw4w9WgXc!" })).not.toEqual([]);
  });

  it("rejects a bad status", () => {
    expect(validateResult({ ...result, status: "failed" })).not.toEqual([]);
  });
});

describe("log event contract", () => {
  it("accepts a valid log line", () => {
    expect(validateLogEvent(logLine)).toEqual([]);
  });

  it("rejects an unknown event", () => {
    expect(validateLogEvent({ ...logLine, event: "transcript.text" })).not.toEqual([]);
  });
});
