"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ARISConfigPanel } from "@/components/ARISConfigPanel";
import { LiveSessionPicker } from "@/components/LiveSessionPicker";
import { getDrivers, getQuickAnalysis } from "@/lib/api";
import { asSessionType, pickDefaultHubSession, shouldAutoStartLiveSession } from "@/lib/liveSetup";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";
import {
  canStartRace,
  isArisCapableSession,
  nextSelectorStep,
  sessionLabel,
  type SelectorStep,
} from "@/lib/sessionFlow";
import { useRaceStore } from "@/store/raceStore";
import type { HubSession, LiveHub, SessionType } from "@/lib/types";

export function LiveSetupFlow({
  hub,
  onLoaded,
  onEnterDemo,
}: {
  hub: LiveHub;
  onLoaded: () => void;
  onEnterDemo: () => void;
}) {
  const setSession = useRaceStore((s) => s.setSession);
  const setARISDriver = useRaceStore((s) => s.setARISDriver);
  const setSelectedDriver = useRaceStore((s) => s.setSelectedDriver);
  const setARISOn = useRaceStore((s) => s.setARISOn);
  const setARISMode = useRaceStore((s) => s.setARISMode);
  const arisMode = useRaceStore((s) => s.arisMode);
  const arisEnabled = useRaceStore((s) => s.arisEnabled);
  const setDriverLocked = useRaceStore((s) => s.setDriverLocked);
  const setStrategies = useRaceStore((s) => s.setStrategies);
  const setSelectedStrategy = useRaceStore((s) => s.setSelectedStrategy);
  const strategies = useRaceStore((s) => s.strategies);
  const selectedStrategy = useRaceStore((s) => s.selectedStrategy);
  const setFocusDriver = useRaceStore((s) => s.setFocusDriver);
  const setTotalLaps = useRaceStore((s) => s.setTotalLaps);
  const setGridDrivers = useRaceStore((s) => s.setGridDrivers);

  const [step, setStep] = useState<SelectorStep>("circuit");
  const [picked, setPicked] = useState<HubSession | null>(() => pickDefaultHubSession(hub.weekend_sessions));
  const [driver, setDriver] = useState<string | null>(null);
  const [drivers, setDrivers] = useState(MOCK_DRIVERS_2025);
  const [analysisPending, setAnalysisPending] = useState(false);
  const autoStarted = useRef(false);

  const year = hub.next.year;
  const round = hub.next.round_number;

  useEffect(() => {
    setPicked((cur) => {
      const next = hub.weekend_sessions;
      if (!next.length) return null;
      if (cur) {
        const match = next.find((s) => s.session_type === cur.session_type);
        if (match) return match;
      }
      return pickDefaultHubSession(next);
    });
  }, [hub.weekend_sessions]);

  useEffect(() => {
    let cancelled = false;
    getDrivers(year).then((d) => {
      if (!cancelled && d.length) setDrivers(d);
    });
    return () => {
      cancelled = true;
    };
  }, [year]);

  useEffect(() => {
    if (!driver) return;
    setARISDriver(driver);
    setFocusDriver(driver);
  }, [driver, setARISDriver, setFocusDriver]);

  useEffect(() => {
    setARISOn(false);
  }, [setARISOn]);

  useEffect(() => {
    if (picked && !isArisCapableSession(picked.session_type) && arisEnabled) {
      setARISOn(false);
    }
  }, [picked, arisEnabled, setARISOn]);

  const commitLive = useCallback(
    (withARIS: boolean) => {
      if (!picked) return;
      const stype = asSessionType(picked.session_type);
      const total = hub.circuit.total_laps ?? hub.live.total_laps ?? 72;
      setARISOn(withARIS);
      setSession({
        year,
        round,
        sessionType: stype as SessionType,
        circuitName: hub.circuit.circuit_name || hub.next.circuit_name,
        countryFlag: hub.circuit.country_flag,
        totalLaps: total,
        date: picked.datetime_utc ?? hub.next.date_race ?? new Date().toISOString(),
        driverCode: driver ?? "VER",
      });
      setTotalLaps(total);
      setGridDrivers(drivers);
      setARISDriver(driver);
      setFocusDriver(driver);
      useRaceStore.getState().setARISModeLocked(withARIS);
      onLoaded();
    },
    [
      picked,
      hub,
      year,
      round,
      driver,
      drivers,
      setARISOn,
      setSession,
      setTotalLaps,
      setGridDrivers,
      setARISDriver,
      setFocusDriver,
      onLoaded,
    ],
  );

  useEffect(() => {
    if (autoStarted.current || !picked) return;
    if (!shouldAutoStartLiveSession(hub)) return;
    autoStarted.current = true;
    commitLive(false);
  }, [hub, picked, commitLive]);

  function continueFromWeekend() {
    if (!picked) return;
    const arisOnRace = arisEnabled && isArisCapableSession(picked.session_type);
    if (arisOnRace) {
      setARISOn(true);
      setStep(nextSelectorStep("circuit", "aris", { arisEnabled: true }));
      return;
    }
    commitLive(false);
  }

  async function fetchStrategies() {
    if (!driver) return;
    setDriverLocked(true);
    setARISDriver(driver);
    setAnalysisPending(true);
    setStep("strategies");
    const payload = await getQuickAnalysis(year, round, driver);
    const plans = payload?.plans ?? [];
    setStrategies(plans);
    setSelectedStrategy(null);
    setAnalysisPending(false);
  }

  const back = () => {
    setStep(nextSelectorStep(step, "back", { arisEnabled }));
  };

  const startEnabled = canStartRace({
    arisEnabled: true,
    selectedDriver: driver,
    strategies,
    selectedStrategy,
  });

  const summary = useMemo(() => {
    return [
      String(year),
      `${hub.circuit.country_flag} ${hub.circuit.circuit_name}`,
      picked ? sessionLabel(picked.session_type) : null,
      arisEnabled ? "ARIS" : "Data",
    ]
      .filter(Boolean)
      .join("  ·  ");
  }, [year, hub.circuit.country_flag, hub.circuit.circuit_name, picked, arisEnabled]);

  return (
    <main className="replay-surface relative flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-mono-data text-[10px] uppercase tracking-[0.28em] text-muted">Live setup</h1>
            {summary && <p className="mt-1 font-mono-data text-[12px] text-white">{summary}</p>}
          </div>
          {step !== "circuit" && (
            <button
              type="button"
              onClick={back}
              className="font-mono-data text-[11px] uppercase tracking-widest text-muted hover:text-red"
            >
              ← Back
            </button>
          )}
        </div>

        <ol className="flex flex-wrap gap-2 font-mono-data text-[9px] uppercase tracking-widest text-muted">
          {(
            [
              ["circuit", "01 Weekend & session"],
              ["driver", "02 Driver"],
              ["strategies", "03 Strategies"],
            ] as const
          ).map(([id, label]) => {
            const skipped = (id === "driver" || id === "strategies") && !arisEnabled && step === "circuit";
            const active = step === id;
            const done =
              (id === "circuit" && step !== "circuit") ||
              (id === "driver" && step === "strategies");
            return (
              <li
                key={id}
                className={`rounded px-2 py-1 ${
                  skipped
                    ? "text-muted-2"
                    : active
                      ? "bg-red/15 text-red"
                      : done
                        ? "text-white"
                        : ""
                }`}
              >
                {label}
              </li>
            );
          })}
        </ol>

        {step === "circuit" && (
          <LiveSessionPicker
            hub={hub}
            selected={picked}
            arisEnabled={arisEnabled}
            onArisChange={setARISOn}
            onSelect={(s) => {
              setPicked(s);
              if (!isArisCapableSession(s.session_type)) setARISOn(false);
              setStrategies(null);
              setSelectedStrategy(null);
              setDriverLocked(false);
            }}
            onContinue={continueFromWeekend}
            onEnterDemo={onEnterDemo}
          />
        )}

        {step === "driver" && (
          <div className="replay-panel rounded-[8px] border border-border p-5">
            <ARISConfigPanel
              phase="driver"
              arisMode={arisMode}
              drivers={drivers}
              selectedDriver={driver}
              plans={strategies ?? []}
              selectedPlanId={selectedStrategy?.id ?? null}
              analysisPending={analysisPending}
              onArisMode={setARISMode}
              onDriver={(code) => {
                setDriver(code);
                setSelectedDriver(code);
              }}
              onGetStrategies={() => void fetchStrategies()}
              onPlan={(id) => {
                const hit = (strategies ?? []).find((p) => p.id === id) ?? null;
                setSelectedStrategy(hit);
              }}
            />
          </div>
        )}

        {step === "strategies" && (
          <div className="replay-panel rounded-[8px] border border-border p-5">
            <ARISConfigPanel
              phase="strategies"
              arisMode={arisMode}
              drivers={drivers}
              selectedDriver={driver}
              plans={strategies ?? []}
              selectedPlanId={selectedStrategy?.id ?? null}
              analysisPending={analysisPending}
              onArisMode={setARISMode}
              onDriver={setDriver}
              onGetStrategies={() => void fetchStrategies()}
              onPlan={(id) => {
                const hit = (strategies ?? []).find((p) => p.id === id) ?? null;
                setSelectedStrategy(hit);
              }}
              continueLabel="Go Live"
              onContinue={() => {
                if (!startEnabled) return;
                commitLive(true);
              }}
            />
          </div>
        )}
      </div>
    </main>
  );
}
