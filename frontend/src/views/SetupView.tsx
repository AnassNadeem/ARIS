import { useEffect, useMemo, useState } from "react";
import type { CalendarRound, ReplayWatchPick } from "../api/types";
import { apiGet, apiPost, warmReplaySession } from "../api/client";
import { useCalendar } from "../hooks/useCalendar";
import { useRoundSessions } from "../hooks/useRoundSessions";
import { C, T } from "../theme";
import { Chip, ErrorPanel, SkeletonPanel } from "../components/atoms";
import { Shell } from "../components/Shell";
import { replayYears } from "../years";

const SESSION_ORDER = ["FP1", "FP2", "FP3", "SQ", "S", "Q", "R"] as const;

const SESSION_LABEL: Record<string, string> = {
  FP1: "Practice 1",
  FP2: "Practice 2",
  FP3: "Practice 3",
  SQ: "Sprint Qualifying",
  S: "Sprint",
  Q: "Qualifying",
  R: "Race",
};

function cancelledRound(year: number, r: CalendarRound): boolean {
  if (r.status === "CANCELLED") return true;
  const name = `${r.name} ${r.country} ${r.city}`.toLowerCase();
  return year === 2026 && (name.includes("bahrain") || name.includes("saudi"));
}

function formatDay(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function formatWhen(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function weekendDate(r: CalendarRound): string {
  return formatDay(r.date_race || r.date_quali || r.date_sprint || r.date_fp1);
}

export function SetupView({
  year,
  onYear,
  onWatch,
  initialRound,
}: {
  year: number;
  onYear: (y: number) => void;
  onWatch: (pick: ReplayWatchPick) => void;
  initialRound?: CalendarRound | null;
}) {
  const [race, setRace] = useState<CalendarRound | null>(initialRound ?? null);
  const [sessionType, setSessionType] = useState("R");
  const [ingest, setIngest] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "ready" | "sprint">("all");
  const cal = useCalendar(year);
  const sessions = useRoundSessions(year, race && !cancelledRound(year, race) ? race.round_number : null);

  const rounds = cal.status === "ok" ? cal.data.rounds : [];
  const blocked = Boolean(race && cancelledRound(year, race));
  const sessionList = SESSION_ORDER.map((code) =>
    (sessions.status === "ok" ? sessions.data.sessions : []).find((s) => s.session_type === code),
  ).filter((s): s is NonNullable<typeof s> => Boolean(s));
  const selectedSession = sessionList.find((s) => s.session_type === sessionType) ?? sessionList[0] ?? null;
  const playable = Boolean(
    race && !blocked && selectedSession && (selectedSession.status === "COMPLETED" || selectedSession.status === "LIVE"),
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rounds.filter((r) => {
      if (filter === "ready" && r.status !== "COMPLETED" && r.status !== "LIVE") return false;
      if (filter === "sprint" && !r.is_sprint_weekend) return false;
      if (!q) return true;
      const blob = `${r.name} ${r.circuit_name} ${r.country} ${r.city} R${r.round_number}`.toLowerCase();
      return blob.includes(q);
    });
  }, [rounds, query, filter]);

  useEffect(() => {
    if (cal.status !== "ok") return;
    const fromInitial = initialRound
      ? rounds.find((r) => r.round_number === initialRound.round_number)
      : null;
    if (fromInitial && !cancelledRound(year, fromInitial)) {
      setRace(fromInitial);
      return;
    }
    const pick =
      rounds.find((r) => r.status === "LIVE" && !cancelledRound(year, r)) ??
      [...rounds].reverse().find((r) => r.status === "COMPLETED" && !cancelledRound(year, r)) ??
      null;
    setRace(pick);
  }, [year, cal.status, initialRound?.round_number]);

  useEffect(() => {
    if (!race || cancelledRound(year, race)) {
      setSessionType("R");
      setIngest(null);
    }
  }, [year, race]);

  useEffect(() => {
    if (sessionList.length && !sessionList.some((s) => s.session_type === sessionType)) {
      setSessionType(sessionList[0].session_type);
    }
  }, [sessionList, sessionType]);

  const warm = async (stype: string) => {
    if (!race) return;
    try {
      await warmReplaySession(year, race.round_number, stype);
    } catch {
      return;
    }
  };

  useEffect(() => {
    if (cal.status !== "ok" || !race) return;
    const completed = sessionList.filter((s) => s.status === "COMPLETED");
    let cancelled = false;
    const run = async () => {
      for (const sess of completed) {
        if (cancelled) return;
        await warm(sess.session_type);
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [cal.status, year, race?.round_number, sessions.status]);

  const runIngest = async () => {
    if (!race || !selectedSession) return;
    setIngest("INGESTING");
    try {
      const res = await apiPost<{ status: string }>(
        `/api/session/${year}/${race.round_number}/${selectedSession.session_type}/ingest`,
        {},
        { timeout: 20_000 },
      );
      setIngest(res.status);
      void warm(selectedSession.session_type);
      if (res.status === "INGESTING") {
        const started = Date.now();
        const poll = window.setInterval(() => {
          apiGet<{ status: string }>(
            `/api/session/${year}/${race.round_number}/${selectedSession.session_type}/ingest`,
            { timeout: 15_000, cache: false },
          )
            .then((d) => {
              setIngest(d.status);
              if (d.status !== "INGESTING" || Date.now() - started > 180_000) window.clearInterval(poll);
            })
            .catch(() => window.clearInterval(poll));
        }, 2500);
      }
    } catch {
      setIngest("UNAVAILABLE");
      void warm(selectedSession.session_type);
    }
  };

  const watch = () => {
    if (!race || !selectedSession) return;
    if (!ingest) void runIngest();
    onWatch({ year, round: race, sessionType: selectedSession.session_type });
  };

  return (
    <Shell title="REPLAY">
      <style>{`@media (max-width: 840px) { .replay-picker { grid-template-columns: 1fr !important; } }`}</style>
      <div style={{ height: "100%", display: "flex", flexDirection: "column", minHeight: 0 }}>
        <div style={{ padding: "22px 28px 0", maxWidth: 1280, margin: "0 auto", width: "100%" }}>
          <div style={{ fontFamily: T.display, fontWeight: 800, fontSize: 28, letterSpacing: "0.04em" }}>
            SESSION REPLAY
          </div>
          <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist, marginTop: 4, marginBottom: 16 }}>
            Pick a weekend, then a session — completed races play from FastF1 telemetry
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 14 }}>
            {replayYears().map((y) => {
              const on = y === year;
              return (
                <button
                  key={y}
                  onClick={() => {
                    onYear(y);
                    setRace(null);
                    setIngest(null);
                    setQuery("");
                  }}
                  style={{
                    padding: "6px 12px",
                    cursor: "pointer",
                    background: on ? C.signalMid : C.raised,
                    border: `1px solid ${on ? C.signal : C.border}`,
                    color: on ? C.signal : C.mist,
                    fontFamily: T.mono,
                    fontSize: 12,
                    borderRadius: 4,
                    fontWeight: on ? 700 : 500,
                  }}
                >
                  {y}
                </button>
              );
            })}
          </div>
        </div>

        <div
          style={{
            flex: 1,
            minHeight: 0,
            display: "grid",
            gridTemplateColumns: "minmax(280px, 380px) 1fr",
            gap: 0,
            maxWidth: 1280,
            margin: "0 auto",
            width: "100%",
            borderTop: `1px solid ${C.border}`,
          }}
          className="replay-picker"
        >
          <div
            style={{
              borderRight: `1px solid ${C.border}`,
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
              background: C.panel,
            }}
          >
            <div style={{ padding: "12px 14px", borderBottom: `1px solid ${C.border}` }}>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search circuit, country, GP…"
                style={{
                  width: "100%",
                  background: C.raised,
                  color: C.paper,
                  border: `1px solid ${C.border}`,
                  fontFamily: T.mono,
                  fontSize: 12,
                  padding: "8px 10px",
                  borderRadius: 4,
                  outline: "none",
                }}
              />
              <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                {(
                  [
                    ["ready", "READY"],
                    ["all", "ALL"],
                    ["sprint", "SPRINT"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    onClick={() => setFilter(id)}
                    style={{
                      padding: "4px 8px",
                      cursor: "pointer",
                      background: filter === id ? C.signalMid : "transparent",
                      border: `1px solid ${filter === id ? C.signal : C.border}`,
                      color: filter === id ? C.signal : C.mist,
                      fontFamily: T.mono,
                      fontSize: 9,
                      letterSpacing: "0.08em",
                      borderRadius: 3,
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ flex: 1, overflow: "auto" }}>
              {cal.status === "loading" && <SkeletonPanel rows={8} label="Loading weekends…" />}
              {cal.status === "error" && (
                <ErrorPanel
                  message={
                    /502|503/.test(cal.error || "")
                      ? "Calendar is warming up. Retry in a moment."
                      : `Could not load weekends. ${cal.error}`
                  }
                  onRetry={cal.retry}
                />
              )}
              {cal.status === "ok" &&
                visible.map((r) => {
                  const dead = cancelledRound(year, r);
                  const on = race?.round_number === r.round_number;
                  return (
                    <button
                      key={r.round_number}
                      disabled={dead}
                      onClick={() => {
                        setRace(r);
                        setIngest(null);
                      }}
                      style={{
                        display: "block",
                        width: "100%",
                        textAlign: "left",
                        padding: "12px 14px",
                        cursor: dead ? "not-allowed" : "pointer",
                        background: on ? C.signalMid : "transparent",
                        border: "none",
                        borderBottom: `1px solid ${C.border}`,
                        borderLeft: on ? `3px solid ${C.signal}` : "3px solid transparent",
                        color: dead ? C.faint : C.paper,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                        <span style={{ fontFamily: T.mono, fontSize: 10, color: on ? C.signal : C.faint }}>
                          R{r.round_number}
                          {r.is_sprint_weekend ? " · SPRINT" : ""}
                        </span>
                        <span style={{ fontFamily: T.mono, fontSize: 10, color: C.faint }}>{weekendDate(r)}</span>
                      </div>
                      <div style={{ fontFamily: T.display, fontWeight: 800, fontSize: 18, marginTop: 2, lineHeight: 1.1 }}>
                        {r.name}
                      </div>
                      <div style={{ fontFamily: T.mono, fontSize: 10, color: C.mist, marginTop: 4 }}>
                        {r.circuit_name}
                        {r.city ? ` · ${r.city}` : ""}
                      </div>
                      <div style={{ marginTop: 6 }}>
                        {dead ? (
                          <Chip tone="caution" size="xs">
                            CANCELLED
                          </Chip>
                        ) : (
                          <Chip
                            tone={r.status === "LIVE" ? "caution" : r.status === "COMPLETED" ? "green" : "mist"}
                            size="xs"
                          >
                            {r.status}
                          </Chip>
                        )}
                      </div>
                    </button>
                  );
                })}
              {cal.status === "ok" && visible.length === 0 && (
                <div style={{ padding: 16, fontFamily: T.mono, fontSize: 11, color: C.faint }}>
                  No weekends match this filter.
                </div>
              )}
            </div>
          </div>

          <div style={{ padding: "22px 24px 32px", overflow: "auto", background: C.ink }}>
            {!race && (
              <div style={{ fontFamily: T.mono, fontSize: 12, color: C.mist, marginTop: 24 }}>
                Select a weekend from the list.
              </div>
            )}
            {race && (
              <>
                <div style={{ fontFamily: T.mono, fontSize: 10, color: C.faint, letterSpacing: "0.12em" }}>
                  ROUND {race.round_number} · {year}
                </div>
                <div style={{ fontFamily: T.display, fontWeight: 900, fontSize: 36, lineHeight: 1, marginTop: 6 }}>
                  {race.name.toUpperCase()}
                </div>
                <div style={{ fontFamily: T.mono, fontSize: 12, color: C.mist, marginTop: 8 }}>
                  {race.circuit_name.toUpperCase()}
                  {race.city ? ` · ${race.city}` : ""}
                  {race.country ? ` · ${race.country}` : ""}
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
                  {blocked ? (
                    <Chip tone="caution">CANCELLED</Chip>
                  ) : (
                    <Chip tone={race.status === "LIVE" ? "caution" : race.status === "COMPLETED" ? "green" : "mist"}>
                      {race.status}
                    </Chip>
                  )}
                  {race.is_sprint_weekend && <Chip tone="purple">SPRINT WEEKEND</Chip>}
                  {weekendDate(race) && <Chip tone="mist">{weekendDate(race)}</Chip>}
                </div>
                {blocked && (
                  <div style={{ marginTop: 16, fontFamily: T.mono, fontSize: 12, color: C.caution }}>
                    {race.cancelled_reason || `${race.name} was cancelled and cannot be replayed.`}
                  </div>
                )}

                {!blocked && (
                  <>
                    <div
                      style={{
                        fontFamily: T.mono,
                        fontSize: 10,
                        color: C.faint,
                        letterSpacing: "0.12em",
                        marginTop: 28,
                        marginBottom: 10,
                      }}
                    >
                      SESSION
                    </div>
                    {sessions.status === "loading" && <SkeletonPanel rows={2} label="Loading sessions…" />}
                    {sessions.status === "error" && <ErrorPanel message={sessions.error} onRetry={sessions.retry} />}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fill, minmax(148px, 1fr))",
                        gap: 10,
                      }}
                    >
                      {sessionList.map((s) => {
                        const on = s.session_type === (selectedSession?.session_type ?? sessionType);
                        const ready = s.status === "COMPLETED" || s.status === "LIVE";
                        return (
                          <button
                            key={s.session_type}
                            disabled={!ready}
                            onClick={() => {
                              setSessionType(s.session_type);
                              setIngest(null);
                            }}
                            onDoubleClick={() => {
                              if (!ready) return;
                              setSessionType(s.session_type);
                              watch();
                            }}
                            style={{
                              textAlign: "left",
                              padding: "12px 12px 14px",
                              cursor: ready ? "pointer" : "not-allowed",
                              background: on ? C.signalMid : C.panel,
                              border: `1px solid ${on ? C.signal : C.border}`,
                              color: ready ? C.paper : C.faint,
                              borderRadius: 6,
                            }}
                          >
                            <div style={{ fontFamily: T.mono, fontSize: 10, color: on ? C.signal : C.faint }}>
                              {s.session_type}
                            </div>
                            <div style={{ fontFamily: T.display, fontWeight: 800, fontSize: 18, marginTop: 4 }}>
                              {(SESSION_LABEL[s.session_type] || s.session_name).toUpperCase()}
                            </div>
                            <div style={{ fontFamily: T.mono, fontSize: 10, color: C.mist, marginTop: 6 }}>
                              {formatWhen(s.datetime_utc) || s.status}
                            </div>
                            <div style={{ marginTop: 8 }}>
                              <Chip
                                tone={s.status === "LIVE" ? "caution" : s.status === "COMPLETED" ? "green" : "mist"}
                                size="xs"
                              >
                                {s.status}
                              </Chip>
                            </div>
                          </button>
                        );
                      })}
                    </div>

                    <button
                      disabled={!playable}
                      onClick={watch}
                      style={{
                        marginTop: 22,
                        width: "100%",
                        padding: "16px 28px",
                        background: playable ? C.signal : C.ghost,
                        border: "none",
                        borderRadius: 4,
                        color: playable ? C.ink : C.faint,
                        fontFamily: T.display,
                        fontSize: 18,
                        fontWeight: 800,
                        cursor: playable ? "pointer" : "not-allowed",
                        letterSpacing: "0.08em",
                      }}
                    >
                      {playable
                        ? `WATCH ${selectedSession?.session_name.toUpperCase() || "SESSION"} →`
                        : "SELECT A COMPLETED SESSION"}
                    </button>
                    {ingest && (
                      <div style={{ marginTop: 10 }}>
                        <Chip tone={ingest === "INGESTED" ? "green" : ingest === "INGESTING" ? "signal" : "mist"} size="xs">
                          {ingest === "INGESTING" ? "PREPARING TELEMETRY…" : ingest}
                        </Chip>
                      </div>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </Shell>
  );
}
