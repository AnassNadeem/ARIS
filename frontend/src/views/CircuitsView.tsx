import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiGet } from "../api/client";
import type { CalendarRound, CircuitMap } from "../api/types";
import { useCalendar } from "../hooks/useCalendar";
import { useCircuit } from "../hooks/useCircuit";
import { useCircuitMap } from "../hooks/useCircuitMap";
import { C, T } from "../theme";
import { Chip, EmptyState, ErrorPanel, Panel, SkeletonPanel } from "../components/atoms";
import { CircuitOutline, TrackMapKey } from "../components/CircuitSvg";
import { Shell } from "../components/Shell";

function needleZandvoort(slug: string): boolean {
  const s = slug.toLowerCase();
  return s.includes("zandvoort") || s === "netherlands" || s === "dutch";
}

export function CircuitsView() {
  const { slug } = useParams();
  const cal26 = useCalendar(2026);
  const cal25 = useCalendar(2025);
  const cal24 = useCalendar(2024);
  const rounds = useMemo(() => {
    const all = [
      ...(cal26.status === "ok" ? cal26.data.rounds : []),
      ...(cal25.status === "ok" ? cal25.data.rounds : []),
      ...(cal24.status === "ok" ? cal24.data.rounds : []),
    ];
    void all;
    const map = new Map<string, CalendarRound & { year: number }>();
    const buckets: [number, CalendarRound[]][] = [
      [2025, cal25.status === "ok" ? cal25.data.rounds : []],
      [2024, cal24.status === "ok" ? cal24.data.rounds : []],
      [2026, cal26.status === "ok" ? cal26.data.rounds : []],
    ];
    for (const [year, list] of buckets) {
      for (const r of list) {
        if (r.status === "COMPLETED" && !map.has(r.circuit_key)) {
          map.set(r.circuit_key, { ...r, year });
        }
      }
    }
    for (const [year, list] of buckets) {
      for (const r of list) {
        if (!map.has(r.circuit_key)) map.set(r.circuit_key, { ...r, year });
      }
    }
    return [...map.values()];
  }, [cal26, cal25, cal24]);

  const [previews, setPreviews] = useState<Record<string, CircuitMap>>({});
  useEffect(() => {
    if (slug || !rounds.length) return;
    let cancelled = false;
    const load = async () => {
      const batch = 3;
      for (let i = 0; i < rounds.length; i += batch) {
        if (cancelled) return;
        const chunk = rounds.slice(i, i + batch);
        const results = await Promise.allSettled(
          chunk.map(async (r) => {
            const p = await apiGet<CircuitMap>(`/api/circuit/${r.year}/${r.round_number}/preview`, { timeout: 8_000 });
            return [`${r.year}-${r.round_number}`, p] as const;
          }),
        );
        if (cancelled) return;
        setPreviews((prev) => {
          const next = { ...prev };
          for (const result of results) {
            if (result.status === "fulfilled") {
              const [k, p] = result.value;
              next[k] = p;
            }
          }
          return next;
        });
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [rounds, slug]);

  if (slug) {
    const needle = slug.toLowerCase().replace(/[\s_-]/g, "");
    const hit =
      rounds.find((r) => r.circuit_key === slug) ??
      rounds.find((r) =>
        [r.circuit_key, r.city, r.circuit_name, r.country].some(
          (s) => (s || "").toLowerCase().replace(/[\s_-]/g, "") === needle,
        ),
      );
    const fallback24 =
      cal24.status === "ok"
        ? cal24.data.rounds.find((r) => r.circuit_key === (hit?.circuit_key ?? slug))
        : undefined;
    return <CircuitDetail slug={slug} round={hit} fallbackRound={fallback24} />;
  }

  const loading = cal26.status === "loading" && cal25.status === "loading";
  return (
    <Shell title="CIRCUITS">
      <div style={{ padding: "24px 28px 40px", maxWidth: 1280, margin: "0 auto" }}>
        <div style={{ fontFamily: T.display, fontWeight: 800, fontSize: 28, letterSpacing: "0.04em", marginBottom: 6 }}>
          CIRCUIT MAPS
        </div>
        <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist, marginBottom: 18 }}>
          Sector 1 · 2 · 3 on the racing line · start/finish as a chequered stripe
        </div>
        {loading && <SkeletonPanel rows={10} label="Loading circuits…" />}
        {cal26.status === "error" && <ErrorPanel message={cal26.error} onRetry={cal26.retry} />}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
          {rounds.map((r) => (
            <CircuitCard
              key={r.circuit_key}
              round={r}
              year={r.year}
              preview={previews[`${r.year}-${r.round_number}`]}
            />
          ))}
        </div>
        {rounds.length === 0 && !loading && <EmptyState title="No circuits" body="Calendar has not loaded yet." />}
      </div>
    </Shell>
  );
}

function CircuitCard({ round, year, preview }: { round: CalendarRound; year: number; preview?: CircuitMap }) {
  const navigate = useNavigate();
  const map: CircuitMap =
    preview ??
    {
      year,
      round_number: round.round_number,
      x: [],
      y: [],
      corners: [],
      available: false,
      fallback: true,
    };
  return (
    <button
      onClick={() => navigate(`/circuits/${round.circuit_key}`)}
      style={{
        textAlign: "left",
        padding: 0,
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        cursor: "pointer",
        overflow: "hidden",
      }}
    >
      <div style={{ height: 150, background: C.ink, padding: "10px 8px 0" }}>
        <CircuitOutline map={map} width="100%" height={140} quietUnavailable showSectors />
      </div>
      <div style={{ padding: "12px 14px 14px" }}>
        <div style={{ fontFamily: T.display, fontSize: 20, fontWeight: 800, lineHeight: 1.1 }}>{round.circuit_name}</div>
        <div style={{ fontFamily: T.mono, fontSize: 10, color: C.mist, marginTop: 4 }}>
          {(round.city || "").toUpperCase()}
          {round.city ? " · " : ""}
          {round.country}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8, fontFamily: T.mono, fontSize: 9, color: C.faint }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 10, height: 3, background: C.purple, display: "inline-block" }} /> S1
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 10, height: 3, background: C.green, display: "inline-block" }} /> S2
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 10, height: 3, background: C.blue, display: "inline-block" }} /> S3
          </span>
        </div>
        <div style={{ fontFamily: T.mono, fontSize: 10, color: C.faint, marginTop: 8 }}>
          {round.name} · R{round.round_number} · {year}
        </div>
      </div>
    </button>
  );
}

