import { describe, expect, it } from "vitest";
import { useRaceStore } from "@/store/raceStore";

describe("connectionStatus", () => {
  it("starts disconnected and can move connecting → connected", () => {
    useRaceStore.getState().reset();
    expect(useRaceStore.getState().connectionStatus).toBe("disconnected");
    useRaceStore.getState().setConnectionStatus("connecting");
    expect(useRaceStore.getState().connectionStatus).toBe("connecting");
    useRaceStore.getState().setConnectionStatus("connected", 0);
    expect(useRaceStore.getState().connectionStatus).toBe("connected");
    expect(useRaceStore.getState().connectionLagMs).toBe(0);
  });
});
