import { describe, expect, it } from "vitest";
import { replayIndex, pageOffset } from "./replay";

describe("bounded replay cursor", () => {
  it("clamps previous/next and maps an index to a bounded page", () => {
    expect(replayIndex(0, -1, 42)).toBe(0);
    expect(replayIndex(41, 1, 42)).toBe(41);
    expect(replayIndex(19, 1, 42)).toBe(20);
    expect(pageOffset(20, 20)).toBe(20);
    expect(pageOffset(39, 20)).toBe(20);
  });
  it("has no cursor or page to request for empty results", () => {
    expect(replayIndex(0, 1, 0)).toBe(0);
    expect(pageOffset(0, 20)).toBe(0);
  });
});
