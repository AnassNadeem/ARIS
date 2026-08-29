"use client";

import { SEASON_YEARS, type SeasonYear } from "@/lib/seasonYears";

export function YearSelector({
  year,
  onChange,
}: {
  year: SeasonYear | number | null;
  onChange: (year: SeasonYear) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Season year">
      {SEASON_YEARS.map((y) => {
        const on = y === year;
        return (
          <button
            key={y}
            type="button"
            onClick={() => onChange(y)}
            className={`rounded border px-3 py-1.5 font-mono-data text-sm uppercase tracking-wide ${
              on
                ? "border-red bg-red/10 text-red"
                : "border-border bg-obsidian text-muted hover:border-red/40 hover:text-white"
            }`}
          >
            {y}
          </button>
        );
      })}
    </div>
  );
}