function CircuitDetail({
  slug,
  round,
  fallbackRound,
}: {
  slug: string;
  round?: CalendarRound & { year?: number };
  fallbackRound?: CalendarRound;
}) {
  const navigate = useNavigate();
  const year = round?.year ?? 2025;
  const rn = round?.round_number ?? 15;
  const cmap = useCircuitMap(year, rn);
  const circuit = useCircuit(round?.circuit_key ?? slug, year);
  const [tip, setTip] = useState<string | null>(null);
  const fbYear = 2024;
  const fbRound = fallbackRound?.round_number ?? (needleZandvoort(slug) ? 15 : rn);
  const useFallback = cmap.status === "ok" && (!cmap.data.available || cmap.data.fallback);
  const cmap2 = useCircuitMap(fbYear, fbRound, Boolean(useFallback && (fbYear !== year || fbRound !== rn)));
  const map: CircuitMap | undefined =
    cmap.status === "ok" && cmap.data.available && !cmap.data.fallback
      ? cmap.data
      : cmap2.status === "ok" && cmap2.data.available
        ? cmap2.data
        : cmap.status === "ok"
          ? cmap.data
          : undefined;

  return (
    <Shell title="CIRCUIT">
      <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
        <button onClick={() => navigate("/circuits")} style={{ background: "none", border: "none", color: C.mist, fontFamily: T.mono, fontSize: 11, cursor: "pointer", marginBottom: 12 }}>
          ← ALL CIRCUITS
        </button>
        <div style={{ fontFamily: T.display, fontSize: 36, fontWeight: 900 }}>
          {circuit.chars.status === "ok" ? circuit.chars.data.name : round?.circuit_name ?? slug}
        </div>
        <div style={{ fontFamily: T.mono, fontSize: 12, color: C.mist, marginBottom: 16 }}>
          {circuit.chars.status === "ok" ? circuit.chars.data.country : round?.country}
        </div>
        <div style={{ position: "relative", height: 420, background: C.ink, border: `1px solid ${C.border}`, borderRadius: 8, overflow: "hidden" }}>
          {map ? (
            <CircuitOutline map={map} showCorners showSectors showDrs onCornerHover={(t) => setTip(t)} />
          ) : (
            <SkeletonPanel rows={6} label="Loading circuit map…" />
          )}
          {map && <TrackMapKey showDrs showSectors />}
          {tip && (
            <div style={{ position: "absolute", bottom: 8, left: 12, background: C.raised, padding: "4px 8px", fontFamily: T.mono, fontSize: 10 }}>{tip}</div>
          )}
        </div>
        {circuit.chars.status === "ok" && (
          <Panel title="CIRCUIT CHARACTERISTICS" style={{ marginTop: 16 }}>
            <div style={{ padding: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {[
                ["Length", circuit.chars.data.lap_length_km ? `${circuit.chars.data.lap_length_km} km` : "—"],
                ["Turns", String(circuit.chars.data.turns ?? "—")],
                ["DRS zones", String(circuit.chars.data.drs_zones ?? "—")],
                ["Pit loss", circuit.chars.data.pit_loss_seconds != null ? `${circuit.chars.data.pit_loss_seconds}s` : "—"],
                ["Tyre stress", circuit.chars.data.tyre_stress_rating ?? "—"],
                ["Track evolution", circuit.chars.data.track_evolution_rating ?? "—"],
              ].map(([k, v]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: C.mist, fontFamily: T.body, fontSize: 13 }}>{k}</span>
                  <span style={{ fontFamily: T.mono, fontSize: 12 }}>{v}</span>
                </div>
              ))}
              {circuit.chars.data.sector_descriptions.map((s) => (
                <div key={s} style={{ gridColumn: "1 / -1", fontFamily: T.body, fontSize: 12, color: C.mist }}>{s}</div>
              ))}
            </div>
          </Panel>
        )}
        <Panel title={`RACE HISTORY · FROM 2018`} style={{ marginTop: 12 }}>
          {circuit.history.status === "loading" && <SkeletonPanel rows={4} label="Loading history…" />}
          {circuit.history.status === "ok" && (
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 12 }}>
              <thead>
                <tr style={{ color: C.faint, fontSize: 9 }}>
                  {["Year", "Winner", "Team", "Pole", "Fastest Lap", "Weather"].map((h) => (
                    <th key={h} style={{ textAlign: "left", padding: "8px 10px" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {circuit.history.data.years.map((h) => (
                  <tr key={`${h.year}-${h.race_name || ""}`} style={{ borderBottom: `1px solid ${C.border}40` }}>
                    <td style={{ padding: "8px 10px" }}>{h.year}</td>
                    <td style={{ padding: "8px 10px" }}>{h.winner ?? "—"}</td>
                    <td style={{ padding: "8px 10px" }}>{h.winner_team ?? "—"}</td>
                    <td style={{ padding: "8px 10px" }}>{h.pole ?? "—"}</td>
                    <td style={{ padding: "8px 10px" }}>{h.fastest_lap ?? "—"}</td>
                    <td style={{ padding: "8px 10px" }}>{h.weather ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
        {circuit.chars.status === "ok" && circuit.chars.data.aris_notes && (
          <Panel title="ARIS CIRCUIT NOTES" style={{ marginTop: 12 }}>
            <div style={{ padding: 14, fontFamily: T.body, fontSize: 13, color: C.mist, lineHeight: 1.7 }}>
              <p>{circuit.chars.data.aris_notes.undercut_effectiveness}</p>
              <p style={{ marginTop: 8 }}>{circuit.chars.data.aris_notes.tyre_compound_tendencies}</p>
              <p style={{ marginTop: 8 }}>{circuit.chars.data.aris_notes.overtaking_difficulty}</p>
              <p style={{ marginTop: 8 }}>{circuit.chars.data.aris_notes.sc_probability_history}</p>
            </div>
          </Panel>
        )}
        {circuit.chars.status === "ok" && circuit.chars.data.estimated && <Chip tone="signal">ESTIMATED</Chip>}
      </div>
    </Shell>
  );
}
