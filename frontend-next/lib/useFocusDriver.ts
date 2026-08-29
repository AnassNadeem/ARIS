import { useRaceStore } from "@/store/raceStore";

export function useFocusDriver(fallback = "VER"): string {
  return useRaceStore((s) => s.focusDriver ?? s.arisDriver ?? fallback);
}
