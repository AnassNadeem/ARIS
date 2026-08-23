"use client";

import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import {
  Actions,
  DockLocation,
  Layout,
  Model,
  type IJsonModel,
  type ILayoutApi,
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

// How far a drag of the bottom "grow canvas" handle can extend the layout,
// in pixels, before the console area needs to be scrolled to reach it.
const MAX_EXTRA_CANVAS_HEIGHT = 4000;
const CANVAS_HEIGHT_STEP = 420;

const ANALYTICS_TABSET_ID = "analytics-tabset";
const COMMS_TABSET_ID = "comms-tabset";

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
    weight: 75,
    children: [
      {
        type: "tabset",
        weight: 62,
        children: [tab("trackmap", "Track Map", { enableClose: false })],
      },
      {
        type: "column",
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

  return {
    global: {
      tabEnableClose: true,
      tabSetEnableMaximize: true,
      tabSetMinWidth: 160,
      tabSetMinHeight: 100,
    },
    borders: [],
    layout: {
      type: "row",
      children: [
        mainRow,
        {
          type: "tabset",
          id: ANALYTICS_TABSET_ID,
          weight: 25,
          children: [
            tab("tyredeg", "Tyre Deg"),
            tab("sectortimes", "Sector Times"),
            tab("gapchart", "Gap Chart"),
          ],
        },
      ],
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

  // ARIS strategy scoring only applies to Race / Sprint Race sessions.
  const arisCapable = !session || session.sessionType === "R" || session.sessionType === "S";

  const [extraHeight, setExtraHeight] = useState(0);
  const extraHeightRef = useRef(0);

  useEffect(() => {
    setConsoleMode(mode);
  }, [mode, setConsoleMode]);

  useEffect(() => {
    if (!arisCapable && isARISOn) setARISOn(false);
  }, [arisCapable, isARISOn, setARISOn]);

  function growCanvas(deltaPx: number) {
    const next = Math.max(0, Math.min(MAX_EXTRA_CANVAS_HEIGHT, extraHeightRef.current + deltaPx));
    extraHeightRef.current = next;
    setExtraHeight(next);
  }

  function handleGrowHandlePointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    e.preventDefault();
    const startY = e.clientY;
    const startExtra = extraHeightRef.current;
    function onMove(ev: PointerEvent) {
      const next = Math.max(0, Math.min(MAX_EXTRA_CANVAS_HEIGHT, startExtra + (ev.clientY - startY)));
      extraHeightRef.current = next;
      setExtraHeight(next);
    }
    function onUp() {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  // Dynamically add/remove the Comms tab if ARIS is toggled after mount.
  useEffect(() => {
    if (isARISOn === arisOnAtMount.current) return;
    arisOnAtMount.current = isARISOn;
    if (isARISOn) {
      if (!model.getNodeById(COMMS_TABSET_ID)) {
        const root = model.getRootRow();
        if (root) {
          model.doAction(
            Actions.addNode(tab("comms", "ARIS Comms"), root.getId(), DockLocation.RIGHT, -1),
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

  // Not a component definition: this is flexlayout's per-node render callback,
  // invoked imperatively by the layout engine rather than rendered as JSX.
  const factory = useMemo(() => {
    return function renderTabContent(node: TabNode) {
      const componentId = node.getComponent() ?? "";
      return <PanelWrapper>{renderPanel(componentId)}</PanelWrapper>;
    };
  }, []);

  function handleAddPanel(componentId: string) {
    const json = tab(componentId);
    if (componentId === "comms" || componentId === "trackmap" || componentId === "timingtower") {
      layoutRef.current?.addTabToActiveTabSet(json);
      return;
    }
    if (model.getNodeById(ANALYTICS_TABSET_ID)) {
      layoutRef.current?.addTabToTabSet(ANALYTICS_TABSET_ID, json);
    } else {
      layoutRef.current?.addTabToActiveTabSet(json);
    }
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
            <button
              onClick={() => growCanvas(CANVAS_HEIGHT_STEP)}
              title="Grow the console downward so more panels fit without opening a new window"
              className="rounded border border-border px-2 py-1 font-mono-data text-[10px] uppercase text-muted hover:border-white hover:text-white"
            >
              ⤓ More space
            </button>
            <AnalyticsCatalogue onAdd={handleAddPanel} />
          </>
        }
      />
      <div className="relative min-h-0 flex-1 overflow-y-auto">
        <div className="relative" style={{ height: `calc(100% + ${extraHeight}px)` }}>
          <Layout
            ref={layoutRef}
            model={model}
            factory={factory}
            onRenderTab={renderTabWithTearOff}
            realtimeResize
          />
        </div>
        <div
          onPointerDown={handleGrowHandlePointerDown}
          onDoubleClick={() => growCanvas(-extraHeightRef.current)}
          title="Drag to grow the console downward, then scroll to arrange more panels. Double-click to reset."
          className="sticky bottom-0 left-0 z-20 flex h-3 w-full cursor-row-resize select-none items-center justify-center gap-2 border-t border-border bg-surface-2 hover:bg-border"
        >
          <span className="h-0.5 w-8 rounded bg-muted-2" />
          {extraHeight > 0 && (
            <span className="font-mono-data text-[9px] text-muted-2">
              +{extraHeight}px — scroll to see more, double-click to reset
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
