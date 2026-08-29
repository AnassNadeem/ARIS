"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Actions,
  DockLocation,
  Layout,
  Model,
  type Action,
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
import { catalogueEntry, renderPanel } from "@/lib/panelRegistry";
import { explainFeatureEnabled, getCircuitCoords } from "@/lib/api";
import { MockRaceFeed } from "@/lib/mockRaceFeed";
import { LiveSseFeed, ReplayFrameFeed } from "@/lib/liveFeed";
import { broadcastRaceState } from "@/lib/broadcastChannel";
import { SpeedWidget } from "@/components/ui/SpeedWidget";
import { RaceFinishedDebrief } from "@/components/aris/RaceFinishedDebrief";
import { useArisRecommendLoop } from "@/lib/useArisRecommendLoop";
import { formatLapHeader } from "@/lib/formatLap";
import { sessionLabel } from "@/lib/sessionFlow";
import { useCountdown } from "@/lib/useCountdown";
import {
  loadPersistedLayout,
  rowWeightFromLayout,
  savePersistedLayout,
} from "@/lib/layoutPersist";

const COMMS_TABSET_ID = "comms-tabset";
const MAIN_ROW_ID = "main-dock-row";
const ANALYTICS_ROW_ID = "analytics-row";

// The main dock's target height, in vh — kept pinned so the primary panels
// (track map, timing, comms) always fill exactly one screen. The analytics
// row below gets whatever is left of MAIN_ROW_VH + ANALYTICS_BASE_VH + extraVh,
// so it starts as a real "second screen" rather than squeezed alongside the dock.
const MAIN_ROW_VH = 100;
const ANALYTICS_BASE_VH = 56;
const GROWTH_PER_TAB_VH = 30;
const MAX_EXTRA_VH = 360;

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

