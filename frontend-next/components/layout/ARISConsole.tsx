"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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
import { PanelWrapper, renderTabWithTearOff } from "@/components/layout/PanelWrapper";
import { AnalyticsCatalogue } from "@/components/layout/AnalyticsCatalogue";
import { ConnectionStatus } from "@/components/ui/ConnectionStatus";
import { catalogueEntry, renderPanel } from "@/lib/panelRegistry";
import { MockRaceFeed } from "@/lib/mockRaceFeed";
import { broadcastRaceState } from "@/lib/broadcastChannel";

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
              children: [tab("comms", "ARIS Comms", { enableClose: false })],
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

  useEffect(() => {
    setConsoleMode(mode);
  }, [mode, setConsoleMode]);

  // Dynamically add/remove the Comms tab if ARIS is toggled after mount.
  useEffect(() => {
    if (isARISOn === arisOnAtMount.current) return;
    arisOnAtMount.current = isARISOn;
    if (isARISOn) {
      if (!model.getNodeById(COMMS_TABSET_ID)) {
        const root = model.getRootRow();
        if (root) {
          model.doAction(
            Actions.addNode(tab("comms", "ARIS Comms", { enableClose: false }), root.getId(), DockLocation.RIGHT, -1),
          );
        }
      }
    }
  }, [isARISOn, model]);

  useEffect(() => {
    setConnectionStatus("connecting");
    const feed = new MockRaceFeed(useRaceStore);
    feedRef.current = feed;
    feed.start();
    const t = setTimeout(() => setConnectionStatus("connected", 340), 600);
    return () => {
      feed.stop();
      clearTimeout(t);
      setConnectionStatus("disconnected");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      <div className="flex h-11 shrink-0 items-center gap-4 border-b border-border bg-surface-2 px-3">
        <span className="font-mono-data text-[11px] font-semibold text-white">
          {session?.circuitName ?? "ARIS"} · {session?.year ?? ""}
        </span>
        <span className="font-mono-data text-[11px] text-muted">
          Lap {currentLap} / {totalLaps}
        </span>
        <button
          onClick={() => setARISOn(!isARISOn)}
          className={`rounded px-2 py-0.5 font-mono-data text-[10px] uppercase ${
            isARISOn ? "bg-red/15 text-red" : "border border-border text-muted hover:text-white"
          }`}
        >
          {isARISOn ? `● ARIS ${arisMode}` : "○ ARIS OFF"}
        </button>
        <span className="ml-auto" />
        <ConnectionStatus />
        <AnalyticsCatalogue onAdd={handleAddPanel} />
      </div>
      <div className="relative min-h-0 flex-1">
        <Layout
          ref={layoutRef}
          model={model}
          factory={factory}
          onRenderTab={renderTabWithTearOff}
          realtimeResize
        />
      </div>
    </div>
  );
}
