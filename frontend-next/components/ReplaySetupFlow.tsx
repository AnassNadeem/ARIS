"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ARISConfigPanel } from "@/components/ARISConfigPanel";
import { LoadingTransition } from "@/components/LoadingTransition";
import { ReplaySelector } from "@/components/ReplaySelector";
import {
  getCalendar,
  getCircuitCoords,
  getDrivers,
  getQuickAnalysis,
  getReplayPackStatus,
  initReplay,
  circuitCoordsFromReplayOutline,
  prewarmSession,
} from "@/lib/api";
import {
  fetchGhost,
  fetchRaceField,
  fieldToDrivers,
  fieldToLapRows,
  fieldToStintRows,
  ghostTicksMap,
  r2Configured,
  raceFieldExists,
  r2FetchErrorMessage,
  GhostUnavailableError,
  R2_LOAD_ERROR,
} from "@/lib/r2Replay";
import { isFullCircuitOutline, shouldApplyFallbackOutline } from "@/lib/circuitCache";
import {
  defaultReplayYear,
  filterReplayRounds,
  isAllowedReplayYear,
  keepRoundsWithPack,
} from "@/lib/replayFilter";
import { canStartRace, nextSelectorStep, sessionLabel, type ReplayMode, type SelectorStep } from "@/lib/sessionFlow";
import { useRaceStore } from "@/store/raceStore";
import type { DriverListing, RoundCard } from "@/lib/types";

const RACE_SESSION = "R" as const;

