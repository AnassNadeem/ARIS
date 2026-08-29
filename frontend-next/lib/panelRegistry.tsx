import type { ComponentType, ReactNode } from "react";
import { ComingSoon } from "@/components/panels/ComingSoon";
import { TrackMap } from "@/components/panels/TrackMap";
import { TimingTower } from "@/components/panels/TimingTower";
import { LapTimesChart } from "@/components/panels/LapTimesChart";
import { TyreDegradation } from "@/components/panels/TyreDegradation";
import { SectorTimes } from "@/components/panels/SectorTimes";
import { GapChart } from "@/components/panels/GapChart";
import { PositionTrace } from "@/components/panels/PositionTrace";
import { StintSummary } from "@/components/panels/StintSummary";
import { TyreStrategyBar } from "@/components/panels/TyreStrategyBar";
import { PitStopTimeline } from "@/components/panels/PitStopTimeline";
import { WeatherForecast } from "@/components/panels/WeatherForecast";
import { ARISComms } from "@/components/aris/ARISComms";
import { ExplainPanel } from "@/components/aris/ExplainPanel";
import { GhostDelta } from "@/components/panels/GhostDelta";

export type PanelCategory = "core" | "analytics";

export interface PanelCatalogueEntry {
  componentId: string;
  label: string;
  status: "built" | "coming-soon";
  description: string;
  category: PanelCategory;
  /** Core panels that should only exist once by default (still re-addable). */
  singleton?: boolean;
}

export const PANEL_CATALOGUE: PanelCatalogueEntry[] = [
  { componentId: "trackmap", label: "Track map", status: "built", category: "core", singleton: true, description: "Live circuit map with car positions, dead-reckoned between ticks." },
  { componentId: "timingtower", label: "Timing tower", status: "built", category: "core", singleton: true, description: "Classic F1 timing tower: position, gap, last lap, tyre." },
  { componentId: "laptimes", label: "Lap times", status: "built", category: "analytics", description: "Lap time trace with safety car zones overlaid." },
  { componentId: "comms", label: "ARIS comms", status: "built", category: "core", singleton: true, description: "ARIS radio channel — recommendations, Ask ARIS, and Copilot." },
  { componentId: "tyredeg", label: "Tyre degradation", status: "built", category: "analytics", description: "Lap-time vs tyre age, per compound, for selected driver." },
  { componentId: "sectortimes", label: "Sector times", status: "built", category: "analytics", description: "S1/S2/S3 per lap, delta from personal best." },
  { componentId: "gapchart", label: "Gap chart", status: "built", category: "analytics", description: "Gap to car ahead and car behind over race distance." },
  { componentId: "positiontrace", label: "Position trace", status: "built", category: "analytics", description: "Position (1-20) per lap for all selected drivers." },
  { componentId: "stintsummary", label: "Stint summary", status: "built", category: "analytics", description: "Table: stint number, compound, start lap, end lap, avg lap time." },
  { componentId: "tyrestrategy", label: "Tyre strategy comparison", status: "built", category: "analytics", description: "All drivers' tyre strategies as coloured stint bars." },
  { componentId: "pitstoptimeline", label: "Pit stop timeline", status: "built", category: "analytics", description: "All pit stops as a scatter plot, lap vs duration." },
  { componentId: "speedtrace", label: "Speed trace", status: "coming-soon", category: "analytics", description: "Speed vs track distance for a selected lap. Requires per-lap telemetry data from FastF1." },
  { componentId: "throttlebrake", label: "Throttle / brake", status: "coming-soon", category: "analytics", description: "Throttle and brake trace vs track distance." },
  { componentId: "corneranalysis", label: "Corner analysis", status: "coming-soon", category: "analytics", description: "Mini-sector times per corner." },
  { componentId: "weatheroverlay", label: "Weather forecast", status: "built", category: "analytics", description: "Session-by-session forecast plus track/air temp and rain probability over race distance." },
  { componentId: "dirtyair", label: "Dirty air zone", status: "coming-soon", category: "analytics", description: "Laps where gap to car ahead < 1.0 s." },
  { componentId: "undercutwindow", label: "Undercut window", status: "coming-soon", category: "analytics", description: "ARIS undercut probability over race distance." },
  { componentId: "ghostdelta", label: "Ghost delta", status: "built", category: "analytics", description: "Time delta between real driver and ARIS ghost driver." },
  { componentId: "explain", label: "Explain", status: "built", category: "analytics", description: "Degradation curves, ARIS ghost vs real, and race debrief with recommend() top-3." },
];

export function catalogueEntry(componentId: string): PanelCatalogueEntry | undefined {
  return PANEL_CATALOGUE.find((p) => p.componentId === componentId);
}

const BUILT_COMPONENTS: Record<string, ComponentType> = {
  trackmap: TrackMap,
  timingtower: TimingTower,
  laptimes: LapTimesChart,
  comms: ARISComms,
  tyredeg: TyreDegradation,
  sectortimes: SectorTimes,
  gapchart: GapChart,
  positiontrace: PositionTrace,
  stintsummary: StintSummary,
  tyrestrategy: TyreStrategyBar,
  pitstoptimeline: PitStopTimeline,
  weatheroverlay: WeatherForecast,
  ghostdelta: GhostDelta,
  explain: ExplainPanel,
};

/** Renders a panel's content directly, so callers never create a component during render. */
export function renderPanel(componentId: string): ReactNode {
  const entry = catalogueEntry(componentId);
  if (!entry) return <ComingSoon title={componentId} description="Unknown panel type." />;
  if (entry.status === "coming-soon") {
    return <ComingSoon title={entry.label} description={entry.description} />;
  }
  const Comp: ComponentType | undefined = BUILT_COMPONENTS[componentId];
  if (!Comp) return <ComingSoon title={entry.label} description={entry.description} />;
  return <Comp />;
}
