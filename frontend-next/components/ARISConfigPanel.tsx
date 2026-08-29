"use client";

import { ARISStrategyWait } from "@/components/ARISStrategyWait";
import { TyreIcon } from "@/components/ui/TyreIcon";
import { normalizeCompound } from "@/lib/compounds";
import type { DriverListing, StratPlan } from "@/lib/types";
import type { ARISMode } from "@/store/raceStore";

function driverInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase() || "?";
}

function strategyKind(plan: StratPlan, index: number): "recommended" | "alternative" | "aggressive" {
  if (plan.recommended || /recommend/i.test(plan.name)) return "recommended";
  if (/aggress/i.test(plan.name) || index === 2) return "aggressive";
  return "alternative";
}

function PlanCard({
  plan,
  index,
  selected,
  onSelect,
}: {
  plan: StratPlan;
  index: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const kind = strategyKind(plan, index);
  const compounds = [plan.start_compound, ...plan.pit_compounds].filter(Boolean);
  const title =
    kind === "recommended" ? "Recommended" : kind === "aggressive" ? "Aggressive" : "Alternative";
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-[8px] border p-4 text-left transition-colors ${
        selected
          ? "border-red bg-red/10 replay-glow-red"
          : plan.recommended
            ? "border-red/40 bg-red/5 hover:border-red"
            : "border-border bg-obsidian hover:border-red/40"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono-data text-[11px] uppercase tracking-widest text-white">
          {kind === "recommended" ? "★ " : ""}
          {title}
        </span>
        {plan.risk ? (
          <span className="font-mono-data text-[9px] uppercase text-muted">{plan.risk} risk</span>
        ) : null}
      </div>
      <p className="mt-1 font-mono-data text-[11px] text-muted">{plan.name}</p>
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {compounds.map((c, i) => (
          <span key={`${c}-${i}`} className="flex items-center gap-1">
            {i > 0 && <span className="font-mono-data text-[10px] text-muted">→</span>}
            <TyreIcon compound={normalizeCompound(c)} size={18} />
          </span>
        ))}
      </div>
      <div className="mt-2 font-mono-data text-[10px] text-muted-2">
        Start {plan.start_compound} · pits {plan.pit_laps.length ? plan.pit_laps.map((l) => `L${l}`).join(", ") : "—"}
      </div>
      {plan.description ? (
        <p className="mt-2 font-mono-data text-[10px] leading-relaxed text-muted">{plan.description}</p>
      ) : null}
    </button>
  );
}

export function ARISConfigPanel({
  phase,
  arisMode,
  drivers,
  selectedDriver,
  plans,
  selectedPlanId,
  analysisPending,
  onArisMode,
  onDriver,
  onGetStrategies,
  onPlan,
  onContinue,
  continueLabel = "Start Race",
}: {
  phase: "driver" | "strategies";
  arisMode: ARISMode;
  drivers: DriverListing[];
  selectedDriver: string | null;
  plans: StratPlan[];
  selectedPlanId: string | null;
  analysisPending?: boolean;
  onArisMode: (mode: ARISMode) => void;
  onDriver: (code: string) => void;
  onGetStrategies?: () => void;
  onPlan: (id: string) => void;
  onContinue?: () => void;
  continueLabel?: string;
}) {
  const canStart = Boolean(selectedDriver && plans.length > 0 && selectedPlanId);

  return (
    <section className="flex flex-col gap-5">
      {phase === "driver" && (
        <>
          <div>
            <div className="font-mono-data text-[10px] uppercase tracking-[0.22em] text-red">Step 02</div>
            <h2 className="mt-1 text-xl font-bold tracking-wide text-white uppercase sm:text-2xl">
              Select Driver
            </h2>
            <p className="mt-1 font-mono-data text-[11px] text-muted">
              Choose who ARIS runs for, then fetch strategies.
            </p>
          </div>

          <div>
            <div className="mb-2 font-mono-data text-[10px] uppercase tracking-widest text-muted">ARIS control</div>
            <div className="flex gap-2">
              {(["auto", "assisted"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => onArisMode(m)}
                  className={`rounded-[8px] border px-4 py-2 font-mono-data text-[11px] uppercase ${
                    arisMode === m ? "border-red bg-red/15 text-white" : "border-border bg-obsidian text-muted hover:text-white"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 font-mono-data text-[10px] uppercase tracking-widest text-muted">Driver grid</div>
            <div className="grid grid-cols-4 gap-2 sm:grid-cols-5 md:grid-cols-10">
              {drivers.map((d) => {
                const on = selectedDriver === d.driver_code;
                return (
                  <button
                    key={d.driver_code}
                    type="button"
                    onClick={() => onDriver(d.driver_code)}
                    className={`flex flex-col items-center gap-1.5 rounded-[8px] border p-2 ${
                      on ? "border-red bg-red/10 replay-glow-red" : "border-border bg-obsidian hover:border-red/40"
                    }`}
                  >
                    <span className="h-1 w-full rounded-full" style={{ background: d.team_colour }} />
                    {d.headshot_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={d.headshot_url} alt="" className="h-8 w-8 rounded-full object-cover" />
                    ) : (
                      <span
                        className="flex h-8 w-8 items-center justify-center rounded-full font-mono-data text-[10px] font-bold text-white"
                        style={{ background: `${d.team_colour}33`, color: "#fff" }}
                      >
                        {driverInitials(d.full_name)}
                      </span>
                    )}
                    <span className="font-mono-data text-[10px] text-white">
                      #{d.driver_number} {d.driver_code}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <button
            type="button"
            disabled={!selectedDriver}
            title={!selectedDriver ? "Choose a driver first." : undefined}
            onClick={onGetStrategies}
            className="self-start rounded-[8px] bg-safety px-5 py-2.5 font-mono-data text-[11px] uppercase tracking-widest text-white hover:brightness-110 disabled:cursor-not-allowed disabled:bg-obsidian disabled:text-muted-2"
          >
            Get Strategies
          </button>
        </>
      )}

      {phase === "strategies" && (
        <>
          <div>
            <div className="font-mono-data text-[10px] uppercase tracking-[0.22em] text-red">Step 03</div>
            <h2 className="mt-1 text-xl font-bold tracking-wide text-white uppercase sm:text-2xl">
              Pre-Race Strategy
            </h2>
            <p className="mt-1 font-mono-data text-[11px] text-muted">
              {selectedDriver ? `Plans for ${selectedDriver}. Select one before starting.` : "Fetching strategies…"}
            </p>
          </div>

          {analysisPending && <ARISStrategyWait pending />}

          {!analysisPending && (
            <div className="flex w-full flex-col gap-4">
              <div className="flex gap-3 overflow-x-auto pb-1">
                {plans.map((p, i) => (
                  <div key={p.id} className="min-w-[220px] flex-1">
                    <PlanCard
                      plan={p}
                      index={i}
                      selected={selectedPlanId === p.id}
                      onSelect={() => onPlan(p.id)}
                    />
                  </div>
                ))}
              </div>
              <button
                type="button"
                disabled={!canStart}
                title={!canStart ? "Select a strategy to start the race." : undefined}
                onClick={onContinue}
                className="w-full rounded-[8px] bg-safety px-5 py-3 font-mono-data text-[12px] uppercase tracking-widest text-white hover:brightness-110 disabled:cursor-not-allowed disabled:bg-obsidian disabled:text-muted-2 sm:w-auto sm:self-end"
              >
                {continueLabel}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
