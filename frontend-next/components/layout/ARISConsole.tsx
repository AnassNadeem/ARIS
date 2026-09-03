"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Actions,
  DockLocation,
  Layout,
  Model,
  type IJsonModel,
  type ILayoutApi,
  type Node as FlexNode,
  type TabNode,
} from "flexlayout-react";
import "flexlayout-react/style/dark.css";
import { useRaceStore } from "@/store/raceStore";
import { AppHeader } from "@/components/layout/AppHeader";
import { PanelWrapper, renderTabWithTearOff } from "@/components/layout/PanelWrapper";
import { AnalyticsCatalogue } from "@/components/layout/AnalyticsCatalogue";
import { MobileConsole } from "@/components/layout/MobileConsole";
import { catalogueEntry, renderPanel } from "@/lib/panelRegistry";
import { getCircuitCoords } from "@/lib/api";
import { defaultAnalyticsIds, loadAnalyticsSlots, moveAnalyticsSlot, saveAnalyticsSlots, clearAnalyticsSlots } from "@/lib/analyticsSlots";
import { useIsNarrow } from "@/lib/useIsNarrow";
import { MockRaceFeed } from "@/lib/mockRaceFeed";
import { LiveSseFeed, ReplayFrameFeed } from "@/lib/liveFeed";
import { R2_LOAD_ERROR, ghostUnavailableMessage } from "@/lib/r2Replay";
import { broadcastRaceState } from "@/lib/broadcastChannel";
import { SpeedWidget } from "@/components/ui/SpeedWidget";
import { RaceFinishedDebrief } from "@/components/aris/RaceFinishedDebrief";
import { StrategyChangeBanner } from "@/components/aris/StrategyChangeBanner";
import { useArisRecommendLoop } from "@/lib/useArisRecommendLoop";
import { formatLapCompact, formatLapHeader } from "@/lib/formatLap";
import { sessionLabel } from "@/lib/sessionFlow";
import { useCountdown } from "@/lib/useCountdown";
import {
  ANALYTICS_ROW_ID,
  componentsFromLayoutJson,
  loadPersistedLayout,
  savePersistedLayout,
  clearPersistedLayout,
} from "@/lib/layoutPersist";

const COMMS_TABSET_ID = "comms-tabset";
const MAIN_ROW_ID = "main-dock-row";

/** Main dock fills one screen; analytics sit on a scrollable canvas below. */
const MAIN_ROW_VH = 100;
const ANALYTICS_BASE_VH = 56;

function analyticsIdsFromModel(model: Model): string[] {
  return componentsFromLayoutJson(model.toJson()).filter(
    (id) => id !== "analytics-add" && catalogueEntry(id)?.category === "analytics",
  );
}

function tab(componentId: string, name?: string, extra: Record<string, unknown> = {}) {
  const entry = catalogueEntry(componentId);
  return {
    type: "tab",
    id: `${componentId}-${Math.random().toString(36).slice(2, 8)}`,
    name: name ?? entry?.label ?? componentId,
    component: componentId,
    ...extra,
  };
}

function buildDefaultModel(isARISOn: boolean): IJsonModel {
  const mainRow = {
    type: "row",
    id: MAIN_ROW_ID,
    weight: MAIN_ROW_VH,
    children: [
      {
        type: "tabset",
        weight: 62,
        children: [tab("trackmap", "Track Map", { enableClose: false })],
      },
      {
        type: "row",
        weight: 28,
        children: [
          { type: "tabset", weight: 50, children: [tab("timingtower", "Timing Tower", { enableClose: false })] },
          { type: "tabset", weight: 50, children: [tab("laptimes", "Lap Times")] },
        ],
      },
      ...(isARISOn
        ? [
            {
              type: "tabset",
              id: COMMS_TABSET_ID,
              weight: 22,
              children: [tab("comms", "ARIS Comms")],
            },
          ]
        : []),
    ],
  };

  const analyticsRow = {
    type: "row",
    id: ANALYTICS_ROW_ID,
    weight: ANALYTICS_BASE_VH,
    children: isARISOn
      ? [
          { type: "tabset", weight: 32, children: [tab("ghostdelta", "Ghost Δ")] },
          {
            type: "row",
            weight: 36,
            children: [
              { type: "tabset", weight: 50, children: [tab("tyredeg")] },
              { type: "tabset", weight: 50, children: [tab("sectortimes")] },
            ],
          },
          { type: "tabset", weight: 32, children: [tab("gapchart")] },
        ]
      : [
          { type: "tabset", weight: 34, children: [tab("tyredeg")] },
          { type: "tabset", weight: 33, children: [tab("sectortimes")] },
          { type: "tabset", weight: 33, children: [tab("gapchart")] },
        ],
  };

  return {
    global: {
      rootOrientationVertical: true,
      tabEnableClose: true,
      tabSetEnableMaximize: true,
      tabSetMinWidth: 160,
      tabSetMinHeight: 120,
    },
    borders: [],
    layout: {
      type: "row",
      children: [mainRow, analyticsRow],
    },
  };
}

