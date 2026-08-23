"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { renderPanel, catalogueEntry } from "@/lib/panelRegistry";
import { subscribeRaceState } from "@/lib/broadcastChannel";
import { useRaceStore } from "@/store/raceStore";
import { PanelWrapper } from "@/components/layout/PanelWrapper";
import type { CarState } from "@/lib/types";

interface TickPayload {
  cars?: Record<string, CarState>;
  ghostCar?: CarState | null;
  currentLap?: number;
  totalLaps?: number;
}

/**
 * Torn-off panel window (opened via the ⤢ button). The main console window
 * is always the data source; this window only listens on BroadcastChannel
 * and re-renders the same panel component in isolation.
 */
export default function TornOffPanelPage() {
  const params = useParams<{ panelId: string }>();
  const panelId = params.panelId;
  const setCars = useRaceStore((s) => s.setCars);
  const setGhostCar = useRaceStore((s) => s.setGhostCar);
  const setCurrentLap = useRaceStore((s) => s.setCurrentLap);
  const setTotalLaps = useRaceStore((s) => s.setTotalLaps);

  useEffect(() => {
    document.title = `ARIS — ${catalogueEntry(panelId)?.label ?? panelId}`;
    return subscribeRaceState((msg) => {
      if (msg.type !== "tick") return;
      const payload = msg.payload as TickPayload;
      if (payload.cars) setCars(payload.cars);
      if (payload.ghostCar !== undefined) setGhostCar(payload.ghostCar ?? null);
      if (payload.currentLap != null) setCurrentLap(payload.currentLap);
      if (payload.totalLaps != null) setTotalLaps(payload.totalLaps);
    });
  }, [panelId, setCars, setGhostCar, setCurrentLap, setTotalLaps]);

  return (
    <div className="h-screen w-screen bg-carbon">
      <PanelWrapper>{renderPanel(panelId)}</PanelWrapper>
    </div>
  );
}
