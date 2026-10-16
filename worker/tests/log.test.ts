import { afterEach, describe, expect, it, vi } from "vitest";
import type { LogEventName } from "../src/contracts/log-event";
import { log } from "../src/log";

describe("log", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("writes one JSON line for a catalogued event", () => {
    const write = vi.spyOn(console, "log").mockImplementation(() => undefined);
    log("service.started", { request_id: "req-1", attrs: { version: "0.1.0" } });
    expect(write).toHaveBeenCalledTimes(1);
    const line: unknown = JSON.parse(String(write.mock.calls[0]?.[0]));
    expect(line).toMatchObject({
      level: "info",
      service: "worker",
      event: "service.started",
      request_id: "req-1",
      attrs: { version: "0.1.0" },
    });
    expect((line as { ts: string }).ts).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
  });

  it("throws on an event outside the catalogue", () => {
    const write = vi.spyOn(console, "log").mockImplementation(() => undefined);
    expect(() => log("transcript.text" as LogEventName)).toThrow(/invalid log event/);
    expect(write).not.toHaveBeenCalled();
  });

  it("throws on an unknown field", () => {
    const fields = { attrs: {}, text: "hello" } as Parameters<typeof log>[1];
    expect(() => log("service.started", fields)).toThrow(/invalid log event/);
  });
});