function LiveSessionWaitBanner({
  targetIso,
  sessionType,
  note,
}: {
  targetIso: string | null;
  sessionType: string;
  note: string;
}) {
  const valid =
    Boolean(targetIso) && !Number.isNaN(new Date(targetIso!).getTime());
  if (!valid || !targetIso) {
    return (
      <div className="shrink-0 bg-amber/10 px-4 py-2 font-sans text-xs text-amber">
        <p>{note}</p>
      </div>
    );
  }
  return <LiveWaitWithCountdown iso={targetIso} sessionType={sessionType} note={note} />;
}

function LiveWaitWithCountdown({
  iso,
  sessionType,
  note,
}: {
  iso: string;
  sessionType: string;
  note: string;
}) {
  const countdown = useCountdown(iso);
  const remaining = new Date(iso).getTime() > Date.now();
  return (
    <div className="shrink-0 bg-amber/10 px-4 py-2 font-sans text-xs text-amber">
      {remaining ? (
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-mono-data text-[14px] tracking-wide text-red">{countdown}</span>
          <span className="font-mono-data text-[11px] uppercase tracking-widest text-amber">
            until {sessionLabel(sessionType)}
          </span>
        </div>
      ) : null}
      <p className={remaining ? "mt-1" : undefined}>{note}</p>
    </div>
  );
}

