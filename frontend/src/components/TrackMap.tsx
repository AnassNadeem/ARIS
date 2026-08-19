import { useEffect, useMemo, useRef, useState } from "react";
import type { CarPosition, CircuitMap, LiveTimingRow } from "../api/types";
import { C, SPEED_MS, SPEED_OPTIONS, T } from "../theme";
import { CircuitOutline } from "./CircuitSvg";
import { Chip, SkeletonPanel } from "./atoms";
import { useAllLapPositions, useCircuitMap } from "../hooks/useCircuitMap";
import { useLivePositions } from "../hooks/useLivePositions";
import { useDrivers } from "../hooks/useDrivers";

function normLive(p: CarPosition, map: CircuitMap): { x: number; y: number } {
  const b = map.bounds;
  if (!b) return { x: p.x, y: p.y };
  const dx = Math.max(b.max_x - b.min_x, 1e-6);
  const dy = Math.max(b.max_y - b.min_y, 1e-6);
  const looksNorm = p.x >= 0 && p.x <= 440 && p.y >= 0 && p.y <= 280;
  if (looksNorm && (p.x > 30 || p.y > 30)) return { x: p.x, y: p.y };
  return {
    x: 20 + ((p.x - b.min_x) / dx) * 400,
    y: 20 + (1 - (p.y - b.min_y) / dy) * 240,
  };
}

