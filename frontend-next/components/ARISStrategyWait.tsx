"use client";

import { useEffect, useState } from "react";

const STEPS = [
  { title: "Read the race", body: "Laps, stints, and compounds for this weekend." },
  { title: "Model the tyres", body: "How this driver degrades versus the cars around them." },
  { title: "Simulate the stops", body: "Undercut and overcut windows, pit loss included." },
  { title: "Rank the plans", body: "Race time, risk, and the two-compound rule." },
];

const STEP_MS = 1700;

export function ARISStrategyWait({ pending }: { pending: boolean }) {
  const [step, setStep] = useState(0);
  const animDone = step >= STEPS.length;

  useEffect(() => {
    if (!pending || animDone) return;
    const id = window.setTimeout(() => setStep((s) => s + 1), STEP_MS);
    return () => window.clearTimeout(id);
  }, [pending, animDone, step]);

  if (!pending) return null;

  return (
    <div className="mx-auto flex w-full max-w-lg flex-col items-center gap-6 py-4 md:max-w-5xl">
      <div className="relative h-16 w-16">
        <span className="absolute inset-0 rounded-full border border-red/30" />
        <span className="absolute inset-1 animate-spin rounded-full border-2 border-transparent border-t-red" />
        <span className="absolute inset-0 flex items-center justify-center font-mono-data text-[10px] text-red">
          ARIS
        </span>
      </div>

      {!animDone && (
        <ol className="flex w-full flex-col gap-2 md:flex-row md:items-stretch md:gap-3">
          {STEPS.map((s, i) => {
            const active = i === step;
            const done = i < step;
            return (
              <li
                key={s.title}
                className={`rounded-[8px] border px-4 py-3 transition-colors md:min-w-0 md:flex-1 ${
                  active
                    ? "border-red bg-red/10 replay-glow-red"
                    : done
                      ? "border-border bg-obsidian text-white"
                      : "border-border/60 bg-obsidian/40 text-muted-2"
                }`}
              >
                <div className="font-mono-data text-[10px] uppercase tracking-widest">
                  {done ? "Done" : active ? "Working" : `0${i + 1}`}
                </div>
                <div className="mt-0.5 text-sm font-semibold text-white">{s.title}</div>
                <p className="mt-0.5 font-mono-data text-[11px] text-muted">{s.body}</p>
              </li>
            );
          })}
        </ol>
      )}

      {animDone && (
        <div className="flex flex-col items-center gap-2 text-center">
          <p className="font-mono-data text-[12px] uppercase tracking-widest text-white">
            Hang on a second
          </p>
          <p className="max-w-sm font-mono-data text-[11px] text-muted">
            Getting the best strategies for this driver…
          </p>
        </div>
      )}
    </div>
  );
}
