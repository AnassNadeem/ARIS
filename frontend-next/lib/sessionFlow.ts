export type SelectorStep = "circuit" | "driver" | "strategies" | "loading";
export type SelectorAction = "select" | "replay" | "aris" | "lock" | "strategies" | "continue" | "back";
export type ReplayMode = "data" | "aris";

export type SessionWeekend = "standard" | "sprint" | "both";

export interface SessionOption {
  id: string;
  type: string;
  label: string;
  arisCapable: boolean;
  weekend: SessionWeekend;
}

/** Replay/ARIS is Race-only. Other codes remain for labels on live/history surfaces. */
export const SESSION_OPTIONS: SessionOption[] = [
  { id: "R", type: "R", label: "Race", arisCapable: true, weekend: "both" },
];

/** Race is the product path. FP2 is a temporary live-wiring probe for ghost/tower. */
const ARIS_SESSIONS = new Set(["R", "FP2"]);

export function isArisCapableSession(sessionType: string | null | undefined): boolean {
  return ARIS_SESSIONS.has(String(sessionType ?? "").toUpperCase());
}

/** Console ARIS toggle: Race and FP2 can turn it on after entering, including replay. */
export function canToggleArisInConsole(sessionType: string | null | undefined): boolean {
  return isArisCapableSession(sessionType);
}

/** Race and FP2 ARIS both pick a driver and a strategy before the console. */
export function sessionNeedsStrategyPick(sessionType: string | null | undefined): boolean {
  return isArisCapableSession(sessionType);
}

export function sessionLabel(sessionType: string | null | undefined): string {
  const t = String(sessionType ?? "").toUpperCase();
  if (t === "FP1") return "FP1";
  if (t === "FP2") return "FP2";
  if (t === "FP3") return "FP3";
  if (t === "R" || t === "") return "Race";
  if (t === "SQ") return "Sprint Quali";
  if (t === "SS") return "SG2";
  if (t === "S") return "Sprint";
  if (t === "Q") return "Quali";
  return t || "Race";
}

export function circuitBadge(
  round: { isSprint: boolean },
  selectedSession?: string | null,
): string {
  const t = String(selectedSession ?? "R").toUpperCase();
  if (t === "R" || t === "") return "RACE";
  return round.isSprint ? "SPRINT WEEKEND" : "STANDARD WEEKEND";
}

export function sessionAvailability(
  option: SessionOption,
  _isSprint: boolean,
  status: Record<string, string>,
): { enabled: boolean; reason?: string } {
  if (option.type !== "R") {
    return { enabled: false, reason: "Only Race sessions are supported for Replay/ARIS." };
  }
  const st = status[option.type];
  if (st === "UPCOMING") {
    return { enabled: false, reason: "This session has not run yet." };
  }
  return { enabled: true };
}

export function nextSelectorStep(
  step: SelectorStep,
  action: SelectorAction,
  opts?: { arisEnabled?: boolean; arisCapable?: boolean },
): SelectorStep {
  const arisOn = opts?.arisEnabled ?? opts?.arisCapable ?? true;
  if (action === "back") {
    if (step === "loading") return arisOn ? "strategies" : "circuit";
    if (step === "strategies") return "driver";
    if (step === "driver") return "circuit";
    return "circuit";
  }
  if (step === "circuit" && (action === "select" || action === "aris")) {
    return arisOn ? "driver" : "loading";
  }
  if (step === "circuit" && action === "replay") return "loading";
  if (step === "driver" && (action === "lock" || action === "strategies")) return "strategies";
  if (step === "driver" && action === "continue") return "strategies";
  if (step === "strategies" && (action === "continue" || action === "replay" || action === "aris")) {
    return "loading";
  }
  return step;
}

export function canStartRace(opts: {
  arisEnabled: boolean;
  selectedDriver: string | null;
  strategies: unknown[] | null;
  selectedStrategy: unknown | null;
}): boolean {
  if (!opts.arisEnabled) return true;
  return Boolean(
    opts.selectedDriver && (opts.strategies?.length ?? 0) > 0 && opts.selectedStrategy,
  );
}

/** Console Start Race: pack must be ready, the feed must have stopped waiting, and at least one car must exist. */
export function replayStartReady(opts: {
  packStage: string;
  waitingForRace: boolean;
  carCount: number;
  playState: string;
}): boolean {
  const packOk = opts.packStage === "minimal" || opts.packStage === "full";
  return packOk && !opts.waitingForRace && opts.carCount > 0 && opts.playState === "ready";
}

export function commsTabs(opts: { arisOn: boolean; copilotOn: boolean; copilotDocked: boolean }): {
  id: "main" | "chat";
  label: string;
}[] {
  const chatLabel = opts.copilotOn ? "Copilot" : "Ask ARIS";
  if (opts.arisOn)
    return [
      { id: "main", label: "Main Comms" },
      { id: "chat", label: chatLabel },
    ];
  if (opts.copilotDocked) return [{ id: "chat", label: chatLabel }];
  return [
    { id: "main", label: "Main Comms" },
    { id: "chat", label: chatLabel },
  ];
}
