import { describe, expect, it } from "vitest";
import { VERSION } from "../src/index";

describe("worker package", () => {
  it("has a version", () => {
    expect(VERSION).toBe("0.1.0");
  });
});
