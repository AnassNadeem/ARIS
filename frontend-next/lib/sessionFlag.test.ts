import { describe, expect, it } from "vitest";
import { sessionFlagToPhase } from "./mapCars";

describe("sessionFlagToPhase standing start", () => {
  it("maps STANDING_START", () => {
    expect(sessionFlagToPhase("STANDING_START")).toBe("STANDING_START");
    expect(sessionFlagToPhase("STANDING START")).toBe("STANDING_START");
  });
});
