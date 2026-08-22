import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CarPosition, CircuitMap, LiveTimingRow } from "../api/types";
import { C, SPEED_FACTOR, SPEED_MS, SPEED_OPTIONS, T } from "../theme";
import { CircuitOutline } from "./CircuitSvg";
import { Chip, SkeletonPanel } from "./atoms";
import { useAllLapPositions, useCircuitMap } from "../hooks/useCircuitMap";
import { useLivePositions } from "../hooks/useLivePositions";
import { useDrivers } from "../hooks/useDrivers";

interface PathPoint {
  x: number;
  y: number;
}
interface PathSegment {
  start: PathPoint;
  end: PathPoint;
  length: number;
  cumulativeFrac: number;
}
interface CarAnimState {
  driverCode: string;
  currentFrac: number;
  targetFrac: number;
  prevFrac: number;
  lapDurationMs: number;
  lapStartTime: number;
  teamColour: string;
  isPitted: boolean;
  isDnf: boolean;
  reason?: string | null;
  useXy: boolean;
  prevX: number;
  prevY: number;
  targetX: number;
  targetY: number;
  currentX: number;
  currentY: number;
}

function buildPathSegments(pathX: number[], pathY: number[]): { segments: PathSegment[]; totalLength: number } {
  const xs = [...pathX];
  const ys = [...pathY];
  const n0 = Math.min(xs.length, ys.length);
  if (n0 >= 2 && (xs[0] !== xs[n0 - 1] || ys[0] !== ys[n0 - 1])) {
    xs.push(xs[0]);
    ys.push(ys[0]);
  }
  const segments: PathSegment[] = [];
  const n = Math.min(xs.length, ys.length);
  const lengths: number[] = [];
  let totalLength = 0;
  for (let i = 0; i < n - 1; i++) {
    const dx = xs[i + 1] - xs[i];
    const dy = ys[i + 1] - ys[i];
    const len = Math.sqrt(dx * dx + dy * dy);
    lengths.push(len);
    totalLength += len;
  }
  if (totalLength <= 0) return { segments, totalLength: 0 };
  let cumulative = 0;
  for (let i = 0; i < n - 1; i++) {
    segments.push({
      start: { x: xs[i], y: ys[i] },
      end: { x: xs[i + 1], y: ys[i + 1] },
      length: lengths[i],
      cumulativeFrac: cumulative / totalLength,
    });
    cumulative += lengths[i];
  }
  return { segments, totalLength };
}

function getPointAtFraction(segments: PathSegment[], frac: number): PathPoint {
  if (!segments.length) return { x: 220, y: 140 };
  const f = ((frac % 1) + 1) % 1;
  let lo = 0;
  let hi = segments.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (segments[mid].cumulativeFrac <= f) lo = mid;
    else hi = mid - 1;
  }
  const seg = segments[lo];
  const nextFrac = lo < segments.length - 1 ? segments[lo + 1].cumulativeFrac : 1.0;
  const segFrac = nextFrac > seg.cumulativeFrac ? (f - seg.cumulativeFrac) / (nextFrac - seg.cumulativeFrac) : 0;
  return {
    x: seg.start.x + segFrac * (seg.end.x - seg.start.x),
    y: seg.start.y + segFrac * (seg.end.y - seg.start.y),
  };
}

function wrapFrac(v: number): number {
  return ((v % 1) + 1) % 1;
}

function computePathFrac(x: number, y: number, segments: PathSegment[], totalLength: number): number {
  if (!segments.length || totalLength <= 0) return 0;
  let minDist = Infinity;
  let best = 0;
  for (const seg of segments) {
    const abx = seg.end.x - seg.start.x;
    const aby = seg.end.y - seg.start.y;
    const len2 = seg.length * seg.length || 1;
    let t = ((x - seg.start.x) * abx + (y - seg.start.y) * aby) / len2;
    t = Math.max(0, Math.min(1, t));
    const px = seg.start.x + t * abx;
    const py = seg.start.y + t * aby;
    const d = (x - px) ** 2 + (y - py) ** 2;
    if (d < minDist) {
      minDist = d;
      best = seg.cumulativeFrac + (t * seg.length) / totalLength;
    }
  }
  return best;
}

