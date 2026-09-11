"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { LiveSessionPicker } from "@/components/LiveSessionPicker";
import { LoadingTransition } from "@/components/LoadingTransition";
import { getDrivers, getReplayPackStatus, initReplay } from "@/lib/api";
import {
  asSessionType,
  hubSessionCta,
  liveHubSession,
  pickDefaultHubSession,
  replayPackWaitMs,
  shouldAutoStartLiveSession,
} from "@/lib/liveSetup";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";
import { sessionLabel } from "@/lib/sessionFlow";
import { applyLiveHubSessionWindows } from "@/lib/sessionWindow";
import { useRaceStore } from "@/store/raceStore";
import type { HubSession, LiveHub, SessionType } from "@/lib/types";

export function LiveSetupFlow({
  hub: rawHub,
  autoEnter = false,
  autoSession = null,
  autoDriver = null,
  onLoaded,
}: {
  hub: LiveHub;
  autoEnter?: boolean;
  autoSession?: string | null;
  /** @deprecated Live ARIS is disabled; ignored. */
  autoAris?: boolean;
  autoDriver?: string | null;
  onLoaded: (mode: "live" | "replay") => void;
}) {
  const [now, setNow] = useState(() => Date.now());
  const hub = useMemo(() => applyLiveHubSessionWindows(rawHub, now), [rawHub, now]);

  const setSession = useRaceStore((s) => s.setSession);
  const setARISDriver = useRaceStore((s) => s.setARISDriver);
  const setARISOn = useRaceStore((s) => s.setARISOn);
  const setFocusDriver = useRaceStore((s) => s.setFocusDriver);
  const setTotalLaps = useRaceStore((s) => s.setTotalLaps);
  const setGridDrivers = useRaceStore((s) => s.setGridDrivers);

  const [step, setStep] = useState<"circuit" | "loading">("circuit");
  const [picked, setPicked] = useState<HubSession | null>(() => {
    const weekend = applyLiveHubSessionWindows(rawHub).weekend_sessions;
    if (autoSession) {
      const match = weekend.find((s) => s.session_type.toUpperCase() === autoSession.toUpperCase());
      if (match) return match;
    }
    return pickDefaultHubSession(weekend);
  });
  const [driver, setDriver] = useState<string | null>(autoDriver);
  const [drivers, setDrivers] = useState(MOCK_DRIVERS_2025);
  const [loadReady, setLoadReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const autoStarted = useRef(false);
  const navigated = useRef(false);

  const year = hub.next.year;
  const round = hub.next.round_number;

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    setPicked((cur) => {
      const next = hub.weekend_sessions;
      if (!next.length) return null;
      const live = liveHubSession(hub);
      if (live) return live;
      if (autoSession) {
        const wanted = next.find((s) => s.session_type.toUpperCase() === autoSession.toUpperCase());
        if (wanted) return wanted;
      }
      if (cur) {
        const match = next.find((s) => s.session_type === cur.session_type);
        if (match) return match;
      }
      return pickDefaultHubSession(next);
    });
  }, [hub, autoSession]);

  useEffect(() => {
    let cancelled = false;
    getDrivers(year, round, picked?.session_type).then((d) => {
      if (!cancelled && d.length) setDrivers(d);
    });
    return () => {
      cancelled = true;
    };
  }, [year, round, picked?.session_type]);

  useEffect(() => {
    if (!driver) return;
    setFocusDriver(driver);
  }, [driver, setFocusDriver]);

  // Live ARIS is deferred - always keep strategy off on the live hub.
  // Strat A/B/C start compounds are ARIS-chosen (generate_strat_plans), never
  // copied from the real driver's lap-1 tyre. Do not add a grid-compound
  // overlay here if live ARIS is re-enabled.
  useEffect(() => {
    setARISOn(false);
  }, [setARISOn]);

  const finish = useCallback(
    (mode: "live" | "replay") => {
      if (navigated.current) return;
      navigated.current = true;
      onLoaded(mode);
    },
    [onLoaded],
  );

  const pendingMode = useRef<"live" | "replay">("live");

  const commitSession = useCallback(
    async (session: HubSession | null = picked) => {
      if (!session) return;
      const stype = asSessionType(session.session_type);
      const total = hub.circuit.total_laps ?? hub.live.total_laps ?? 72;
      const code = driver ?? "VER";
      const cta = hubSessionCta(session);
      const mode: "live" | "replay" = cta === "replay" ? "replay" : "live";
      pendingMode.current = mode;
      navigated.current = false;
      setLoadReady(false);
      setLoadError(null);
      setStep("loading");
      setARISOn(false);
      setSession({
        year,
        round,
        sessionType: stype as SessionType,
        circuitName: hub.circuit.circuit_name || hub.next.circuit_name,
        countryFlag: hub.circuit.country_flag,
        totalLaps: total,
        date: session.datetime_utc ?? hub.next.date_race ?? new Date().toISOString(),
        driverCode: code,
      });
      setTotalLaps(total);
      setGridDrivers(drivers);
      setARISDriver(null);
      setFocusDriver(code);
      useRaceStore.getState().setARISModeLocked(false);
      useRaceStore.getState().setConsoleMode(mode);

      if (mode === "live") {
        setLoadReady(true);
        return;
      }

      try {
        const init = await initReplay({
          year,
          round_number: round,
          session_type: stype,
        });
        if (init?.stage) {
          useRaceStore.getState().setPackStatus({
            stage: init.stage,
            progress: init.progress,
            gpsReady: Boolean(init.flags?.gps_ready),
          });
        }
        const key = init?.session_key;
        if (!key) {
          setLoadError("Couldn't start replay. Try another session or retry.");
          return;
        }
        const deadline = Date.now() + replayPackWaitMs(stype);
        while (!navigated.current && Date.now() < deadline) {
          const st = await getReplayPackStatus({
            session_key: key,
            year,
            round_number: round,
            session_type: stype,
          });
          const stage = st?.stage ?? "metadata";
          useRaceStore.getState().setPackStatus({
            stage,
            progress: st?.progress,
            gpsReady: Boolean(st?.flags?.gps_ready ?? st?.gps_ready),
          });
          if (stage === "minimal" || stage === "full" || st?.ready) {
            setLoadReady(true);
            return;
          }
          if (st?.status === "error") {
            setLoadError(st.error || "Couldn't load session data. Try another session or retry.");
            return;
          }
          await new Promise((r) => window.setTimeout(r, 800));
        }
        setLoadError("Session data took too long to load. Retry, or try another session.");
      } catch {
        setLoadError("Couldn't load session data. Try another session or retry.");
      }
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
    ],
  );

  useEffect(() => {
    if (autoStarted.current) return;
    const liveSess = liveHubSession(hub);
    const shouldStart = shouldAutoStartLiveSession(hub, Date.now(), {
      watch: autoEnter,
      session: autoSession,
    });
    if (!shouldStart || !liveSess) return;
    autoStarted.current = true;
    setPicked(liveSess);
    if (autoDriver) setDriver(autoDriver);
    void commitSession(liveSess);
  }, [hub, commitSession, autoEnter, autoSession, autoDriver]);

  function continueFromWeekend() {
    if (!picked) return;
    if (hubSessionCta(picked) === "wait") return;
    void commitSession(picked);
  }

  const summary = useMemo(() => {
    return [
      String(year),
      `${hub.circuit.country_flag} ${hub.circuit.circuit_name}`,
      picked ? sessionLabel(picked.session_type) : null,
      "Live timing",
    ]
      .filter(Boolean)
      .join("  ·  ");
  }, [year, hub.circuit.country_flag, hub.circuit.circuit_name, picked]);

  return (
    <main className="replay-surface relative flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-mono-data text-[10px] uppercase tracking-[0.28em] text-muted">Live setup</h1>
            {summary && <p className="mt-1 font-mono-data text-[12px] text-white">{summary}</p>}
          </div>
        </div>

        {step === "circuit" && (
          <LiveSessionPicker
            hub={hub}
            selected={picked}
            onSelect={(s) => {
              setPicked(s);
            }}
            onContinue={continueFromWeekend}
          />
        )}
      </div>

      {step === "loading" && (
        <LoadingTransition
          ready={loadReady}
          error={loadError}
          circuitName={hub.circuit.circuit_name || hub.next.name}
          sessionLabel={picked ? sessionLabel(picked.session_type) : "Session"}
          onRetry={() => void commitSession(picked)}
          onComplete={() => finish(pendingMode.current)}
        />
      )}
    </main>
  );
}