/** Counts tab nodes in a node's subtree (itself included). */
function countTabsInSubtree(node: FlexNode): number {
  if (node.getType() === "tab") return 1;
  return node.getChildren().reduce((sum, child) => sum + countTabsInSubtree(child), 0);
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
        // Nested inside the (horizontal) main row, so it renders as a
        // vertical stack: Timing Tower on top, Lap Times below.
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

  // A second full-width row, below the main dock, seeded with the core
  // analytics panels. It's a normal flexlayout row — free to split, resize
  // via native splitters, and tear any tab off into its own window, exactly
  // like the dock above it.
  const analyticsChildren = [
    { type: "tabset", weight: 34, children: [tab("tyredeg", "Tyre Degradation")] },
    { type: "tabset", weight: 33, children: [tab("sectortimes", "Sector Times")] },
    { type: "tabset", weight: 33, children: [tab("gapchart", "Gap Chart")] },
  ];
  if (explainFeatureEnabled()) {
    analyticsChildren.push({ type: "tabset", weight: 34, children: [tab("explain", "Explain")] });
  }

  const analyticsRow = {
    type: "row",
    id: ANALYTICS_ROW_ID,
    weight: ANALYTICS_BASE_VH,
    children: analyticsChildren,
  };

  return {
    global: {
      // Root lays its own children out vertically (main dock, then the
      // analytics row below) — which flips each of those rows back to
      // horizontal for their own children. See flexlayout's alternating
      // row/column orientation model.
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

  // Tracks total tab count so the analytics row can grow (or shrink back)
  // as panels are added to / removed from the console, instead of a manual
  // "more space" control.
  const tabCountRef = useRef(0);
  const [extraVh, setExtraVh] = useState(0);

  // Load saved dock JSON after mount so SSR/default layout cannot overwrite it.
  useEffect(() => {
    const saved = loadPersistedLayout();
    if (saved) {
      try {
        setModel(Model.fromJson(saved));
        const weight = rowWeightFromLayout(saved, ANALYTICS_ROW_ID);
        if (weight != null) {
          setExtraVh(Math.max(0, Math.min(MAX_EXTRA_VH, weight - ANALYTICS_BASE_VH)));
        }
      } catch {
        // Corrupt JSON — keep the default model.
      }
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

  useEffect(() => {
    const analyticsRow = model.getNodeById(ANALYTICS_ROW_ID);
    tabCountRef.current = analyticsRow ? countTabsInSubtree(analyticsRow) : 0;
  }, [model]);

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
        store.getState().setWaiting(true, "Replay pack is still loading — waiting for FastF1.");
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

  // Grows the analytics row (and the scrollable canvas beneath the main
  // dock) whenever a panel is added there, and shrinks it back down when
  // panels are removed — so there's always room below without a manual
  // "more space" control. Scoped to the analytics row's own subtree so
  // adding a panel elsewhere (e.g. re-enabling ARIS Comms) doesn't grow it.
  const handleModelChange = useCallback((changedModel: Model, action: Action) => {
    if (action.type === Actions.ADD_TAB || action.type === Actions.DELETE_TAB) {
      const analyticsRow = changedModel.getNodeById(ANALYTICS_ROW_ID);
      const count = analyticsRow ? countTabsInSubtree(analyticsRow) : 0;
      const delta = count - tabCountRef.current;
      tabCountRef.current = count;
      if (delta !== 0) {
        setExtraVh((v) => Math.max(0, Math.min(MAX_EXTRA_VH, v + delta * GROWTH_PER_TAB_VH)));
      }
    }
    if (canPersistLayout.current) {
      savePersistedLayout(changedModel);
    }
  }, []);

  // Keeps the main dock pinned at MAIN_ROW_VH and routes all extra growth
  // into the analytics row's own weight (rather than letting flex
  // proportionally inflate the dock too).
  useEffect(() => {
    if (!layoutReady) return;
    canPersistLayout.current = true;
    const root = model.getRootRow();
    if (!root) return;
    const children = root.getChildren();
    if (children.length !== 2) return; // analytics row was closed entirely
    model.doAction(Actions.adjustWeights(root.getId(), [MAIN_ROW_VH, ANALYTICS_BASE_VH + extraVh]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extraVh, model, layoutReady]);

  // Not a component definition: this is flexlayout's per-node render callback,
  // invoked imperatively by the layout engine rather than rendered as JSX.
  const factory = useMemo(() => {
    return function renderTabContent(node: TabNode) {
      const componentId = node.getComponent() ?? "";
      return <PanelWrapper>{renderPanel(componentId)}</PanelWrapper>;
    };
  }, []);

  function handleAddPanel(componentId: string) {
    layoutRef.current?.addTabToActiveTabSet(tab(componentId));
  }

  useEffect(() => {
    if (!explainTabRequest) return;
    handleAddPanel("explain");
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
            <span className="hidden font-sans text-xs font-medium text-white sm:inline">
              {session?.circuitName ?? "ARIS"}
              {session?.year != null ? (
                <>
                  {" · "}
                  <span className="font-mono-data">{session.year}</span>
                </>
              ) : null}
            </span>
            {isARISOn && arisDriver && (
              <span className="hidden rounded bg-red/15 px-2 py-0.5 font-mono-data text-[10px] uppercase text-red sm:inline">
                ARIS for {arisDriver}
              </span>
            )}
            <span className="font-mono-data text-xs text-muted">
              {formatLapHeader(currentLap, totalLaps)}
            </span>
            {mode === "replay" && replayNotRacing && (
              <button
                type="button"
                disabled={!startEnabled || lightsOut}
                onClick={() => beginLightsOut()}
                title={!packReady ? "Waiting for laps and circuit map…" : "Lights-out on the track, then replay from lap 1"}
                className={`shrink-0 rounded px-3 py-1 font-mono-data text-[11px] uppercase tracking-wide ${
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
              className={`shrink-0 rounded px-2 py-0.5 font-mono-data text-[10px] uppercase ${
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
                className="rounded border border-border px-2 py-0.5 font-mono-data text-[10px] uppercase text-muted hover:text-white"
              >
                {copilotDocked ? "● Copilot" : "Add Copilot"}
              </button>
            )}
            <div className="shrink-0">
              <AnalyticsCatalogue onAdd={handleAddPanel} />
            </div>
          </>
        }
      />
      <SpeedWidget />
      {mode === "replay" && !packReady && (
        <div className="shrink-0 bg-amber/10 px-4 py-2 font-sans text-xs text-amber">
          {packStage === "metadata" || packStage === "empty"
            ? "Loading session metadata…"
            : "Preparing race data (laps, map)…"}
        </div>
      )}
      {packToast && (
        <div className="shrink-0 bg-red/10 px-4 py-1.5 font-mono-data text-[11px] uppercase tracking-wide text-red">
          {packToast}
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
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <RaceFinishedDebrief />
        <div className="h-full min-h-0 overflow-y-auto [overflow-anchor:none]">
          <div style={{ height: `${MAIN_ROW_VH + ANALYTICS_BASE_VH + extraVh}vh` }} className="relative w-full">
            {layoutReady ? (
              <Layout
                ref={layoutRef}
                model={model}
                factory={factory}
                onRenderTab={renderTabWithTearOff}
                onModelChange={handleModelChange}
                realtimeResize
              />
            ) : (
              <div className="h-full w-full bg-carbon" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
