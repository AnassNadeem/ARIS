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
import { ConnectionStatus } from "@/components/ui/ConnectionStatus";
import { catalogueEntry, renderPanel } from "@/lib/panelRegistry";
import { MockRaceFeed } from "@/lib/mockRaceFeed";
import { createRaceSocket } from "@/lib/raceSocket";
import { broadcastRaceState } from "@/lib/broadcastChannel";

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
  const analyticsRow = {
    type: "row",
    id: ANALYTICS_ROW_ID,
    weight: ANALYTICS_BASE_VH,
    children: [
      { type: "tabset", weight: 34, children: [tab("tyredeg", "Tyre Degradation")] },
      { type: "tabset", weight: 33, children: [tab("sectortimes", "Sector Times")] },
      { type: "tabset", weight: 33, children: [tab("gapchart", "Gap Chart")] },
    ],
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

export function ARISConsole({ mode }: { mode: "replay" | "live" }) {
  const session = useRaceStore((s) => s.session);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const arisMode = useRaceStore((s) => s.arisMode);
  const currentLap = useRaceStore((s) => s.currentLap);
  const totalLaps = useRaceStore((s) => s.totalLaps);
  const cars = useRaceStore((s) => s.cars);
  const ghostCar = useRaceStore((s) => s.ghostCar);
  const setConsoleMode = useRaceStore((s) => s.setConsoleMode);
  const setConnectionStatus = useRaceStore((s) => s.setConnectionStatus);
  const setARISOn = useRaceStore((s) => s.setARISOn);

  const layoutRef = useRef<ILayoutApi | null>(null);
  const [model] = useState<Model>(() => Model.fromJson(buildDefaultModel(useRaceStore.getState().isARISOn)));
  const arisOnAtMount = useRef(isARISOn);
  const feedRef = useRef<MockRaceFeed | null>(null);

  // Tracks total tab count so the analytics row can grow (or shrink back)
  // as panels are added to / removed from the console, instead of a manual
  // "more space" control.
  const tabCountRef = useRef(0);
  const [extraVh, setExtraVh] = useState(0);

  // ARIS strategy scoring only applies to Race / Sprint Race sessions.
  const arisCapable = !session || session.sessionType === "R" || session.sessionType === "S";

  useEffect(() => {
    setConsoleMode(mode);
  }, [mode, setConsoleMode]);

  useEffect(() => {
    if (!arisCapable && isARISOn) setARISOn(false);
  }, [arisCapable, isARISOn, setARISOn]);

  useEffect(() => {
    const analyticsRow = model.getNodeById(ANALYTICS_ROW_ID);
    tabCountRef.current = analyticsRow ? countTabsInSubtree(analyticsRow) : 0;
  }, [model]);

  // Dynamically add/remove the Comms tab if ARIS is toggled after mount.
  useEffect(() => {
    if (isARISOn === arisOnAtMount.current) return;
    arisOnAtMount.current = isARISOn;
    if (isARISOn) {
      if (!model.getNodeById(COMMS_TABSET_ID)) {
        const mainRow = model.getNodeById(MAIN_ROW_ID);
        if (mainRow) {
          model.doAction(
            Actions.addNode(tab("comms", "ARIS Comms"), mainRow.getId(), DockLocation.RIGHT, -1),
          );
        }
      }
    }
  }, [isARISOn, model]);

  // Real backend connection: attempts ws://localhost:8000. If a real ARIS
  // backend is running it takes over and the mock feed steps aside; if not,
  // the mock feed keeps the console demonstrable (matches the API mock
  // fallback pattern used throughout lib/api.ts).
  useEffect(() => {
    const feed = new MockRaceFeed(useRaceStore);
    feedRef.current = feed;
    feed.start();
    setConnectionStatus("connecting");
    const fallbackTimer = setTimeout(() => setConnectionStatus("connected", 340), 900);

    const socket = createRaceSocket(mode, `${session?.year}-${session?.round}`);
    socket.onOpen = () => feed.stop();
    socket.connect();

    return () => {
      feed.stop();
      socket.disconnect();
      clearTimeout(fallbackTimer);
      setConnectionStatus("disconnected");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  useEffect(() => {
    broadcastRaceState({ type: "tick", payload: { cars, ghostCar, currentLap, totalLaps } });
  }, [cars, ghostCar, currentLap, totalLaps]);

  // Grows the analytics row (and the scrollable canvas beneath the main
  // dock) whenever a panel is added there, and shrinks it back down when
  // panels are removed — so there's always room below without a manual
  // "more space" control. Scoped to the analytics row's own subtree so
  // adding a panel elsewhere (e.g. re-enabling ARIS Comms) doesn't grow it.
  const handleModelChange = useCallback((changedModel: Model, action: Action) => {
    if (action.type !== Actions.ADD_TAB && action.type !== Actions.DELETE_TAB) return;
    const analyticsRow = changedModel.getNodeById(ANALYTICS_ROW_ID);
    const count = analyticsRow ? countTabsInSubtree(analyticsRow) : 0;
    const delta = count - tabCountRef.current;
    tabCountRef.current = count;
    if (delta !== 0) {
      setExtraVh((v) => Math.max(0, Math.min(MAX_EXTRA_VH, v + delta * GROWTH_PER_TAB_VH)));
    }
  }, []);

  // Keeps the main dock pinned at MAIN_ROW_VH and routes all extra growth
  // into the analytics row's own weight (rather than letting flex
  // proportionally inflate the dock too).
  useEffect(() => {
    const root = model.getRootRow();
    if (!root) return;
    const children = root.getChildren();
    if (children.length !== 2) return; // analytics row was closed entirely
    model.doAction(Actions.adjustWeights(root.getId(), [MAIN_ROW_VH, ANALYTICS_BASE_VH + extraVh]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extraVh, model]);

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

  return (
    <div className="flex h-screen w-screen flex-col bg-carbon">
      <AppHeader
        compact
        backHref={mode === "replay" ? "/replay" : "/live"}
        right={
          <>
            <span className="hidden font-mono-data text-[11px] font-semibold text-white sm:inline">
              {session?.circuitName ?? "ARIS"} · {session?.year ?? ""}
            </span>
            <span className="font-mono-data text-[11px] text-muted">
              Lap {currentLap} / {totalLaps}
            </span>
            <button
              onClick={() => arisCapable && setARISOn(!isARISOn)}
              disabled={!arisCapable}
              title={!arisCapable ? "ARIS runs on Race and Sprint Race sessions only." : undefined}
              className={`rounded px-2 py-0.5 font-mono-data text-[10px] uppercase ${
                !arisCapable
                  ? "cursor-not-allowed border border-border text-muted-2 opacity-50"
                  : isARISOn
                    ? "bg-red/15 text-red"
                    : "border border-border text-muted hover:text-white"
              }`}
            >
              {isARISOn ? `● ARIS ${arisMode}` : "○ ARIS OFF"}
            </button>
            <ConnectionStatus />
            <AnalyticsCatalogue onAdd={handleAddPanel} />
          </>
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div style={{ height: `${MAIN_ROW_VH + ANALYTICS_BASE_VH + extraVh}vh` }} className="relative w-full">
          <Layout
            ref={layoutRef}
            model={model}
            factory={factory}
            onRenderTab={renderTabWithTearOff}
            onModelChange={handleModelChange}
            realtimeResize
          />
        </div>
      </div>
    </div>
  );
}
