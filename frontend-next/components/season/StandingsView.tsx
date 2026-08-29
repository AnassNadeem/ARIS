"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/layout/AppHeader";
import { YearSelector } from "@/components/season/YearSelector";
import { PanelEmpty, PanelSkeleton } from "@/components/ui/PanelStates";
import { getConstructorStandings, getDriverStandings } from "@/lib/api";
import {
  STANDINGS_2026_UNAVAILABLE,
  STANDINGS_YEAR_LIMIT_MSG,
  parseSeasonYear,
  type SeasonYear,
} from "@/lib/seasonYears";
import type { ConstructorStandingsResponse, DriverStandingsResponse } from "@/lib/types";

type Tab = "drivers" | "constructors";

export function StandingsView({ yearParam }: { yearParam?: string }) {
  const router = useRouter();
  const parsed = parseSeasonYear(yearParam, STANDINGS_YEAR_LIMIT_MSG);
  const year = "year" in parsed ? parsed.year : null;
  const [tab, setTab] = useState<Tab>("drivers");
  const [drivers, setDrivers] = useState<DriverStandingsResponse | null>(null);
  const [constructors, setConstructors] = useState<ConstructorStandingsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (year == null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDrivers(null);
    setConstructors(null);
    async function load(y: SeasonYear) {
      const [d, c] = await Promise.all([getDriverStandings(y), getConstructorStandings(y)]);
      if (cancelled) return;
      if (!d.ok) {
        setError(d.message);
        setLoading(false);
        return;
      }
      if (!c.ok) {
        setError(c.message);
        setLoading(false);
        return;
      }
      setDrivers(d.data);
      setConstructors(c.data);
      setLoading(false);
    }
    void load(year);
    return () => {
      cancelled = true;
    };
  }, [year]);

  function selectYear(next: SeasonYear) {
    router.push(`/standings/${next}`);
  }

  return (
    <>
      <AppHeader backHref="/" />
      <main className="flex-1 bg-carbon px-4 py-6 sm:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="font-mono-data text-[10px] uppercase tracking-[0.22em] text-red">Championship</div>
          <h1 className="mt-1 text-2xl font-bold uppercase tracking-wide text-white">Standings</h1>
          <p className="mt-1 font-mono-data text-[11px] text-muted">Driver and constructor tables for 2024–2026.</p>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <YearSelector year={year} onChange={selectYear} />
            {year === 2026 && (
              <span className="font-mono-data text-[11px] uppercase tracking-wide text-red">Season in progress</span>
            )}
          </div>

          {"error" in parsed && (
            <div className="mt-8">
              <PanelEmpty title="Year not available" detail={parsed.error} />
            </div>
          )}

          {year != null && (
            <>
              <div className="mt-6 flex gap-2">
                {(
                  [
                    ["drivers", "Drivers"],
                    ["constructors", "Constructors"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setTab(id)}
                    className={`rounded border px-3 py-1.5 font-mono-data text-xs uppercase tracking-wide ${
                      tab === id
                        ? "border-red bg-red/10 text-red"
                        : "border-border text-muted hover:text-white"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <div className="mt-4 overflow-x-auto rounded-[8px] border border-border bg-obsidian">
                {loading && <PanelSkeleton rows={12} />}
                {!loading && error && <PanelEmpty title="Could not load standings" detail={error} />}
                {!loading && !error && tab === "drivers" && (
                  <DriversTable data={drivers} />
                )}
                {!loading && !error && tab === "constructors" && (
                  <ConstructorsTable data={constructors} />
                )}
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}

function DriversTable({ data }: { data: DriverStandingsResponse | null }) {
  const emptyMsg =
    data?.message ||
    (data?.year === 2026 ? STANDINGS_2026_UNAVAILABLE : "Jolpica has no driver standings for this year yet.");
  if (!data || data.standings.length === 0) {
    return <PanelEmpty title="No standings" detail={emptyMsg} />;
  }
  return (
    <table className="w-full min-w-[720px] border-collapse font-mono-data text-xs">
      <thead>
        <tr className="text-[10px] uppercase tracking-wide text-muted">
          {["Pos", "Driver", "Team", "Points", "Wins", "Podiums", "FL", "DNFs", "Gap"].map((h) => (
            <th key={h} className="px-3 py-3 text-left font-medium">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.standings.map((r) => (
          <tr key={r.driver_code} className="border-t border-border/60">
            <td className="px-3 py-2.5 text-white">{r.position}</td>
            <td className="px-3 py-2.5">
              <span
                className="mr-2 inline-block h-3.5 w-0.5 align-middle"
                style={{ background: r.team_colour || "#888888" }}
              />
              <span className="text-white">{r.full_name}</span>
              <span className="ml-1 text-muted">({r.driver_code})</span>
            </td>
            <td className="px-3 py-2.5 text-muted">{r.team_name}</td>
            <td className="px-3 py-2.5 text-red">{r.points}</td>
            <td className="px-3 py-2.5">{r.wins}</td>
            <td className="px-3 py-2.5">{r.podiums}</td>
            <td className="px-3 py-2.5">{r.fastest_laps}</td>
            <td className="px-3 py-2.5">{r.dnfs}</td>
            <td className="px-3 py-2.5">{r.gap_to_leader}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ConstructorsTable({ data }: { data: ConstructorStandingsResponse | null }) {
  const emptyMsg =
    data?.message ||
    (data?.year === 2026 ? STANDINGS_2026_UNAVAILABLE : "Jolpica has no constructor table for this year yet.");
  if (!data || data.standings.length === 0) {
    return <PanelEmpty title="No constructor standings" detail={emptyMsg} />;
  }
  return (
    <table className="w-full min-w-[640px] border-collapse font-mono-data text-xs">
      <thead>
        <tr className="text-[10px] uppercase tracking-wide text-muted">
          {["Pos", "Team", "Points", "Wins", "Podiums", "Gap", "Drivers"].map((h) => (
            <th key={h} className="px-3 py-3 text-left font-medium">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.standings.map((r) => (
          <tr key={r.team_name} className="border-t border-border/60">
            <td className="px-3 py-2.5 text-white">{r.position}</td>
            <td className="px-3 py-2.5">
              <span
                className="mr-2 inline-block h-3.5 w-0.5 align-middle"
                style={{ background: r.team_colour || "#888888" }}
              />
              <span className="text-white">{r.team_name}</span>
            </td>
            <td className="px-3 py-2.5 text-red">{r.points}</td>
            <td className="px-3 py-2.5">{r.wins}</td>
            <td className="px-3 py-2.5">{r.podiums}</td>
            <td className="px-3 py-2.5">{r.gap_to_leader}</td>
            <td className="px-3 py-2.5 text-muted">{r.drivers.join(" / ") || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
