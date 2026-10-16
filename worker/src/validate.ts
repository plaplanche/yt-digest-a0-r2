// Runtime validation against the JSON Schemas embedded in the generated contracts.
import { Validator, type Schema } from "@cfworker/json-schema";

/** Returns a function giving the errors of a value against `schema`, empty when it is valid. */
export function validator(schema: object): (value: unknown) => string[] {
  const compiled = new Validator(schema as Schema, "2020-12", false);
  return (value) =>
    compiled.validate(value).errors.map((e) => `${e.instanceLocation}: ${e.error}`);
}