function easeInOut(progress: number): number {
  return progress < 0.5 ? 2 * progress * progress : 1 - Math.pow(-2 * progress + 2, 2) / 2;
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
  replaySessionKey,
  liveFeed,
}: {
  year: number;
  round: number;
  cars: LiveTimingRow[];
  focusCode?: string;
  hiddenCars: string[];
  lap: number;
  live?: boolean;
  speed?: (typeof SPEED_OPTIONS)[number];
  replaySessionKey?: number | null;
  liveFeed?: { positions: CarPosition[]; circuitPath?: { x: number[]; y: number[] } | null };
}) {
  const cmap = useCircuitMap(year, round);
  const allPos = useAllLapPositions(year, round, !live);
  const positionsRef = useRef<Record<string, CarPosition[]>>({});
  const circuitPathRef = useRef<{ x: number[]; y: number[] } | null>(null);
  if (allPos.status === "ok") {
    positionsRef.current = allPos.data.laps;
    if (allPos.data.circuit_path?.x?.length) circuitPathRef.current = allPos.data.circuit_path;
  }
  const livePos = useLivePositions(!!live && liveFeed == null, replaySessionKey);
  const drivers = useDrivers(year);
  const [hover, setHover] = useState<{
    code: string;
    name: string;
    x: number;
    y: number;
    row?: LiveTimingRow;
    reason?: string | null;
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

  const colourByRef = useRef(colourBy);
  colourByRef.current = colourBy;

  const nameBy = useMemo(() => {
    const m = new Map<string, string>();
    if (drivers.status === "ok") {
      for (const d of drivers.data.drivers) m.set(d.driver_code, d.full_name);
    }
    return m;
  }, [drivers]);

  const feedPath = liveFeed?.circuitPath ?? livePos.circuitPath;
  const pathX = map && map.x.length >= 2 ? map.x : (feedPath?.x ?? circuitPathRef.current?.x ?? []);
  const pathY = map && map.y.length >= 2 ? map.y : (feedPath?.y ?? circuitPathRef.current?.y ?? []);
  const pathData = useMemo(() => buildPathSegments(pathX, pathY), [pathX, pathY]);
  const pathDataRef = useRef(pathData);
  pathDataRef.current = pathData;

  const driverCodes = useMemo(() => {
    const fromDrivers =
      drivers.status === "ok" ? drivers.data.drivers.map((d) => d.driver_code) : cars.map((c) => c.driver_code);
    const fromPos = (liveFeed?.positions ?? []).map((p) => p.driver_code);
    const codes = [...new Set([...fromDrivers, ...fromPos, ...cars.map((c) => c.driver_code)])];
    return codes.filter((code) => !hiddenCars.includes(code));
  }, [drivers, cars, hiddenCars, liveFeed]);

  const carStatesRef = useRef<Map<string, CarAnimState>>(new Map());
  const carGroupRefs = useRef<Map<string, SVGGElement>>(new Map());
  const dotRefs = useRef<Map<string, SVGCircleElement>>(new Map());
  const labelRefs = useRef<Map<string, SVGTextElement>>(new Map());
  const svgRef = useRef<SVGSVGElement>(null);
  const missRef = useRef<Map<string, number>>(new Map());

  const rawPositions: CarPosition[] = live
    ? (liveFeed?.positions ?? livePos.positions)
    : positionsRef.current[String(lap)] ?? positionsRef.current[String(lap - 1)] ?? [];

  const lapDurationMs = live
    ? Math.min(2000, Math.max(160, 500 / (SPEED_FACTOR[speed] ?? 1)))
    : SPEED_MS[speed] ?? 90_000;
  const eliminatedKey = cars
    .filter((c) => c.eliminated)
    .map((c) => c.driver_code)
    .sort()
    .join(",");

  useEffect(() => {
    const { segments, totalLength } = pathDataRef.current;
    const now = performance.now();
    const incoming = new Set<string>();
    const eliminated = new Set(eliminatedKey ? eliminatedKey.split(",") : []);
    for (const pos of rawPositions) {
      incoming.add(pos.driver_code);
      missRef.current.set(pos.driver_code, 0);
      const existing = carStatesRef.current.get(pos.driver_code);
      let frac =
        pos.path_frac != null && Number.isFinite(pos.path_frac)
          ? wrapFrac(pos.path_frac)
          : computePathFrac(pos.x, pos.y, segments, totalLength);
      const prevFrac = existing?.currentFrac ?? frac;
      let target = frac;
      if (pos.is_dnf || eliminated.has(pos.driver_code)) {
        target = existing?.currentFrac ?? frac;
      } else if (pos.is_pitted) {
        target = existing?.currentFrac ?? frac;
      } else if (!live) {
        if (!existing) {
          target = frac + 1;
        } else {
          let delta = frac - prevFrac;
          if (delta < 0.25) delta += 1;
          target = prevFrac + delta;
        }
      } else {
        let delta = target - prevFrac;
        if (delta < -0.5) delta += 1;
        if (delta > 0.5) delta -= 1;
        target = prevFrac + delta;
      }
      const useXy = Boolean(pos.is_pitted || pos.is_dnf || pos.reason);
      carStatesRef.current.set(pos.driver_code, {
        driverCode: pos.driver_code,
        currentFrac: existing ? prevFrac : frac,
        targetFrac: target,
        prevFrac: existing ? prevFrac : frac,
        lapDurationMs,
        lapStartTime: now,
        teamColour: pos.team_colour || colourByRef.current.get(pos.driver_code) || C.signal,
        isPitted: Boolean(pos.is_pitted),
        isDnf: Boolean(pos.is_dnf) || eliminated.has(pos.driver_code),
        reason: pos.reason ?? null,
        useXy,
        prevX: existing && existing.useXy ? existing.currentX : pos.x,
        prevY: existing && existing.useXy ? existing.currentY : pos.y,
        targetX: pos.x,
        targetY: pos.y,
        currentX: existing && existing.useXy ? existing.currentX : pos.x,
        currentY: existing && existing.useXy ? existing.currentY : pos.y,
      });
    }
    if (live && liveFeed == null) {
      for (const [code, car] of carStatesRef.current) {
        if (incoming.has(code)) continue;
        const misses = (missRef.current.get(code) ?? 0) + 1;
        missRef.current.set(code, misses);
        if (misses >= 3) {
          carStatesRef.current.set(code, { ...car, isPitted: true });
        }
      }
    }
  }, [lap, rawPositions, lapDurationMs, live, eliminatedKey]);

  useEffect(() => {
    let rafId = 0;
    function renderFrame() {
      const now = performance.now();
      const { segments } = pathDataRef.current;
      carStatesRef.current.forEach((car, code) => {
        const elapsed = now - car.lapStartTime;
        const progress = Math.min(elapsed / Math.max(car.lapDurationMs, 1), 1);
        const eased = easeInOut(progress);
        let currentFrac: number;
        let point: PathPoint;
        if (car.useXy) {
          const x = car.prevX + eased * (car.targetX - car.prevX);
          const y = car.prevY + eased * (car.targetY - car.prevY);
          car.currentX = x;
          car.currentY = y;
          point = { x, y };
          currentFrac = car.prevFrac;
        } else if (car.isDnf) {
          currentFrac = wrapFrac(car.prevFrac);
          point = getPointAtFraction(segments, currentFrac);
        } else {
          currentFrac = wrapFrac(car.prevFrac + eased * (car.targetFrac - car.prevFrac));
          point = getPointAtFraction(segments, currentFrac);
        }
        car.currentFrac = currentFrac;
        const g = carGroupRefs.current.get(code);
        if (g) g.setAttribute("transform", `translate(${point.x}, ${point.y})`);
        const dot = dotRefs.current.get(code);
        const label = labelRefs.current.get(code);
        if (dot) {
          if (car.isDnf) {
            dot.setAttribute("fill", "transparent");
            dot.setAttribute("stroke", car.teamColour);
            dot.setAttribute("stroke-dasharray", "3,2");
            dot.setAttribute("opacity", "0.4");
          } else if (car.isPitted) {
            dot.setAttribute("fill", car.teamColour);
            dot.setAttribute("opacity", "0.5");
            dot.setAttribute("stroke-dasharray", "2,2");
            dot.setAttribute("stroke", C.paper);
          } else {
            dot.setAttribute("fill", car.teamColour);
            dot.setAttribute("opacity", "1");
            dot.setAttribute("stroke-dasharray", "none");
            if (code !== focusCode) dot.setAttribute("stroke", "none");
          }
        }
        if (label) {
          label.textContent = car.isPitted || car.reason ? (car.reason?.startsWith("OUT") ? "OUT" : "PIT") : code;
        }
      });
      rafId = requestAnimationFrame(renderFrame);
    }
    rafId = requestAnimationFrame(renderFrame);
    return () => cancelAnimationFrame(rafId);
  }, [pathData.totalLength, pathData.segments.length, focusCode]);

  useLayoutEffect(() => {
    const { segments } = pathDataRef.current;
    carStatesRef.current.forEach((car, code) => {
      const g = carGroupRefs.current.get(code);
      if (!g) return;
      const point = car.useXy
        ? { x: car.currentX, y: car.currentY }
        : getPointAtFraction(segments, car.currentFrac);
      g.setAttribute("transform", `translate(${point.x}, ${point.y})`);
    });
  });

  const mapLoading = cmap.status === "loading";
  const posLoading = !live && allPos.status === "loading";
  const unavailable = map != null && (!map.available || map.fallback || map.x.length < 2) && pathX.length < 2;

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
      <svg ref={svgRef} viewBox="0 0 440 280" style={{ width: "100%", height: "100%" }}>
        {map && <CircuitOutline map={map} embedded showCorners showSectors />}
        {!map && pathX.length >= 2 && (
          <CircuitOutline
            map={{
              year,
              round_number: round,
              x: pathX,
              y: pathY,
              corners: [],
              available: true,
              fallback: false,
            }}
            embedded
          />
        )}
        <g>
          {driverCodes.map((code) => {
            const r = code === focusCode ? 9 : 6;
            const colour = colourBy.get(code) || C.signal;
            return (
              <g
                key={code}
                ref={(el) => {
                  if (el) carGroupRefs.current.set(code, el);
                  else carGroupRefs.current.delete(code);
                }}
                onMouseEnter={() => {
                  const svg = svgRef.current?.getBoundingClientRect();
                  const car = carStatesRef.current.get(code);
                  const pt = car?.useXy
                    ? { x: car.currentX, y: car.currentY }
                    : getPointAtFraction(pathDataRef.current.segments, car?.currentFrac ?? 0);
                  const w = svg?.width ?? 440;
                  const h = svg?.height ?? 280;
                  setHover({
                    code,
                    name: nameBy.get(code) || code,
                    x: (pt.x / 440) * w,
                    y: (pt.y / 280) * h,
                    row: cars.find((c) => c.driver_code === code),
                    reason: car?.reason ?? cars.find((c) => c.driver_code === code)?.reason,
                  });
                }}
                onMouseLeave={() => setHover(null)}
                style={{ cursor: "pointer" }}
              >
                {code === focusCode && <circle r={14} fill={C.signal} opacity={0.15} />}
                <circle
                  r={r}
                  fill={colour}
                  stroke={code === focusCode ? C.signal : C.ink}
                  strokeWidth={code === focusCode ? 2 : 1}
                  ref={(el) => {
                    if (el) dotRefs.current.set(code, el);
                    else dotRefs.current.delete(code);
                  }}
                />
                <text
                  fontSize={code === focusCode ? 9 : 7}
                  fill={code === focusCode ? C.signal : C.paper}
                  fontFamily="IBM Plex Mono"
                  fontWeight="700"
                  textAnchor="middle"
                  dy={-12}
                  style={{ pointerEvents: "none" }}
                  ref={(el) => {
                    if (el) labelRefs.current.set(code, el);
                    else labelRefs.current.delete(code);
                  }}
                >
                  {code}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      {hover && (
        <div
          style={{
            position: "absolute",
            left: hover.x + 8,
            top: Math.max(4, hover.y - 60),
            background: C.raised,
            border: `1px solid ${C.border}`,
            padding: "8px 10px",
            borderRadius: 4,
            pointerEvents: "none",
            zIndex: 5,
            minWidth: 160,
            boxShadow: "0 8px 24px rgba(0,0,0,0.45)",
          }}
        >
          <div style={{ fontFamily: T.mono, fontSize: 11, color: C.signal }}>{hover.name}</div>
          {hover.reason && (
            <div style={{ fontFamily: T.mono, fontSize: 11, color: C.signal, marginTop: 4 }}>{hover.reason}</div>
          )}
          <div style={{ fontFamily: T.mono, fontSize: 10, color: C.mist, marginTop: 4 }}>
            P{hover.row?.position ?? "—"} · gap{" "}
            {hover.row?.gap_to_leader_s != null ? `+${hover.row.gap_to_leader_s.toFixed(1)}s` : "—"}
          </div>
          <div style={{ fontFamily: T.mono, fontSize: 10, color: C.mist }}>
            {hover.row?.compound ?? "—"} · {hover.row?.tyre_life ?? "—"}L · last{" "}
            {hover.row?.last_lap_ms != null ? (hover.row.last_lap_ms / 1000).toFixed(3) : "—"}
          </div>
          {hover.row?.speed_trap_kph != null && (
            <div style={{ fontFamily: T.mono, fontSize: 10, color: C.mist }}>
              trap {hover.row.speed_trap_kph.toFixed(0)} km/h
            </div>
          )}
        </div>
      )}
    </div>
  );
}
