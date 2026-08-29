"use client";

import { useEffect, useState } from "react";
import { DegradationChart } from "@/components/aris/DegradationChart";
import { GhostVsRealChart } from "@/components/aris/GhostVsRealChart";
import { RaceDebriefView } from "@/components/aris/RaceDebriefView";
import { explainFeatureEnabled } from "@/lib/api";
import { useRaceStore } from "@/store/raceStore";
import { PanelEmpty } from "@/components/ui/PanelStates";

type SubTab = "deg" | "ghost" | "debrief";

export function ExplainPanel() {
  const [tab, setTab] = useState<SubTab>("deg");
  const featureOn = explainFeatureEnabled();
  const tabRequest = useRaceStore((s) => s.explainTabRequest);
  const setExplainTabRequest = useRaceStore((s) => s.setExplainTabRequest);
  const debriefDismissed = useRaceStore((s) => s.debriefDismissed);
  const setDebriefOpen = useRaceStore((s) => s.setDebriefOpen);
  const raceFinished = useRaceStore((s) => s.raceFinished);

  useEffect(() => {
    if (!tabRequest) return;
    setTab(tabRequest);
    setExplainTabRequest(null);
  }, [tabRequest, setExplainTabRequest]);

  if (!featureOn) {
    return (
      <PanelEmpty
        title="Explain"
        detail="Degradation curves, ARIS ghost vs real, and race debrief. Set NEXT_PUBLIC_ARIS_EXPLAIN=1 to enable this panel."
      />
    );
  }

  const tabs: { id: SubTab; label: string }[] = [
    { id: "deg", label: "Degradation Curves" },
    { id: "ghost", label: "Ghost vs Real" },
    { id: "debrief", label: "Race Debrief" },
  ];

  return (
    <div className="flex h-full flex-col bg-carbon">
      <div className="flex shrink-0 overflow-x-auto border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`whitespace-nowrap px-4 py-2 font-sans text-[10px] uppercase tracking-wide ${
              tab === t.id ? "border-b-2 border-red text-white" : "text-muted hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
        {(raceFinished || debriefDismissed) && (
          <button
            type="button"
            onClick={() => setDebriefOpen(true)}
            className="ml-auto whitespace-nowrap px-4 py-2 font-sans text-[10px] uppercase tracking-wide text-red hover:text-white"
          >
            Post-race debrief
          </button>
        )}
      </div>
      <div className="min-h-0 flex-1">
        {tab === "deg" && <DegradationChart />}
        {tab === "ghost" && <GhostVsRealChart />}
        {tab === "debrief" && <RaceDebriefView />}
      </div>
    </div>
  );
}