import { useState } from "react";
import type { CalendarRound, Driver, DriverStandings } from "../api/types";
import { useCalendar } from "../hooks/useCalendar";
import { useDrivers } from "../hooks/useDrivers";
import { useStandings } from "../hooks/useStandings";
import { C, T } from "../theme";
import { Chip, EmptyState, ErrorPanel, SectionLabel, SkeletonPanel, initials } from "../components/atoms";
import { Shell } from "../components/Shell";

export function SetupView({
  year,
  onYear,
  onProceed,
  initialRound,
}: {
  year: number;
  onYear: (y: number) => void;
  onProceed: (cfg: { mode: "replay" | "live"; year: number; round: CalendarRound; driver: string }) => void;
  initialRound?: CalendarRound | null;
}) {
  const [race, setRace] = useState<CalendarRound | null>(initialRound ?? null);
  const [driver, setDriver] = useState<string | null>(null);
  const cal = useCalendar(year);
  const drivers = useDrivers(year);
  const standings = useStandings(year);
  const pts = new Map(
    standings.drivers.status === "ok"
      ? standings.drivers.data.standings.map((s) => [s.driver_code, s])
      : [],
  );

  const rounds = cal.status === "ok" ? cal.data.rounds : [];
  const completed = rounds.filter((r) => r.status === "COMPLETED");
  const upcoming = rounds.filter((r) => r.status !== "COMPLETED");
  const champ =
    standings.drivers.status === "ok"
      ? standings.drivers.data.champion_code || standings.drivers.data.leader_code
      : null;

  const canProceed = !!(race && driver && race.status === "COMPLETED");

  return (
    <Shell title="MISSION SETUP">
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "32px 24px" }}>
        <SectionLabel>01 — SELECT YEAR</SectionLabel>
        <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
          {[2024, 2025, 2026].map((y) => (
            <YearChip
              key={y}
              y={y}
              selected={year === y}
              fallbackCompleted={y === year ? completed.length : null}
              fallbackChamp={y === year ? champ ?? null : null}
              onSelect={() => {
                onYear(y);
                setRace(null);
                setDriver(null);
              }}
            />
          ))}
        </div>
        <SectionLabel>02 — SELECT RACE</SectionLabel>
        {cal.status === "loading" && (
          <SkeletonPanel
            rows={8}
            label="Loading races — this may take a moment on first load as data is being cached..."
          />
        )}
        {cal.status === "error" && <ErrorPanel message={`Could not load races. ${cal.error}`} onRetry={cal.retry} />}
        {cal.status === "ok" && (
          <>
            <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint, marginBottom: 8 }}>COMPLETED</div>
            <RaceGrid rounds={completed} selected={race} onSelect={setRace} />
            {upcoming.length > 0 && (
              <>
                <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint, margin: "16px 0 8px" }}>UPCOMING</div>
                <RaceGrid rounds={upcoming} selected={race} onSelect={setRace} />
              </>
            )}
          </>
        )}

        <SectionLabel>03 — SELECT YOUR DRIVER</SectionLabel>
        {drivers.status === "loading" && (
          <SkeletonPanel
            rows={8}
            label="Loading drivers — this may take a moment on first load as data is being cached..."
          />
        )}
        {drivers.status === "error" && (
          <ErrorPanel message={`Could not load drivers. ${drivers.error}`} onRetry={drivers.retry} />
        )}
        {drivers.status === "ok" && (
          <>
            {drivers.data.estimated_label && <Chip tone="signal">{drivers.data.estimated_label}</Chip>}
            <DriverGrid
              drivers={drivers.data.drivers}
              standings={pts}
              selected={driver}
              onSelect={setDriver}
            />
          </>
        )}

        <button
          disabled={!canProceed}
          onClick={() => {
            if (!race || !driver) return;
            onProceed({ mode: "replay", year, round: race, driver });
          }}
          style={{
            marginTop: 28,
            padding: "13px 28px",
            background: canProceed ? C.signal : C.ghost,
            border: "none",
            borderRadius: 4,
            color: canProceed ? C.ink : C.faint,
            fontFamily: T.display,
            fontSize: 17,
            fontWeight: 800,
            cursor: canProceed ? "pointer" : "not-allowed",
          }}
        >
          BUILD STRATEGY BRIEFING →
        </button>
      </div>
    </Shell>
  );
}