export function ARISConsole({ mode, allowMock = false }: { mode: "replay" | "live"; allowMock?: boolean }) {
  const session = useRaceStore((s) => s.session);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const arisDriver = useRaceStore((s) => s.arisDriver);
  const ghostReason = useRaceStore((s) => s.ghostReason);
  const currentLap = useRaceStore((s) => s.currentLap);
  const totalLaps = useRaceStore((s) => s.totalLaps);
  const carCount = useRaceStore((s) => Object.keys(s.cars).length);
  const racePhase = useRaceStore((s) => s.racePhase);
  const setConsoleMode = useRaceStore((s) => s.setConsoleMode);
  const setConnectionStatus = useRaceStore((s) => s.setConnectionStatus);
  const setARISOn = useRaceStore((s) => s.setARISOn);
  const explainTabRequest = useRaceStore((s) => s.explainTabRequest);
  const copilotDocked = useRaceStore((s) => s.copilotDocked);
  const setCopilotDocked = useRaceStore((s) => s.setCopilotDocked);
  const waitingMessage = useRaceStore((s) => s.waitingMessage);
  const waitingForRace = useRaceStore((s) => s.waitingForRace);
  const consolePlayState = useRaceStore((s) => s.consolePlayState);
  const beginLightsOut = useRaceStore((s) => s.beginLightsOut);
  const startRacing = useRaceStore((s) => s.startRacing);
  const setWaiting = useRaceStore((s) => s.setWaiting);
  const packStage = useRaceStore((s) => s.packStage);
  const packToast = useRaceStore((s) => s.packToast);
  const setPackToast = useRaceStore((s) => s.setPackToast);

  useArisRecommendLoop();

  const layoutRef = useRef<ILayoutApi | null>(null);
  const [model, setModel] = useState<Model>(() =>
    Model.fromJson(buildDefaultModel(useRaceStore.getState().isARISOn)),
  );
  const arisOnAtMount = useRef(isARISOn);
  const canPersistLayout = useRef(false);
  const [layoutReady, setLayoutReady] = useState(false);
  const isNarrow = useIsNarrow();
  const [analyticsSlots, setAnalyticsSlots] = useState<string[]>(() =>
    defaultAnalyticsIds({ arisOn: useRaceStore.getState().isARISOn }),
  );
  const [layoutEpoch, setLayoutEpoch] = useState(0);

  useEffect(() => {
    const saved = loadPersistedLayout();
    const extra = loadAnalyticsSlots();
    if (saved) {
      try {
        const loaded = Model.fromJson(saved);
        setModel(loaded);
        const fromLayout = analyticsIdsFromModel(loaded);
        if (fromLayout.length) setAnalyticsSlots(fromLayout);
        else if (extra?.length) setAnalyticsSlots(extra);
      } catch {
        if (extra?.length) setAnalyticsSlots(extra);
      }
    } else if (extra?.length) {
      setAnalyticsSlots(extra);
    }
    setLayoutReady(true);
  }, []);

  const arisCapable = !session || session.sessionType === "R";
  const canEnableStrategy = arisOnAtMount.current && arisCapable;
  const packReady = mode === "replay" ? packStage === "minimal" || packStage === "full" : Boolean(session);
  const lightsOut = consolePlayState === "starting";
  const replayNotRacing = consolePlayState !== "racing";
  const startEnabled = packReady && consolePlayState === "ready";

  useEffect(() => {
    setConsoleMode(mode);
  }, [mode, setConsoleMode]);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    getCircuitCoords(session.year, session.round).then((c) => {
      if (cancelled || !c.x.length) return;
      useRaceStore.getState().setCircuitOutline(c);
    });
    return () => {
      cancelled = true;
    };
  }, [session?.year, session?.round]);

  useEffect(() => {
    if (mode === "live" && isARISOn) setARISOn(false);
  }, [mode, isARISOn, setARISOn]);

  useEffect(() => {
    if (!arisCapable && isARISOn) setARISOn(false);
  }, [arisCapable, isARISOn, setARISOn]);

  useEffect(() => {
    if (mode !== "live") return;
    setWaiting(true, "Waiting for live data to come.");
  }, [mode, setWaiting]);

  useEffect(() => {
    if (mode !== "live") return;
    if (carCount <= 0) return;
    startRacing();
    setWaiting(false);
  }, [mode, carCount, startRacing, setWaiting]);

  const waitingForLiveData = mode === "live" && carCount === 0;

  // Dynamically add/remove the Comms tab if ARIS is on at mount or Copilot is added.
  useEffect(() => {
    if (!layoutReady) return;
    const wantComms = isARISOn || copilotDocked;
    if (wantComms) {
      if (!model.getNodeById(COMMS_TABSET_ID)) {
        const mainRow = model.getNodeById(MAIN_ROW_ID);
        if (mainRow) {
          model.doAction(
            Actions.addNode(tab("comms", "ARIS Comms"), mainRow.getId(), DockLocation.RIGHT, -1),
          );
        }
      }
    }
  }, [isARISOn, copilotDocked, model, layoutReady]);

  // Live: EventSource → /api/live/stream (SSE) plus GPS positions.
  // Replay: FastF1 replay-frame on the playback clock.
  // Mock oval is only for explicit demo (?demo=1) or replay when no pack exists.
  useEffect(() => {
    const store = useRaceStore;
    setConnectionStatus("connecting");

    if (mode === "live") {
      const feed = new LiveSseFeed();
      let mock: MockRaceFeed | null = null;
      feed.onOpen = () => {
        mock?.stop();
        mock = null;
      };
      feed.onFailure = () => {
        if (allowMock && !mock) {
          mock = new MockRaceFeed(store);
          mock.start();
        }
      };
      feed.connect();
      if (allowMock) {
        const fallback = setTimeout(() => {
          if (store.getState().connectionStatus !== "connected") {
            mock = new MockRaceFeed(store);
            mock.start();
            setConnectionStatus("connected", 0);
          }
        }, 4000);
        return () => {
          clearTimeout(fallback);
          feed.disconnect();
          mock?.stop();
          setConnectionStatus("disconnected");
        };
      }
      return () => {
        feed.disconnect();
        mock?.stop();
        setConnectionStatus("disconnected");
      };
    }

    const replay = new ReplayFrameFeed();
    let mock: MockRaceFeed | null = null;
    replay.onOpen = () => {
      mock?.stop();
      mock = null;
    };
    replay.onFailure = () => {
      if (allowMock && !mock) {
        mock = new MockRaceFeed(store);
        mock.start();
        setConnectionStatus("connected", 340);
      } else {
        const cur = store.getState().waitingMessage;
        store.getState().setWaiting(true, cur || R2_LOAD_ERROR);
      }
    };
    if (session) void replay.connect(session.year, session.round, session.sessionType);
    else replay.onFailure();
    return () => {
      replay.disconnect();
      mock?.stop();
      setConnectionStatus("disconnected");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, session?.year, session?.round, session?.sessionType, allowMock]);

  useEffect(() => {
    return useRaceStore.subscribe((s) => {
      broadcastRaceState({
        type: "tick",
        payload: { cars: s.cars, ghostCar: s.ghostCar, currentLap: s.currentLap, totalLaps: s.totalLaps },
      });
    });
  }, []);

  const handleModelChange = useCallback((changedModel: Model) => {
    const ids = analyticsIdsFromModel(changedModel);
    setAnalyticsSlots(ids.length ? ids : defaultAnalyticsIds({ arisOn: isARISOn }));
    saveAnalyticsSlots(ids.length ? ids : defaultAnalyticsIds({ arisOn: isARISOn }));
    if (canPersistLayout.current) {
      savePersistedLayout(changedModel);
    }
  }, [isARISOn]);

  useEffect(() => {
    if (!layoutReady) return;
    canPersistLayout.current = true;
  }, [layoutReady]);

  const factory = useMemo(() => {
    return function renderTabContent(node: TabNode) {
      const componentId = node.getComponent() ?? "";
      return <PanelWrapper>{renderPanel(componentId)}</PanelWrapper>;
    };
  }, []);

  const addAnalytics = useCallback((componentId: string) => {
    setAnalyticsSlots((prev) => {
      if (prev.includes(componentId)) return prev;
      const next = [...prev, componentId];
      saveAnalyticsSlots(next);
      return next;
    });
  }, []);

  const removeAnalytics = useCallback((componentId: string) => {
    setAnalyticsSlots((prev) => {
      const next = prev.filter((id) => id !== componentId);
      saveAnalyticsSlots(next);
      return next;
    });
  }, []);

  const moveAnalytics = useCallback((componentId: string, direction: -1 | 1) => {
    setAnalyticsSlots((prev) => {
      const next = moveAnalyticsSlot(prev, componentId, direction);
      if (next === prev) return prev;
      saveAnalyticsSlots(next);
      return next;
    });
  }, []);

  function handleAddPanel(componentId: string) {
    if (componentId === "explain") return;
    const entry = catalogueEntry(componentId);
    if (isNarrow) {
      addAnalytics(componentId);
      return;
    }
    if (entry?.category === "analytics") {
      const row = model.getNodeById(ANALYTICS_ROW_ID);
      const active = model.getActiveTabset();
      if (row && active) {
        let n: FlexNode | null = active;
        let underAnalytics = false;
        while (n) {
          if (n.getId() === ANALYTICS_ROW_ID) {
            underAnalytics = true;
            break;
          }
          n = n.getParent() ?? null;
        }
        if (underAnalytics) {
          layoutRef.current?.addTabToActiveTabSet(tab(componentId));
          addAnalytics(componentId);
          return;
        }
      }
      if (row) {
        const sets = row.getChildren();
        const last = sets[sets.length - 1];
        if (last) {
          model.doAction(Actions.addNode(tab(componentId), last.getId(), DockLocation.CENTER, -1));
          addAnalytics(componentId);
          return;
        }
      }
    }
    layoutRef.current?.addTabToActiveTabSet(tab(componentId));
  }

  const resetView = useCallback(() => {
    const defaults = defaultAnalyticsIds({ arisOn: isARISOn });
    const next = Model.fromJson(buildDefaultModel(isARISOn));
    canPersistLayout.current = false;
    clearPersistedLayout();
    clearAnalyticsSlots();
    setModel(next);
    setAnalyticsSlots(defaults);
    setLayoutEpoch((n) => n + 1);
    savePersistedLayout(next);
    saveAnalyticsSlots(defaults);
    canPersistLayout.current = true;
  }, [isARISOn]);

  useEffect(() => {
    if (!explainTabRequest) return;
    useRaceStore.getState().setExplainTabRequest(null);
  }, [explainTabRequest]);

  useEffect(() => {
    if (!packToast) return;
    const t = window.setTimeout(() => setPackToast(null), 4000);
    return () => window.clearTimeout(t);
  }, [packToast, setPackToast]);

  return (
    <div className="flex h-screen w-screen flex-col bg-carbon">
      <AppHeader
        compact
        backHref={mode === "replay" ? "/replay" : "/live"}
        right={
          <>
            <span className="hidden font-sans text-xs font-medium text-white md:inline">
              {session?.circuitName ?? "ARIS"}
              {session?.year != null ? (
                <>
                  {" · "}
                  <span className="font-mono-data">{session.year}</span>
                </>
              ) : null}
            </span>
            {isARISOn && arisDriver && (
              <span className="hidden rounded bg-red/15 px-2 py-0.5 font-mono-data text-[10px] uppercase text-red md:inline">
                ARIS for {arisDriver}
              </span>
            )}
            <span className="hidden font-mono-data text-xs text-muted md:inline">
              {formatLapHeader(currentLap, totalLaps)}
            </span>
            {mode === "replay" && replayNotRacing && (
              <button
                type="button"
                disabled={!startEnabled || lightsOut}
                onClick={() => beginLightsOut()}
                title={!packReady ? "Waiting for laps and circuit map…" : "Lights-out on the track, then replay from lap 1"}
                className={`hidden shrink-0 rounded px-3 py-1 font-mono-data text-[11px] uppercase tracking-wide md:inline-flex ${
                  !startEnabled || lightsOut
                    ? "cursor-not-allowed border border-border text-muted-2 opacity-50"
                    : "bg-red text-white hover:brightness-110"
                }`}
              >
                {lightsOut ? "Lights out…" : "Start Race"}
              </button>
            )}
            <button
              onClick={() => canEnableStrategy && setARISOn(!isARISOn)}
              disabled={!canEnableStrategy && !isARISOn}
              title={
                !arisCapable
                  ? "ARIS runs on Race sessions only."
                  : !canEnableStrategy
                    ? "Strategy ARIS can only be enabled from the race selector. Add Copilot to ask about this race."
                    : undefined
              }
              className={`hidden shrink-0 rounded px-2 py-0.5 font-mono-data text-[10px] uppercase md:inline-flex ${
                !arisCapable || (!canEnableStrategy && !isARISOn)
                  ? "cursor-not-allowed border border-border text-muted-2 opacity-50"
                  : isARISOn
                    ? "bg-red/15 text-red"
                    : "border border-border text-muted hover:text-white"
              }`}
            >
              {isARISOn ? "● ARIS ON" : "○ ARIS OFF"}
            </button>
            {!isARISOn && (
              <button
                type="button"
                onClick={() => setCopilotDocked(true)}
                className="hidden rounded border border-border px-2 py-0.5 font-mono-data text-[10px] uppercase text-muted hover:text-white md:inline-flex"
              >
                {copilotDocked ? "● Copilot" : "Add Copilot"}
              </button>
            )}
            <button
              type="button"
              onClick={resetView}
              title="Restore the default panel layout"
              className="shrink-0 rounded border border-border bg-surface px-3 py-1.5 font-mono-data text-[11px] uppercase text-white hover:border-white"
            >
              Reset view
            </button>
            <div className="hidden shrink-0 md:block">
              <AnalyticsCatalogue onAdd={handleAddPanel} />
            </div>
          </>
        }
      />
      <div className="grid shrink-0 grid-cols-3 items-center border-b border-border bg-surface-2 px-3 py-1.5 md:hidden">
        <span className="justify-self-start font-mono-data text-xs text-white">
          {formatLapCompact(currentLap, totalLaps)}
        </span>
        <div className="justify-self-center">
          {mode === "replay" && replayNotRacing ? (
            <button
              type="button"
              disabled={!startEnabled || lightsOut}
              onClick={() => beginLightsOut()}
              title={!packReady ? "Waiting for laps and circuit map…" : "Lights-out on the track, then replay from lap 1"}
              className={`rounded px-3 py-1 font-mono-data text-[11px] uppercase tracking-wide ${
                !startEnabled || lightsOut
                  ? "cursor-not-allowed border border-border text-muted-2 opacity-50"
                  : "bg-red text-white hover:brightness-110"
              }`}
            >
              {lightsOut ? "Lights out…" : "Start Race"}
            </button>
          ) : (
            <span />
          )}
        </div>
        <button
          type="button"
          onClick={() => canEnableStrategy && setARISOn(!isARISOn)}
          disabled={!canEnableStrategy && !isARISOn}
          title={
            !arisCapable
              ? "ARIS runs on Race sessions only."
              : !canEnableStrategy
                ? "Strategy ARIS can only be enabled from the race selector. Add Copilot to ask about this race."
                : undefined
          }
          className={`justify-self-end rounded px-2 py-0.5 font-mono-data text-[10px] uppercase ${
            !arisCapable || (!canEnableStrategy && !isARISOn)
              ? "cursor-not-allowed border border-border text-muted-2 opacity-50"
              : isARISOn
                ? "bg-red/15 text-red"
                : "border border-border text-muted hover:text-white"
          }`}
        >
          {isARISOn ? "● ARIS ON" : "○ ARIS OFF"}
        </button>
      </div>
      <div>
        {consolePlayState === "racing" && <SpeedWidget />}
      </div>
      {mode === "replay" && !packReady && (
        <div className="shrink-0 bg-amber/10 px-4 py-2 font-sans text-xs text-amber">
          {waitingMessage ??
            (packStage === "metadata" || packStage === "empty"
              ? "Loading session metadata…"
              : "Preparing race data (laps, map)…")}
        </div>
      )}
      {packToast && (
        <div className="shrink-0 bg-red/10 px-4 py-1.5 font-mono-data text-[11px] uppercase tracking-wide text-red">
          {packToast}
        </div>
      )}
      {isARISOn && (ghostReason === "driver_did_not_race" || ghostReason === "ghost_data_gap") && (
        <div role="alert" className="shrink-0 bg-amber/10 px-4 py-2 font-mono-data text-[11px] text-amber">
          {ghostUnavailableMessage(ghostReason, arisDriver, true)}
        </div>
      )}
      {waitingForLiveData && (
        <LiveSessionWaitBanner
          targetIso={session?.date ?? null}
          sessionType={session?.sessionType ?? "R"}
          note={waitingMessage ?? "Waiting for live data to come."}
        />
      )}
      {consolePlayState === "racing" && mode === "replay" && (waitingForRace || carCount === 0) && (
        <div className="shrink-0 bg-amber/10 px-4 py-2 font-sans text-xs text-amber">
          {waitingMessage ?? "Loading replay from lights out at 1×…"}
        </div>
      )}
      {isARISOn && racePhase !== "GREEN" && (
        <div
          className={`shrink-0 px-4 py-2 font-sans text-xs font-semibold ${
            racePhase === "RED_FLAG"
              ? "bg-[#E8002D]/20 text-[#E8002D]"
              : racePhase === "STANDING_START"
                ? "bg-white/10 text-white"
                : racePhase === "FORMATION_LAP"
                  ? "bg-green-900/30 text-green-400"
                  : "bg-[#FF8700]/20 text-[#FF8700]"
          }`}
        >
          {racePhase === "SC" && "🟡 SAFETY CAR — Pit loss reduced to ~11s. Cheap pit window."}
          {racePhase === "VSC" && "🟡 VIRTUAL SAFETY CAR — Pace delta limited."}
          {racePhase === "RED_FLAG" && "🔴 RED FLAG — Free tyre change. Strategy reset."}
          {racePhase === "STANDING_START" && "🏁 STANDING START — Prior lap deltas cleared."}
          {racePhase === "FORMATION_LAP" && "🟢 EXTRA FORMATION LAP"}
        </div>
      )}
      <StrategyChangeBanner />
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <RaceFinishedDebrief />
        {isNarrow ? (
          <div className="h-full min-h-0 overflow-y-auto [overflow-anchor:none]">
            <MobileConsole
              showComms={isARISOn || copilotDocked}
              slots={analyticsSlots}
              onAdd={addAnalytics}
              onRemove={removeAnalytics}
              onMove={moveAnalytics}
            />
          </div>
        ) : (
          <div className="h-full min-h-0 overflow-y-auto [overflow-anchor:none]">
            {layoutReady ? (
              <div
                className="relative w-full"
                style={{ height: `${MAIN_ROW_VH + ANALYTICS_BASE_VH}vh` }}
              >
                <Layout
                  key={layoutEpoch}
                  ref={layoutRef}
                  model={model}
                  factory={factory}
                  onRenderTab={renderTabWithTearOff}
                  onModelChange={handleModelChange}
                  realtimeResize
                />
              </div>
            ) : (
              <div className="h-full w-full bg-carbon" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
