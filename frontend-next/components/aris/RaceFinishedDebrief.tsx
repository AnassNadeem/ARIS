"use client";

import { useEffect, useMemo } from "react";
import Link from "next/link";
import { explainSessionId } from "@/lib/api";
import { useRaceStore } from "@/store/raceStore";
import { GhostVsRealChart } from "@/components/aris/GhostVsRealChart";
import { buildRaceStory, ghostVsRealFromField, raceFinishSummary } from "@/lib/debriefSummary";

/**
 * Post-race overlay. Stays up until the user leaves the console.
 * Close collapses to a bar with "another race" — it does not dismiss the brief.
 */
export function RaceFinishedDebrief() {
  const session = useRaceStore((s) => s.session);
  const raceFinished = useRaceStore((s) => s.raceFinished);
  const currentLap = useRaceStore((s) => s.currentLap);
  const totalLaps = useRaceStore((s) => s.totalLaps);
  const consolePlayState = useRaceStore((s) => s.consolePlayState);
  const debriefOpen = useRaceStore((s) => s.debriefOpen);
  const setDebriefOpen = useRaceStore((s) => s.setDebriefOpen);
  const arisDriver = useRaceStore((s) => s.arisDriver ?? s.focusDriver ?? session?.driverCode);
  const ghostData = useRaceStore((s) => s.ghostData);
  const ghostCar = useRaceStore((s) => s.ghostCar);
  const ghostTicks = useRaceStore((s) => s.ghostTicksByLap);
  const cars = useRaceStore((s) => s.cars);
  const field = useRaceStore((s) => s.r2RaceField);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const ghostReason = useRaceStore((s) => s.ghostReason);

  const ended =
    raceFinished ||
    (consolePlayState === "racing" && totalLaps > 0 && currentLap >= totalLaps);
  const sid = explainSessionId(session);

  useEffect(() => {
    if (ended) setDebriefOpen(true);
  }, [ended, setDebriefOpen]);

  const finish = useMemo(() => {
    if (!arisDriver) return null;
    return raceFinishSummary({
      driver: arisDriver,
      field,
      cars,
      ghostCar,
      ghostTicks,
    });
  }, [arisDriver, field, cars, ghostCar, ghostTicks]);

  const compare = useMemo(() => {
    if (!arisDriver || !field || !Object.keys(ghostTicks).length) return null;
    return ghostVsRealFromField(field, arisDriver, ghostTicks);
  }, [arisDriver, field, ghostTicks]);

  const story = useMemo(() => {
    if (!arisDriver) return null;
    return buildRaceStory({
      driver: arisDriver,
      field,
      compare,
      ghostData,
      finish,
    });
  }, [arisDriver, field, compare, ghostData, finish]);

  if (!ended && !debriefOpen) return null;

  const collapsed = ended && !debriefOpen;

  return (
    <>
      {collapsed && (
        <div className="pointer-events-auto absolute bottom-4 left-1/2 z-[70] w-[min(40rem,calc(100%-2rem))] -translate-x-1/2 rounded-[10px] border border-border bg-surface-2/95 p-3 shadow-2xl backdrop-blur-sm">
          <div className="flex flex-wrap items-center gap-2">
            <div className="min-w-0 flex-1">
              <div className="font-mono-data text-[10px] uppercase tracking-[0.18em] text-muted">
                Post-race brief
              </div>
              <p className="font-sans text-sm text-white">
                {story?.headline ?? "Race finished."} Pick another race or reopen the debrief.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setDebriefOpen(true)}
              className="rounded bg-red px-3 py-1.5 font-mono-data text-[11px] uppercase text-white"
            >
              View debrief
            </button>
            <Link
              href="/replay"
              className="rounded border border-red bg-red/10 px-3 py-1.5 font-mono-data text-[11px] uppercase text-red hover:bg-red/20"
            >
              Another race
            </Link>
          </div>
        </div>
      )}

      {debriefOpen && (
        <div className="absolute inset-0 z-[80] flex items-center justify-center bg-carbon/70 p-4 backdrop-blur-[2px]">
          <div className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-[12px] border border-border bg-surface-2 shadow-2xl">
            <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border p-4">
              <div>
                <div className="font-mono-data text-[10px] uppercase tracking-[0.2em] text-muted">
                  Post-race debrief
                </div>
                <h2 className="mt-1 text-lg font-bold text-white">
                  {session?.circuitName ?? "Session"} · {session?.year}
                  {arisDriver ? ` · ${arisDriver}` : ""}
                </h2>
                <p className="mt-1 font-mono-data text-[11px] text-muted">
                  {isARISOn && arisDriver ? `ARIS ghost vs ${arisDriver}` : "Replay finished."}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDebriefOpen(false)}
                className="rounded border border-border px-2 py-1 font-mono-data text-[11px] uppercase text-muted hover:text-white"
              >
                Close
              </button>
            </div>

            {isARISOn && ghostReason === "driver_did_not_race" ? (
              <p role="alert" className="px-4 pt-3 font-mono-data text-[11px] text-amber">
                {arisDriver} did not start this race (DNS). ARIS could not compute a ghost car.
              </p>
            ) : isARISOn ? (
              <div className="grid shrink-0 grid-cols-2 gap-3 px-4 pt-3 font-mono-data text-[11px]">
                <div className="rounded border border-border bg-carbon p-3">
                  <div className="text-[9px] uppercase text-muted">ARIS</div>
                  <div className="mt-1 text-white">P{finish?.ghostPos ?? ghostData?.ghost_position ?? "—"}</div>
                  <div className="text-muted">
                    Gap {finish?.ghostGap != null ? `${finish.ghostGap.toFixed(1)}s` : "—"}
                  </div>
                </div>
                <div className="rounded border border-border bg-carbon p-3">
                  <div className="text-[9px] uppercase text-muted">{arisDriver} (real)</div>
                  <div className="mt-1 text-white">P{finish?.realPos ?? "—"}</div>
                  <div className="text-muted">
                    Gap {finish?.realGap != null ? `${finish.realGap.toFixed(1)}s` : "—"}
                  </div>
                </div>
              </div>
            ) : null}

            {story && (
              <div className="shrink-0 space-y-1.5 px-4 pt-3">
                <p className="font-sans text-sm font-semibold text-white">{story.headline}</p>
                <ul className="max-h-[28vh] space-y-1 overflow-y-auto font-mono-data text-[11px] leading-relaxed text-white/85">
                  {story.lines.map((line, i) => (
                    <li key={`${i}-${line.slice(0, 24)}`}>{line}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              <div className="h-[280px] overflow-hidden rounded border border-border">
                <GhostVsRealChart sessionId={sid} driver={arisDriver ?? undefined} lockDriver />
              </div>
            </div>

            <div className="flex shrink-0 flex-wrap gap-2 border-t border-border p-3">
              <Link
                href="/replay"
                className="rounded border border-red bg-red/10 px-3 py-1.5 font-mono-data text-[11px] uppercase text-red hover:bg-red/20"
              >
                Another race
              </Link>
              <button
                type="button"
                onClick={() => setDebriefOpen(false)}
                className="rounded border border-border px-3 py-1.5 font-mono-data text-[11px] uppercase text-muted hover:text-white"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