export function TrackMap({
  year,
  round,
  cars,
  focusCode,
  hiddenCars,
  lap,
  live,
  speed = "1×",
}: {
  year: number;
  round: number;
  cars: LiveTimingRow[];
  focusCode?: string;
  hiddenCars: string[];
  lap: number;
  live?: boolean;
  speed?: (typeof SPEED_OPTIONS)[number];
}) {
  const cmap = useCircuitMap(year, round);
  const allPos = useAllLapPositions(year, round, !live);
  const positionsRef = useRef<Record<string, CarPosition[]>>({});
  if (allPos.status === "ok") {
    positionsRef.current = allPos.data.laps;
  }
  const livePos = useLivePositions(!!live);
  const drivers = useDrivers(year);
  const [hover, setHover] = useState<{
    code: string;
    name: string;
    x: number;
    y: number;
    row?: LiveTimingRow;
  } | null>(null);

  const map: CircuitMap | null = cmap.status === "ok" ? cmap.data : null;
  const colourBy = useMemo(() => {
    const m = new Map<string, string>();
    if (drivers.status === "ok") {
      for (const d of drivers.data.drivers) {
        if (d.team_colour) m.set(d.driver_code, d.team_colour);
      }
    }
    for (const c of cars) {
      if (c.team_colour) m.set(c.driver_code, c.team_colour);
    }
    return m;
  }, [drivers, cars]);

  const nameBy = useMemo(() => {
    const m = new Map<string, string>();
    if (drivers.status === "ok") {
      for (const d of drivers.data.drivers) m.set(d.driver_code, d.full_name);
    }
    return m;
  }, [drivers]);

  const rawPositions: CarPosition[] = live
    ? livePos.positions
    : positionsRef.current[String(lap)] ?? positionsRef.current[String(lap - 1)] ?? [];

  const interpMs = Math.round((SPEED_MS[speed] ?? 90_000) * 0.8);

  const dots = useMemo(() => {
    const byCode = new Map(rawPositions.map((p) => [p.driver_code, p]));
    const codes =
      drivers.status === "ok"
        ? drivers.data.drivers.map((d) => d.driver_code)
        : cars.map((c) => c.driver_code);
    return codes
      .filter((code) => !hiddenCars.includes(code))
      .map((code) => {
        const p = byCode.get(code);
        const row = cars.find((c) => c.driver_code === code);
        const xy = p && map ? (live ? normLive(p, map) : { x: p.x, y: p.y }) : null;
        return {
          code,
          x: xy?.x ?? 220,
          y: xy?.y ?? 140,
          colour: colourBy.get(code) || C.signal,
          isDnf: p?.is_dnf,
          isPitted: p?.is_pitted,
          row,
        };
      });
  }, [rawPositions, cars, hiddenCars, colourBy, drivers, map, live]);

  useEffect(() => {
    /* lap change drives CSS transform */
  }, [lap]);

  const mapLoading = cmap.status === "loading";
  const posLoading = !live && allPos.status === "loading";
  const unavailable = map != null && (!map.available || map.fallback || map.x.length < 2);

  return (
    <div style={{ height: "100%", position: "relative" }}>
      {mapLoading && (
        <div style={{ position: "absolute", inset: 0, zIndex: 3, background: C.panel }}>
          <SkeletonPanel rows={6} label="Loading circuit — this may take ~30s on first load" />
        </div>
      )}
      {posLoading && !mapLoading && (
        <div
          style={{
            position: "absolute",
            top: 8,
            left: 8,
            right: 8,
            zIndex: 3,
            background: C.raised,
            border: `1px solid ${C.border}`,
            padding: "8px 10px",
            fontFamily: T.mono,
            fontSize: 10,
            color: C.mist,
          }}
        >
          Loading race telemetry — this takes ~20s on first load, then it's instant.
        </div>
      )}
      {unavailable && (
        <div style={{ position: "absolute", top: 6, left: 8, zIndex: 2 }}>
          <Chip tone="signal" size="xs">MAP UNAVAILABLE</Chip>
        </div>
      )}
      <svg viewBox="0 0 440 280" style={{ width: "100%", height: "100%" }}>
        {map && <CircuitOutline map={map} embedded showCorners />}
        {dots.map((d) => {
          const r = d.code === focusCode ? 10 : 7;
          return (
            <g
              key={d.code}
              style={{
                transform: `translate(${d.x}px, ${d.y}px)`,
                transition: `transform ${interpMs}ms ease-out`,
              }}
              onMouseEnter={(e) => {
                const svg = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                setHover({
                  code: d.code,
                  name: nameBy.get(d.code) || d.code,
                  x: e.clientX - svg.left,
                  y: e.clientY - svg.top,
                  row: d.row,
                });
              }}
              onMouseLeave={() => setHover(null)}
            >
              {d.code === focusCode && <circle r={r + 4} fill="none" stroke={C.signal} strokeWidth={1.4} />}
              <circle
                r={r}
                fill={d.colour}
                opacity={d.isDnf ? 0.35 : d.isPitted ? 0.6 : 1}
                stroke={d.isDnf || d.isPitted ? C.paper : d.code === focusCode ? C.signal : "none"}
                strokeDasharray={d.isDnf || d.isPitted ? "2 2" : undefined}
                strokeWidth={d.isDnf || d.isPitted || d.code === focusCode ? 1.4 : 0}
              />
              {d.isDnf && (
                <text textAnchor="middle" y={3} fill={C.paper} style={{ fontSize: 8, fontFamily: T.mono }}>
                  ✕
                </text>
              )}
              {d.isPitted && !d.isDnf && (
                <text textAnchor="middle" y={3} fill={C.paper} style={{ fontSize: 8, fontFamily: T.mono }}>
                  P
                </text>
              )}
              <text
                y={-(r + 6)}
                textAnchor="middle"
                fill={C.paper}
                style={{ fontFamily: T.mono, fontSize: 8, fontWeight: 700 }}
              >
                {d.code}
              </text>
            </g>
          );
        })}
      </svg>
      {hover && (
        <div
          style={{
            position: "absolute",
            left: hover.x + 8,
            top: hover.y + 8,
            background: C.raised,
            border: `1px solid ${C.border}`,
            padding: "8px 10px",
            borderRadius: 4,
            pointerEvents: "none",
            zIndex: 5,
            minWidth: 140,
          }}
        >
          <div style={{ fontFamily: T.mono, fontSize: 11, color: C.signal }}>{hover.name}</div>
          <div style={{ fontFamily: T.mono, fontSize: 10, color: C.mist, marginTop: 4 }}>
            P{hover.row?.position ?? "—"} · gap {hover.row?.gap_to_leader_s != null ? `+${hover.row.gap_to_leader_s.toFixed(1)}s` : "—"}
          </div>
          <div style={{ fontFamily: T.mono, fontSize: 10, color: C.mist }}>
            {hover.row?.compound ?? "—"} · {hover.row?.tyre_life ?? "—"}L · last{" "}
            {hover.row?.last_lap_ms != null ? (hover.row.last_lap_ms / 1000).toFixed(3) : "—"}
          </div>
        </div>
      )}
    </div>
  );
}
