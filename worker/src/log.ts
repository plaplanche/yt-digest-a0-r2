// Structured logging: one JSON line per event (spec section 4.4).
import { logEventSchema, type LogEvent, type LogEventName } from "./contracts/log-event";
import { validator } from "./validate";

// The Workers runtime provides console; the worker's tsconfig loads no environment types.
declare global {
  var console: { log(message: string): void };
}

export type LogFields = Partial<Pick<LogEvent, "level" | "request_id" | "video_id" | "attrs">>;

const validateLogEvent = validator(logEventSchema);

/** Writes one log line, validated against the log event contract; throws when it does not match. */
export function log(event: LogEventName, fields: LogFields = {}): void {
  const { level = "info", attrs = {}, ...rest } = fields;
  const line = { ts: new Date().toISOString(), level, service: "worker", event, attrs, ...rest };
  const errors = validateLogEvent(line);
  if (errors.length > 0) {
    throw new Error(`invalid log event ${JSON.stringify(event)}: ${errors.join("; ")}`);
  }
  console.log(JSON.stringify(line));
}
