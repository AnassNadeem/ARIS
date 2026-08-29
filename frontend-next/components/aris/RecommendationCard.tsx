"use client";

import { useState } from "react";
import { useRaceStore } from "@/store/raceStore";
import { askARIS, postGhostRecompute, sendARISAction } from "@/lib/api";
import type { Compound, StratPlan } from "@/lib/types";

export function RecommendationCard() {
  const rec = useRaceStore((s) => s.pendingRecommendation);
  const arisMode = useRaceStore((s) => s.arisMode);
  const activeStrategy = useRaceStore((s) => s.activeStrategy);
  const approve = useRaceStore((s) => s.approveRecommendation);
  const deny = useRaceStore((s) => s.denyRecommendation);
  const alter = useRaceStore((s) => s.alterRecommendation);

  const [showAlter, setShowAlter] = useState(false);
  const [explain, setExplain] = useState<string | null>(null);
  const [alterTyre, setAlterTyre] = useState<Compound>("MEDIUM");
  const [alterLap, setAlterLap] = useState<number>(0);
  const [alterNote, setAlterNote] = useState("");

  if (!rec) return null;

  const recPit = rec.action.pit_lap ?? rec.action.pit_laps?.[0];
  const planPit = activeStrategy?.pit_laps?.[0];
  const differs = activeStrategy != null && recPit != null && recPit !== planPit;

  async function handleAdopt() {
    const store = useRaceStore.getState();
    const session = store.session;
    const driver = store.arisDriver ?? store.selectedDriver;
    if (!session || !driver || !rec) return;
    const pits = rec.action.pit_laps?.length
      ? rec.action.pit_laps
      : recPit != null
        ? [recPit]
        : [];
    const compounds = rec.action.pit_compounds?.length
      ? rec.action.pit_compounds
      : rec.action.pit_compound
        ? [rec.action.pit_compound]
        : [];
    const plan: StratPlan = {
      id: rec.id,
      name: rec.label,
      pit_laps: pits.filter((n): n is number => n != null),
      pit_compounds: compounds,
      start_compound: activeStrategy?.start_compound ?? "MEDIUM",
    };
    store.setActiveStrategy(plan);
    const out = await postGhostRecompute({
      year: session.year,
      round: session.round,
      driver,
      currentLap: store.currentLap,
      pitLaps: plan.pit_laps,
      compounds: plan.pit_compounds,
      label: plan.name,
    });
    if (out?.ticks) store.mergeGhostTicksFrom(store.currentLap, out.ticks);
    store.pushComms({
      id: `${rec.id}-adopted-${Date.now()}`,
      lap: rec.lap,
      source: "USER",
      text: `Adopted new strategy: ${rec.label}. Ghost from lap ${store.currentLap} follows the new plan.`,
      timestamp: Date.now(),
    });
    approve();
  }

  async function handleApprove() {
    await sendARISAction({ action: "approve", lap: rec!.lap, tyre: rec!.action.pit_compound ?? undefined });
    approve();
  }
  async function handleDeny() {
    await sendARISAction({ action: "deny", lap: rec!.lap });
    deny();
  }
  async function handleAlterSubmit() {
    await sendARISAction({ action: "alter", lap: alterLap || rec!.lap, tyre: alterTyre, note: alterNote });
    alter({ action: { ...rec!.action, pit_compound: alterTyre, pit_lap: alterLap || rec!.action.pit_lap } });
    setShowAlter(false);
  }
  async function handleExplain() {
    const { answer } = await askARIS(
      `Explain the strategy recommendation for lap ${rec!.lap}: ${rec!.action.pit_compound ?? ""}`,
    );
    setExplain(answer);
  }

  return (
    <div className="m-2 rounded-[8px] border border-red bg-surface p-3">
      <div className="mb-1 font-mono-data text-[10px] uppercase tracking-wide text-red">
        L{rec.lap} [ARIS RECOMMENDS] {rec.label}
      </div>
      <div className="font-mono-data text-[11px] text-muted">
        Projected: P4 · +2.1s ahead · {(rec.rank_score * 100).toFixed(0)}% confidence
      </div>
      <div className="mt-1 font-mono-data text-[10px] text-muted">
        Delta {rec.delta_vs_stay_out_s.toFixed(1)}s · std {rec.confidence_std_s.toFixed(1)}s · evidence: {rec.evidence}
      </div>

      {arisMode === "assisted" ? (
        <div className="mt-3 flex flex-wrap gap-2 font-mono-data text-[10px] uppercase">
          <button onClick={handleApprove} className="rounded bg-green px-2.5 py-1 text-carbon">✓ APPROVE</button>
          <button onClick={handleDeny} className="rounded border border-border px-2.5 py-1 text-white hover:border-red">✗ DENY</button>
          <button
            onClick={() => setShowAlter((v) => !v)}
            className="rounded border border-border px-2.5 py-1 text-white hover:border-amber"
          >
            ✎ ALTER
          </button>
          <button onClick={handleExplain} className="rounded border border-border px-2.5 py-1 text-white hover:border-white">
            ? EXPLAIN
          </button>
        </div>
      ) : (
        <div className="mt-2 font-mono-data text-[10px] text-muted">Auto mode — ARIS will execute without approval.</div>
      )}

      {differs && (
        <button
          type="button"
          onClick={() => void handleAdopt()}
          className="mt-2 rounded bg-red px-2.5 py-1 font-mono-data text-[10px] uppercase text-white"
        >
          Adopt new strategy
        </button>
      )}

      {showAlter && (
        <div className="mt-3 flex flex-col gap-2 border-t border-border pt-2 font-mono-data text-[10px]">
          <div className="flex items-center gap-2">
            <span className="text-muted">Tyre</span>
            <select
              value={alterTyre}
              onChange={(e) => setAlterTyre(e.target.value as Compound)}
              className="rounded border border-border bg-carbon px-1.5 py-0.5 text-white"
            >
              {(["SOFT", "MEDIUM", "HARD"] as Compound[]).map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <span className="text-muted">Lap</span>
            <input
              type="number"
              placeholder={String(rec.lap)}
              value={alterLap || ""}
              onChange={(e) => setAlterLap(Number(e.target.value))}
              className="w-16 rounded border border-border bg-carbon px-1.5 py-0.5 text-white"
            />
          </div>
          <input
            type="text"
            placeholder="Note (optional)"
            value={alterNote}
            onChange={(e) => setAlterNote(e.target.value)}
            className="rounded border border-border bg-carbon px-1.5 py-0.5 text-white"
          />
          <button onClick={handleAlterSubmit} className="self-start rounded bg-amber px-2.5 py-1 text-carbon">
            SUBMIT ALTER
          </button>
        </div>
      )}

      {explain && (
        <div className="mt-3 border-t border-border pt-2 font-mono-data text-[10px] leading-relaxed text-white/90">
          <span className="text-purple-300">[ARIS ANALYSIS]</span> {explain}
        </div>
      )}
    </div>
  );
}