export function ReplaySetupFlow({ onLoaded }: { onLoaded: () => void }) {
  const search = useSearchParams();
  const urlYearRaw = search.get("year");
  const urlYear = urlYearRaw != null && urlYearRaw !== "" ? Number(urlYearRaw) : null;
  const yearBlocked = urlYear != null && Number.isFinite(urlYear) && !isAllowedReplayYear(urlYear);
  const urlRound = Number(search.get("round"));

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

  const [step, setStep] = useState<SelectorStep>("circuit");
  const [year, setYear] = useState(() =>
    urlYear != null && isAllowedReplayYear(urlYear) ? urlYear : defaultReplayYear(),
  );
  const [rounds, setRounds] = useState<RoundCard[]>([]);
  const [roundsLoading, setRoundsLoading] = useState(true);
  const [round, setRound] = useState<RoundCard | null>(null);
  const [mode, setMode] = useState<ReplayMode | null>(null);
  const [driver, setDriver] = useState<string | null>(null);
  const [drivers, setDrivers] = useState<DriverListing[]>([]);
  const [driversLoading, setDriversLoading] = useState(false);
  const [analysisPending, setAnalysisPending] = useState(false);
  const [loadReady, setLoadReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const navigated = useRef(false);

  function storeReplayOutline(src: Parameters<typeof circuitCoordsFromReplayOutline>[0]) {
    const coords = circuitCoordsFromReplayOutline(src);
    if (!coords || !isFullCircuitOutline(coords)) return;
    const cur = useRaceStore.getState().circuitOutline;
    if (cur && cur.x.length >= coords.x.length) return;
    useRaceStore.getState().setCircuitOutline({ ...coords, available: true });
  }

  useEffect(() => {
    let cancelled = false;
    setDrivers([]);
    setDriver(null);
    getCalendar(year, { replay: true }).then(async (r) => {
      if (cancelled) return;
      let playable = filterReplayRounds(r, { year });
      if (r2Configured()) {
        const exists = new Map<number, boolean | null>();
        await Promise.all(
          playable.map(async (card) => {
            exists.set(card.round, await raceFieldExists(year, card.round));
          }),
        );
        if (cancelled) return;
        playable = keepRoundsWithPack(playable, exists);
      }
      setRounds(playable);
      const fromUrl =
        Number.isFinite(urlRound) && urlRound > 0
          ? playable.find((x) => x.round === urlRound)
          : undefined;
      const preferred =
        fromUrl ?? playable[0] ?? null;
      setRound(preferred);
      setStep("circuit");
      setStrategies(null);
      setSelectedStrategy(null);
      setDriverLocked(false);
      setRoundsLoading(false);
    });
    if (!r2Configured()) {
      getDrivers(year).then((d) => {
        if (cancelled) return;
        setDrivers(d);
      });
    }
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year]);

  useEffect(() => {
    if (!round || !r2Configured()) return;
    let cancelled = false;
    setDriversLoading(true);
    fetchRaceField(year, round.round)
      .then((field) => {
        if (cancelled) return;
        const list = fieldToDrivers(field);
        setDrivers(list);
        setDriversLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setDrivers([]);
        setDriversLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [year, round]);

  useEffect(() => {
    if (!driver) return;
    setARISDriver(driver);
    setFocusDriver(driver);
  }, [driver, setARISDriver, setFocusDriver]);

  useEffect(() => {
    if (!round || r2Configured()) return;
    void prewarmSession({ year, round_number: round.round, session_type: RACE_SESSION });
  }, [year, round]);

  const commitSession = useCallback(
    async (withARIS: boolean) => {
      if (!round) return;
      navigated.current = false;
      setLoadReady(false);
      setLoadError(null);
      setStep("loading");
      setARISOn(withARIS);
      setMode(withARIS ? "aris" : "data");
      const store = useRaceStore.getState();
      const plan = store.selectedStrategy;
      if (plan) store.setActiveStrategy(plan);

      try {
        if (r2Configured()) {
          store.setWaiting(true, "Loading race from R2…");
          const field = await fetchRaceField(year, round.round, (loaded, total) => {
            const pct = total ? loaded / total : Math.min(0.9, loaded / 2_000_000);
            useRaceStore.getState().setPackStatus({ stage: "minimal", progress: pct, gpsReady: false });
          });
          store.setR2RaceField(field);
          store.setReplaySource("r2");
          const total = field.meta.total_laps || round.totalLaps || 72;
          setSession({
            year,
            round: round.round,
            sessionType: RACE_SESSION,
            circuitName: field.meta.circuit_name || round.circuitName,
            countryFlag: round.countryFlag,
            totalLaps: total,
            date: field.meta.date_race || round.date,
            driverCode: driver ?? "VER",
          });
          setTotalLaps(total);
          store.setGridDrivers(fieldToDrivers(field).length ? fieldToDrivers(field) : drivers);
          store.setLapRows(fieldToLapRows(field));
          store.setStintRows(fieldToStintRows(field));
          if (field.outline?.x?.length && shouldApplyFallbackOutline(store.circuitOutline)) {
            store.setCircuitOutline({ x: field.outline.x, y: field.outline.y, available: true });
          }
          store.setPackStatus({ stage: "full", progress: 1, gpsReady: true });
          setARISDriver(driver);
          setFocusDriver(driver);
          store.setARISModeLocked(withARIS);
          if (driver && withARIS) {
            try {
              const ghost = await fetchGhost(year, round.round, driver);
              if (ghost) {
                store.setR2Ghost(ghost);
                store.setGhostTicks(ghostTicksMap(ghost));
                store.setGhostReason(null);
              }
            } catch (ghostErr) {
              if (ghostErr instanceof GhostUnavailableError) {
                store.setR2Ghost(null);
                store.setGhostTicks({});
                store.setGhostReason(ghostErr.code);
              } else {
                throw ghostErr;
              }
            }
          }
          setLoadReady(true);
          return;
        }
      } catch (err) {
        console.warn("[ReplaySetupFlow] R2 fetch failed", err);
        useRaceStore.getState().setReplaySource("heroku");
        if (r2Configured()) {
          const msg = r2FetchErrorMessage(err);
          setLoadError(msg);
          useRaceStore.getState().setWaiting(true, msg);
          return;
        }
      }

      void prewarmSession({
        year,
        round_number: round.round,
        session_type: RACE_SESSION,
        driver_code: driver ?? undefined,
      });
      void getCircuitCoords(year, round.round);

      try {
        const init = await initReplay({
          year,
          round_number: round.round,
          session_type: RACE_SESSION,
        });
        const total = init?.total_laps || round.totalLaps || 72;
        setSession({
          year,
          round: round.round,
          sessionType: RACE_SESSION,
          circuitName: init?.circuit || round.circuitName,
          countryFlag: round.countryFlag,
          totalLaps: total,
          date: round.date,
          driverCode: driver ?? "VER",
        });
        setTotalLaps(total);
        useRaceStore.getState().setGridDrivers(drivers);
        setARISDriver(driver);
        setFocusDriver(driver);
        useRaceStore.getState().setARISModeLocked(withARIS);
        if (init?.stage) {
          useRaceStore.getState().setPackStatus({
            stage: init.stage,
            progress: init.progress,
            gpsReady: Boolean(init.flags?.gps_ready),
          });
        }
        storeReplayOutline(init);

        const key = init?.session_key;
        if (key) {
          const deadline = Date.now() + 20_000;
          while (!navigated.current && Date.now() < deadline) {
            const needOutline = !useRaceStore.getState().circuitOutline?.x?.length;
            const st = await getReplayPackStatus({
              session_key: key,
              year,
              round_number: round.round,
              session_type: RACE_SESSION,
              outline: needOutline,
            });
            const stage = st?.stage ?? "metadata";
            useRaceStore.getState().setPackStatus({
              stage,
              progress: st?.progress,
              gpsReady: Boolean(st?.flags?.gps_ready ?? st?.gps_ready),
            });
            storeReplayOutline(st);
            if (stage === "minimal" || stage === "full" || st?.ready) {
              setLoadReady(true);
              return;
            }
            if (st?.status === "error") break;
            await new Promise((r) => window.setTimeout(r, 800));
          }
        }
        setLoadError(R2_LOAD_ERROR);
        useRaceStore.getState().setWaiting(true, R2_LOAD_ERROR);
      } catch (err) {
        console.warn("[ReplaySetupFlow] pack-status failed", err);
        setLoadError(R2_LOAD_ERROR);
        useRaceStore.getState().setWaiting(true, R2_LOAD_ERROR);
      }
    },
    [
      round,
      year,
      driver,
      drivers,
      setARISOn,
      setSession,
      setTotalLaps,
      setARISDriver,
      setFocusDriver,
    ],
  );

  function pickCircuit(r: RoundCard) {
    setRound(r);
    setStrategies(null);
    setSelectedStrategy(null);
    setDriverLocked(false);
  }

  function continueFromCircuit() {
    if (!round) return;
    if (arisEnabled) {
      setMode("aris");
      setARISOn(true);
      setStep(nextSelectorStep("circuit", "aris", { arisEnabled: true }));
      return;
    }
    void commitSession(false);
  }

  async function fetchStrategies() {
    if (!round || !driver) return;
    setDriverLocked(true);
    setARISDriver(driver);
    setAnalysisPending(true);
    setStep("strategies");
    const payload = await getQuickAnalysis(year, round.round, driver);
    const plans = payload?.plans ?? [];
    setStrategies(plans);
    setSelectedStrategy(null);
    setAnalysisPending(false);
  }

  const back = () => {
    if (step === "loading") return;
    setStep(nextSelectorStep(step, "back", { arisEnabled }));
  };

  const finish = useCallback(() => {
    if (navigated.current) return;
    navigated.current = true;
    onLoaded();
  }, [onLoaded]);

  const viewStep: SelectorStep = step === "loading" ? (mode === "aris" ? (strategies?.length ? "strategies" : "driver") : "circuit") : step;

  const startEnabled = canStartRace({
    arisEnabled: true,
    selectedDriver: driver,
    strategies,
    selectedStrategy,
  });

  const summary = useMemo(() => {
    if (!round) return null;
    return [
      String(year),
      `${round.countryFlag} ${round.circuitName}`,
      "Race",
      arisEnabled || mode === "aris" ? "ARIS" : "Data",
    ]
      .filter(Boolean)
      .join("  ·  ");
  }, [year, round, step, mode, arisEnabled]);

  return (
    <main className="replay-surface relative flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-mono-data text-[10px] uppercase tracking-[0.28em] text-muted">Replay setup</h1>
            {summary && <p className="mt-1 font-mono-data text-[12px] text-white">{summary}</p>}
          </div>
          {viewStep !== "circuit" && step !== "loading" && (
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
              ["circuit", "01 Year & Race"],
              ["driver", "02 Driver"],
              ["strategies", "03 Strategies"],
              ["loading", "04 Load"],
            ] as const
          ).map(([id, label]) => {
            const skipped =
              (id === "driver" || id === "strategies") && step === "loading" && mode === "data";
            const active = step === id;
            const done =
              (id === "circuit" && step !== "circuit") ||
              (id === "driver" && (step === "strategies" || (step === "loading" && mode === "aris"))) ||
              (id === "strategies" && step === "loading" && mode === "aris");
            return (
              <li
                key={id}
                className={`rounded px-2 py-1 ${
                  skipped
                    ? "text-muted-2 line-through"
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

        {viewStep === "circuit" && (
          <ReplaySelector
            year={year}
            rounds={rounds}
            selected={round}
            selectedSession={RACE_SESSION}
            loading={roundsLoading}
            yearBlocked={yearBlocked}
            arisEnabled={arisEnabled}
            onYearChange={(y) => {
              setYear(y);
              setRoundsLoading(true);
            }}
            onArisChange={setARISOn}
            onSelect={pickCircuit}
            onContinue={continueFromCircuit}
          />
        )}

        {viewStep === "driver" && (
          <div className="replay-panel rounded-[8px] border border-border p-5">
            {driversLoading && drivers.length === 0 ? (
              <p className="font-mono-data text-[11px] text-muted">Loading this race&apos;s driver grid…</p>
            ) : drivers.length === 0 ? (
              <p className="font-mono-data text-[11px] text-muted">
                No driver grid in race_field.json for this race.
              </p>
            ) : (
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
            )}
          </div>
        )}

        {viewStep === "strategies" && (
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
              onContinue={() => {
                if (!startEnabled) return;
                void commitSession(true);
              }}
            />
          </div>
        )}
      </div>

      {step === "loading" && (
        <LoadingTransition
          ready={loadReady}
          error={loadError}
          circuitName={round?.circuitName ?? "Race"}
          sessionLabel={sessionLabel(RACE_SESSION)}
          onRetry={() => void commitSession(mode === "aris")}
          onComplete={finish}
        />
      )}
    </main>
  );
}