function YearChip({
  y,
  selected,
  onSelect,
  fallbackCompleted,
  fallbackChamp,
}: {
  y: number;
  selected: boolean;
  onSelect: () => void;
  fallbackCompleted: number | null;
  fallbackChamp: string | null;
}) {
  const cal = useCalendar(y);
  const standings = useStandings(y);
  const n = cal.status === "ok" ? cal.data.rounds.filter((r) => r.status === "COMPLETED").length : fallbackCompleted;
  const champ =
    standings.drivers.status === "ok"
      ? standings.drivers.data.champion_code || standings.drivers.data.leader_code
      : fallbackChamp;
  return (
    <button
      onClick={onSelect}
      style={{
        padding: "8px 16px",
        borderRadius: 4,
        cursor: "pointer",
        background: selected ? C.signalMid : "transparent",
        border: `1px solid ${selected ? C.signal : C.border}`,
        color: selected ? C.signal : C.mist,
        fontFamily: T.mono,
        fontSize: 12,
      }}
    >
      {y}
      <div style={{ fontSize: 9, color: C.faint, marginTop: 4 }}>
        {n != null ? `${n} completed` : "…"}
        {champ ? ` · ${champ}` : ""}
      </div>
    </button>
  );
}

function RaceGrid({
  rounds,
  selected,
  onSelect,
}: {
  rounds: CalendarRound[];
  selected: CalendarRound | null;
  onSelect: (r: CalendarRound) => void;
}) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 12 }}>
      {rounds.map((r) => {
        const cancelled = r.status === "CANCELLED";
        const upcoming = r.status === "UPCOMING" || r.status === "LIVE";
        const blocked = cancelled || upcoming;
        return (
          <button
            key={r.round_number}
            disabled={blocked}
            title={cancelled ? r.cancelled_reason || "Cancelled" : upcoming ? "Not yet completed — not replayable" : r.name}
            onClick={() => !blocked && onSelect(r)}
            style={{
              padding: "10px 12px",
              borderRadius: 4,
              textAlign: "left",
              cursor: blocked ? "not-allowed" : "pointer",
              opacity: cancelled ? 0.45 : 1,
              background: selected?.round_number === r.round_number ? C.signalMid : C.panel2,
              border: `1px solid ${selected?.round_number === r.round_number ? C.signal : C.border}`,
            }}
          >
            <div style={{ fontFamily: T.body, fontSize: 13, fontWeight: 600, color: C.paper }}>{r.name}</div>
            <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint, marginTop: 2 }}>
              {r.date_race?.slice(0, 10) ?? ""} · {r.circuit_name}
            </div>
            <div style={{ display: "flex", gap: 4, marginTop: 6, flexWrap: "wrap" }}>
              {r.is_sprint_weekend && <Chip tone="purple" size="xs">SPRINT</Chip>}
              {cancelled && <Chip tone="caution" size="xs">CANCELLED</Chip>}
              {r.status === "LIVE" && <Chip tone="caution" size="xs">LIVE</Chip>}
              {r.status === "UPCOMING" && <Chip tone="mist" size="xs">UPCOMING</Chip>}
            </div>
          </button>
        );
      })}
    </div>
  );
}

function DriverGrid({
  drivers,
  standings,
  selected,
  onSelect,
}: {
  drivers: Driver[];
  standings: Map<string, DriverStandings["standings"][number]>;
  selected: string | null;
  onSelect: (code: string) => void;
}) {
  if (!drivers.length) {
    return <EmptyState title="No drivers" body="Driver data unavailable for this year." />;
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, marginTop: 10 }}>
      {drivers.map((d) => {
        const st = standings.get(d.driver_code);
        return (
          <button
            key={d.driver_code}
            onClick={() => onSelect(d.driver_code)}
            style={{
              padding: "10px 12px",
              borderRadius: 4,
              cursor: "pointer",
              textAlign: "left",
              display: "flex",
              gap: 8,
              alignItems: "center",
              background: selected === d.driver_code ? C.signalMid : C.panel2,
              border: `1px solid ${selected === d.driver_code ? C.signal : C.border}`,
            }}
          >
            <div style={{ width: 3, height: 36, borderRadius: 2, background: d.team_colour || C.mist, flexShrink: 0 }} />
            {d.headshot_url ? (
              <img src={d.headshot_url} alt="" width={28} height={28} style={{ borderRadius: "50%", objectFit: "cover" }} />
            ) : (
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  background: C.raised,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: T.mono,
                  fontSize: 9,
                  color: C.mist,
                }}
              >
                {initials(d.full_name)}
              </div>
            )}
            <div>
              <div style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 700, color: C.paper }}>{d.driver_code}</div>
              <div style={{ fontFamily: T.body, fontSize: 9, color: C.faint }}>{d.team_name}</div>
              {st && (
                <div style={{ fontFamily: T.mono, fontSize: 8, color: C.mist }}>
                  P{st.position} · {st.points} pts
                </div>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
