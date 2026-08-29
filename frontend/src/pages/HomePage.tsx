import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, peekGet } from "../api/client";
import type { NextRace } from "../api/types";
import { nextRaceSchema } from "../api/types";
import { C, T } from "../theme";
import { SkeletonPanel } from "../components/atoms";

type Stats = {
  lap_time_mae_s: number;
  decision_match_rate: number;
  never_pit_baseline: number;
  avg_position_delta: number;
  clean_delta: number;
  disrupted_delta: number;
};

const FALLBACK_STATS: Stats = {
  lap_time_mae_s: 0.583,
  decision_match_rate: 0.325,
  never_pit_baseline: 0.25,
  avg_position_delta: -1.73,
  clean_delta: -1.49,
  disrupted_delta: -2.38,
};

function formatCompact(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${d}D ${h}H ${m}M`;
}

function LiveCountdown({ seconds }: { seconds: number }) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    setLeft(seconds);
    const id = window.setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => window.clearInterval(id);
  }, [seconds]);
  return <span>{formatCompact(left)}</span>;
}

const FEATURES: [string, string][] = [
  ["LAP-BY-LAP STRATEGY", "pit timing, compound choice, pace targets"],
  ["FULL REASONING", "every call shows pace gained vs pit cost"],
  ["REPLAY ANY RACE", "timing, map, and telemetry — view only"],
  ["LIVE RACE MODE", "real OpenF1 data, ARIS recommends in real time"],
];

export function HomePage() {
  const navigate = useNavigate();
  const cachedNext = peekGet<NextRace>("/api/next-race");
  const cachedStats = peekGet<Stats>("/api/aris/stats");
  const [next, setNext] = useState<NextRace | null>(cachedNext ?? null);
  const [stats, setStats] = useState<Stats>(cachedStats ?? FALLBACK_STATS);
  const [loading, setLoading] = useState(!cachedNext);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [n, s] = await Promise.all([
          apiGet("/api/next-race", { schema: nextRaceSchema, timeout: 60_000 }),
          apiGet<Stats>("/api/aris/stats", { timeout: 15_000 }).catch(() => FALLBACK_STATS),
        ]);
        if (!cancelled) {
          setNext(n);
          setStats(s);
        }
      } catch {
        if (!cancelled) setNext(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const offSeason = !next || next.off_season;
  const liveLabel = offSeason ? "⬤ LIVE: OFF SEASON" : `⬤ LIVE: ${next.name.toUpperCase()}`;
  const showBanner = !!next && !offSeason && next.days_until <= 7;
  const sessionName = next?.next_session_name ?? "FP1";

  return (
    <div style={{ flex: 1, minHeight: 0, overflow: "auto", background: C.void }}>
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "48px 24px 64px" }}>
        <div style={{ fontFamily: T.display, fontSize: 96, fontWeight: 900, letterSpacing: "-2px", lineHeight: 0.9, color: C.paper }}>
          ARIS
        </div>
        <div
          style={{
            fontFamily: T.mono,
            fontSize: 14,
            color: C.signal,
            letterSpacing: "0.16em",
            marginTop: 12,
          }}
        >
          Always-on Race Intelligence System
        </div>
        <p
          style={{
            fontFamily: T.body,
            fontSize: 16,
            color: C.mist,
            lineHeight: 1.7,
            maxWidth: 720,
            marginTop: 20,
          }}
        >
          ARIS is a digital race engineer that watches a Grand Prix and makes the decisions a real
          strategist makes — tyre choice, pit timing, Safety Car reactions — aimed at the best
          realistic outcome for your driver. Every recommendation shows its reasoning. Nothing is
          blindly decided.
        </p>
        <div style={{ display: "flex", gap: 12, marginTop: 28, flexWrap: "wrap" }}>
          <button
            onClick={() => navigate("/live")}
            style={{
              padding: "12px 22px",
              background: C.signal,
              border: "none",
              borderRadius: 4,
              color: C.ink,
              fontFamily: T.display,
              fontSize: 16,
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            {liveLabel}
          </button>
          <button
            onClick={() => navigate("/replay")}
            style={{
              padding: "12px 22px",
              background: "transparent",
              border: `1px solid ${C.signal}`,
              borderRadius: 4,
              color: C.signal,
              fontFamily: T.display,
              fontSize: 16,
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            ▶ WATCH A REPLAY
          </button>
        </div>

        {showBanner && next && (
          <div
            style={{
              marginTop: 28,
              padding: "10px 14px",
              border: `1px solid ${C.signal}55`,
              background: C.signalDim,
              borderRadius: 4,
              display: "flex",
              alignItems: "center",
              gap: 12,
              flexWrap: "wrap",
              fontFamily: T.mono,
              fontSize: 11,
              color: C.paper,
            }}
          >
            <span>
              🏁 {next.name.toUpperCase()} WEEKEND · {sessionName.toUpperCase()} IN{" "}
              <LiveCountdown seconds={next.countdown_seconds} />
            </span>
            <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
              <button
                onClick={() => navigate("/replay")}
                style={{
                  padding: "5px 10px",
                  background: C.signal,
                  border: "none",
                  color: C.ink,
                  fontFamily: T.mono,
                  fontSize: 10,
                  cursor: "pointer",
                  borderRadius: 3,
                }}
              >
                WATCH A REPLAY
              </button>
              <button
                onClick={() => navigate(`/circuits/${next.circuit_key}`)}
                style={{
                  padding: "5px 10px",
                  background: "transparent",
                  border: `1px solid ${C.border}`,
                  color: C.mist,
                  fontFamily: T.mono,
                  fontSize: 10,
                  cursor: "pointer",
                  borderRadius: 3,
                }}
              >
                VIEW CIRCUIT
              </button>
            </span>
          </div>
        )}

        {loading && <div style={{ marginTop: 28 }}><SkeletonPanel rows={3} label="Loading model stats…" /></div>}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginTop: 40 }}>
          <StatCard value={`${stats.lap_time_mae_s.toFixed(3)}s`} label="Calendar-wide lap time MAE" />
          <StatCard
            value={`${(stats.decision_match_rate * 100).toFixed(1)}%`}
            label="Decision match-rate 2024"
            sub={`vs ${(stats.never_pit_baseline * 100).toFixed(1)}% never-pit baseline`}
          />
          <StatCard
            value={`${stats.avg_position_delta.toFixed(2).replace("-", "−")}`}
            label="Average position delta"
            sub={`${stats.clean_delta.toFixed(2).replace("-", "−")} clean / ${stats.disrupted_delta.toFixed(2).replace("-", "−")} disrupted`}
          />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 28 }}>
          {FEATURES.map(([title, body]) => (
            <div
              key={title}
              style={{
                padding: 18,
                background: C.panel,
                border: `1px solid ${C.border}`,
                borderRadius: 6,
              }}
            >
              <div style={{ fontFamily: T.mono, fontSize: 11, color: C.signal, letterSpacing: "0.1em" }}>{title}</div>
              <div style={{ fontFamily: T.body, fontSize: 13, color: C.mist, marginTop: 8 }}>{body}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({ value, label, sub }: { value: string; label: string; sub?: string }) {
  return (
    <div style={{ padding: 18, background: C.panel, border: `1px solid ${C.border}`, borderRadius: 6 }}>
      <div style={{ fontFamily: T.display, fontSize: 36, fontWeight: 900, color: C.signal, lineHeight: 1 }}>{value}</div>
      <div style={{ fontFamily: T.mono, fontSize: 10, color: C.mist, marginTop: 8, letterSpacing: "0.06em" }}>{label}</div>
      {sub && <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}
