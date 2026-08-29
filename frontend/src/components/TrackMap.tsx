import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CarPosition, CircuitMap, LiveTimingRow } from "../api/types";
import { C, SPEED_MS, SPEED_OPTIONS, T } from "../theme";
import { CircuitOutline, TrackMapKey } from "./CircuitSvg";
import { Chip, SkeletonPanel } from "./atoms";
import { useAllLapPositions, useCircuitMap, useReplayPath } from "../hooks/useCircuitMap";
import { useLivePositions } from "../hooks/useLivePositions";
import { useDrivers } from "../hooks/useDrivers";
import type { ReplayPathTrace } from "../api/types";

export type ReplayClockHandle = {
  startMs: number;
  elapsedRef: { current: number };
  playing: boolean;
};

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
  coastVel: number;
  gpsRaceMs: number;
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

function lerpFrac(a: number, b: number, u: number): number {
  let d = b - a;
  if (d < -0.5) d += 1;
  if (d > 0.5) d -= 1;
  return wrapFrac(a + u * d);
}

function sampleTrace(trace: ReplayPathTrace, tEpoch: number): number | null {
  const times = trace.t;
  const fracs = trace.f;
  const n = Math.min(times.length, fracs.length);
  if (!n) return null;
  if (tEpoch + 0.25 < times[0]) return null;
  let lo = 0;
  let hi = n - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (times[mid] <= tEpoch) lo = mid;
    else hi = mid - 1;
  }
  if (lo >= n - 1) return fracs[lo];
  const dt = times[lo + 1] - times[lo];
  const u = dt <= 1e-9 ? 0 : Math.max(0, Math.min(1, (tEpoch - times[lo]) / dt));
  return lerpFrac(fracs[lo], fracs[lo + 1], u);
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

function pathViewBox(xs: number[], ys: number[], extraX: number[] = [], extraY: number[] = [], pad = 12) {
  const allX = xs.concat(extraX).filter((v) => Number.isFinite(v));
  const allY = ys.concat(extraY).filter((v) => Number.isFinite(v));
  if (allX.length < 2 || allY.length < 2) {
    return { box: "0 0 440 280", w: 440, h: 280 };
  }
  const minX = Math.min(...allX);
  const maxX = Math.max(...allX);
  const minY = Math.min(...allY);
  const maxY = Math.max(...allY);
  const w = Math.max(maxX - minX, 8);
  const h = Math.max(maxY - minY, 8);
  return { box: `${minX - pad} ${minY - pad} ${w + pad * 2} ${h + pad * 2}`, w: w + pad * 2, h: h + pad * 2 };
}

function svgToLocal(svg: SVGSVGElement, x: number, y: number): { x: number; y: number } {
  const ctm = svg.getScreenCTM();
  const rect = svg.getBoundingClientRect();
  if (!ctm) return { x, y };
  const p = new DOMPoint(x, y).matrixTransform(ctm);
  return { x: p.x - rect.left, y: p.y - rect.top };
}

function mergeMapLayers(
  map: CircuitMap,
  feed?: {
    pitLaneX?: number[];
    pitLaneY?: number[];
    markers?: { kind: string; x: number; y: number; label: string }[];
    drsSegments?: number[][];
  },
): CircuitMap {
  const mapMarks = map.markers ?? [];
  const feedMarks = feed?.markers ?? [];
  const merged = [...mapMarks];
  for (const mark of feedMarks) {
    const dup = merged.some(
      (existing) =>
        existing.kind === mark.kind && Math.hypot(existing.x - mark.x, existing.y - mark.y) < 4,
    );
    if (!dup) merged.push(mark);
  }
  const feedPit = (feed?.pitLaneX?.length ?? 0) >= 2;
  return {
    ...map,
    pit_lane_x: feedPit ? feed?.pitLaneX : map.pit_lane_x,
    pit_lane_y: feedPit ? feed?.pitLaneY : map.pit_lane_y,
    markers: merged.filter((m) => m.kind !== "drs_detect"),
    drs_segments: [],
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
  playing = true,
  replaySessionKey,
  replayClock,
  replaySource,
  liveFeed,
  onSelect,
}: {
  year: number;
  round: number;
  cars: LiveTimingRow[];
  focusCode?: string;
  hiddenCars: string[];
  lap: number;
  live?: boolean;
  playing?: boolean;
  speed?: (typeof SPEED_OPTIONS)[number];
  replaySessionKey?: number | null;
  replayClock?: ReplayClockHandle;
  replaySource?: string | null;
  onSelect?: (code: string) => void;
  liveFeed?: {
    positions: CarPosition[];
    circuitPath?: { x: number[]; y: number[] } | null;
    pitLaneX?: number[];
    pitLaneY?: number[];
    markers?: { kind: string; x: number; y: number; label: string }[];
    drsSegments?: number[][];
    sessionFlag?: string | null;
  };
}) {
  const cmap = useCircuitMap(year, round);
  const replayPath = useReplayPath(replaySessionKey ?? null, year, round, replaySource);
  const tracesRef = useRef<Record<string, ReplayPathTrace>>({});
  if (replayPath.status === "ok") tracesRef.current = replayPath.data.traces || {};
  const replayClockRef = useRef(replayClock);
  replayClockRef.current = replayClock;
  const allPos = useAllLapPositions(year, round, !live && liveFeed == null);
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
  const viewBox = useMemo(
    () =>
      pathViewBox(
        pathX,
        pathY,
        [],
        [],
      ),
    [pathX, pathY, liveFeed?.pitLaneX, liveFeed?.pitLaneY, map?.pit_lane_x, map?.pit_lane_y],
  );
  const pathDataRef = useRef(pathData);
  pathDataRef.current = pathData;

  const driverCodes = useMemo(() => {
    const fromCars = cars.filter((c) => !c.eliminated).map((c) => c.driver_code);
    const liveDots = (liveFeed?.positions ?? (live ? livePos.positions : []))
      .filter((p) => !p.is_dnf)
      .map((p) => p.driver_code);
    const out = new Set(cars.filter((c) => c.eliminated).map((c) => c.driver_code));
    const codes = [...new Set([...fromCars, ...liveDots])];
    return codes.filter((code) => !hiddenCars.includes(code) && !out.has(code));
  }, [cars, hiddenCars, live, liveFeed, livePos.positions]);

  const carStatesRef = useRef<Map<string, CarAnimState>>(new Map());
  const carGroupRefs = useRef<Map<string, SVGGElement>>(new Map());
  const dotRefs = useRef<Map<string, SVGCircleElement>>(new Map());
  const labelRefs = useRef<Map<string, SVGTextElement>>(new Map());
  const svgRef = useRef<SVGSVGElement>(null);
  const missRef = useRef<Map<string, number>>(new Map());

  const playingRef = useRef(playing);
  playingRef.current = playing;
  const replayFeedRef = useRef(liveFeed != null);
  replayFeedRef.current = liveFeed != null;
  const coastRef = useRef(live || liveFeed != null);
  coastRef.current = live || liveFeed != null;
  const lastGpsAtRef = useRef(0);
  const lastGpsSigRef = useRef("");

  const rawPositions: CarPosition[] =
    liveFeed?.positions ??
    (live ? livePos.positions : positionsRef.current[String(lap)] ?? positionsRef.current[String(lap - 1)] ?? []);

  const gpsSig = rawPositions
    .map((p) => `${p.driver_code}:${(p.path_frac ?? 0).toFixed(4)}:${Math.round(p.x)}:${Math.round(p.y)}`)
    .join("|");
  const liveGapRef = useRef(2800);
  const replayGapRef = useRef(180);
  if (gpsSig && gpsSig !== lastGpsSigRef.current) {
    const nowGps = performance.now();
    if (lastGpsAtRef.current > 0) {
      const gap = nowGps - lastGpsAtRef.current;
      if (live && liveFeed == null) {
        liveGapRef.current = Math.min(2800, Math.max(700, gap));
      } else if (liveFeed != null) {
        replayGapRef.current = Math.min(700, Math.max(70, gap));
      }
    }
    lastGpsAtRef.current = nowGps;
    lastGpsSigRef.current = gpsSig;
  }

  const lapDurationMs =
    liveFeed != null
      ? Math.min(720, Math.max(80, replayGapRef.current * 1.22))
      : live
        ? Math.min(2800, Math.max(700, liveGapRef.current * 0.85))
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
      if (pos.is_dnf || eliminated.has(pos.driver_code)) {
        carStatesRef.current.delete(pos.driver_code);
        missRef.current.delete(pos.driver_code);
        continue;
      }
      incoming.add(pos.driver_code);
      missRef.current.set(pos.driver_code, 0);
      const existing = carStatesRef.current.get(pos.driver_code);
      if (replayClockRef.current && liveFeed != null) {
        if (existing) {
          existing.teamColour = pos.team_colour || colourByRef.current.get(pos.driver_code) || existing.teamColour;
          existing.isPitted = Boolean(pos.is_pitted);
          existing.isDnf = Boolean(pos.is_dnf) || eliminated.has(pos.driver_code);
          existing.reason = pos.reason ?? null;
          existing.useXy = Boolean(pos.is_pitted || pos.is_dnf);
        } else {
          const frac = pos.path_frac != null && Number.isFinite(pos.path_frac) ? wrapFrac(pos.path_frac) : 0;
          carStatesRef.current.set(pos.driver_code, {
            driverCode: pos.driver_code,
            currentFrac: frac,
            targetFrac: frac,
            prevFrac: frac,
            lapDurationMs: 1,
            lapStartTime: now,
            teamColour: pos.team_colour || colourByRef.current.get(pos.driver_code) || C.signal,
            isPitted: Boolean(pos.is_pitted),
            isDnf: Boolean(pos.is_dnf) || eliminated.has(pos.driver_code),
            reason: pos.reason ?? null,
            useXy: Boolean(pos.is_pitted || pos.is_dnf),
            prevX: pos.x,
            prevY: pos.y,
            targetX: pos.x,
            targetY: pos.y,
            currentX: pos.x,
            currentY: pos.y,
            coastVel: 0,
            gpsRaceMs: replayClockRef.current.elapsedRef.current ?? 0,
          });
        }
        continue;
      }
      const fromFrac =
        pos.path_frac != null && Number.isFinite(pos.path_frac) ? wrapFrac(pos.path_frac) : null;
      const fromXy =
        fromFrac == null && segments.length > 0 && Number.isFinite(pos.x) && Number.isFinite(pos.y)
          ? computePathFrac(pos.x, pos.y, segments, totalLength)
          : null;
      let frac =
        fromFrac != null
          ? fromFrac
          : fromXy != null && Number.isFinite(fromXy)
            ? wrapFrac(fromXy)
            : 0;
      const prevFrac = existing?.currentFrac ?? frac;
      let target = frac;
      if (!playing) {
        carStatesRef.current.set(pos.driver_code, {
          driverCode: pos.driver_code,
          currentFrac: frac,
          targetFrac: frac,
          prevFrac: frac,
          lapDurationMs: 1,
          lapStartTime: now,
          teamColour: pos.team_colour || colourByRef.current.get(pos.driver_code) || C.signal,
          isPitted: Boolean(pos.is_pitted),
          isDnf: Boolean(pos.is_dnf) || eliminated.has(pos.driver_code),
          reason: pos.reason ?? null,
          useXy: Boolean(pos.is_pitted || pos.is_dnf),
          prevX: pos.x,
          prevY: pos.y,
          targetX: pos.x,
          targetY: pos.y,
          currentX: pos.x,
          currentY: pos.y,
          coastVel: 0,
          gpsRaceMs: replayClockRef.current?.elapsedRef.current ?? 0,
        });
        continue;
      }
      if (existing && playing) {
        let d = frac - existing.currentFrac;
        if (d < -0.5) d += 1;
        if (d > 0.5) d -= 1;
        if (Math.abs(d) < 0.00012) continue;
      }
      if (pos.is_dnf || eliminated.has(pos.driver_code)) {
        target = existing?.currentFrac ?? frac;
      } else if (pos.is_pitted) {
        target = existing?.currentFrac ?? frac;
      } else if (!live && liveFeed == null) {
        if (!existing) {
          target = frac + 1;
        } else {
          let delta = frac - prevFrac;
          if (delta < 0.25) delta += 1;
          target = prevFrac + delta;
        }
      } else {
        let delta = target - prevFrac;
        if (delta < -0.12) delta += 1;
        if (delta > 0.92) delta -= 1;
        target = prevFrac + delta;
      }
      const useXy = Boolean(pos.is_pitted || pos.is_dnf);
      const travel = target - (existing ? prevFrac : frac);
      const raceNow = replayClockRef.current?.elapsedRef.current;
      const replayMotion = liveFeed != null && raceNow != null && Number.isFinite(raceNow);
      let coastVel = lapDurationMs > 0 ? travel / lapDurationMs : 0;
      if (replayMotion && !useXy) {
        const prevRace = existing?.gpsRaceMs ?? raceNow;
        const dt = Math.max(16, raceNow - prevRace);
        let d = frac - (existing?.currentFrac ?? frac);
        if (d < -0.5) d += 1;
        if (d > 0.5) d -= 1;
        const rawVel = existing && dt > 80 ? d / dt : 1 / 90_000;
        coastVel = rawVel < 0 ? 0 : rawVel;
      }
      carStatesRef.current.set(pos.driver_code, {
        driverCode: pos.driver_code,
        currentFrac: existing && !replayMotion ? prevFrac : frac,
        targetFrac: target,
        prevFrac: replayMotion ? frac : existing ? prevFrac : frac,
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
        coastVel,
        gpsRaceMs: replayMotion ? raceNow : 0,
      });
    }
    if (live && liveFeed == null) {
      for (const [code, car] of carStatesRef.current) {
        if (incoming.has(code)) continue;
        if (eliminated.has(code) || car.isDnf) {
          carStatesRef.current.delete(code);
          missRef.current.delete(code);
          continue;
        }
        const misses = (missRef.current.get(code) ?? 0) + 1;
        missRef.current.set(code, misses);
        if (misses >= 8) {
          carStatesRef.current.delete(code);
          missRef.current.delete(code);
        }
      }
    }
  }, [lap, rawPositions, lapDurationMs, live, playing, eliminatedKey, liveFeed]);

  useEffect(() => {
    let rafId = 0;
    function renderFrame() {
      const now = performance.now();
      const { segments } = pathDataRef.current;
      carStatesRef.current.forEach((car, code) => {
        const moving = playingRef.current;
        const elapsed = now - car.lapStartTime;
        const progress = moving ? Math.min(elapsed / Math.max(car.lapDurationMs, 1), 1) : 1;
        const eased = moving ? (replayFeedRef.current ? progress : easeInOut(progress)) : 1;
        let currentFrac: number;
        let point: PathPoint;
        const clock = replayClockRef.current;
        const trace = tracesRef.current[code];
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
        } else if (clock && Number.isFinite(clock.startMs) && trace?.t?.length >= 2) {
          const tEpoch = (clock.startMs + clock.elapsedRef.current) / 1000;
          currentFrac = sampleTrace(trace, tEpoch) ?? car.currentFrac;
          point = getPointAtFraction(segments, currentFrac);
        } else if (replayFeedRef.current && clock && Number.isFinite(clock.startMs) && !car.isPitted) {
          currentFrac = wrapFrac(car.currentFrac);
          point = getPointAtFraction(segments, currentFrac);
        } else {
          currentFrac = wrapFrac(car.prevFrac + eased * (car.targetFrac - car.prevFrac));
          if (moving && coastRef.current && progress >= 1 && !car.isPitted && !car.isDnf) {
            const extra = elapsed - car.lapDurationMs;
            const drifted = Math.min(0.2, Math.max(0, (car.coastVel || 0) * extra));
            currentFrac = wrapFrac(car.targetFrac + drifted);
          }
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
          if (code === "SC") label.textContent = "SC";
          else {
            label.textContent = car.isPitted || car.reason ? (car.reason?.startsWith("OUT") ? "OUT" : "PIT") : code;
          }
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
      {mapLoading && pathX.length < 2 && (
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
      <svg
        ref={svgRef}
        viewBox={viewBox.box}
        preserveAspectRatio="xMidYMid meet"
        style={{ width: "100%", height: "100%", display: "block" }}
      >
        {map && (
          <CircuitOutline
            map={mergeMapLayers(map, liveFeed)}
            embedded
            showDrs={false}
            showSectors={false}
          />
        )}
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
              pit_lane_x: liveFeed?.pitLaneX,
              pit_lane_y: liveFeed?.pitLaneY,
              markers: liveFeed?.markers,
              drs_segments: [],
            }}
            embedded
            showDrs={false}
            showSectors={false}
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
                  const svg = svgRef.current;
                  const car = carStatesRef.current.get(code);
                  const pt = car?.useXy
                    ? { x: car.currentX, y: car.currentY }
                    : getPointAtFraction(pathDataRef.current.segments, car?.currentFrac ?? 0);
                  const local = svg ? svgToLocal(svg, pt.x, pt.y) : pt;
                  setHover({
                    code,
                    name: nameBy.get(code) || code,
                    x: local.x,
                    y: local.y,
                    row: cars.find((c) => c.driver_code === code),
                    reason: car?.reason ?? cars.find((c) => c.driver_code === code)?.reason,
                  });
                }}
                onMouseLeave={() => setHover(null)}
                onClick={(ev) => {
                  ev.stopPropagation();
                  onSelect?.(code);
                }}
                style={{ cursor: "pointer" }}
              >
                {code === focusCode && <circle r={14} fill={C.signal} opacity={0.15} />}
                {code === "SC" ? (
                  <rect x={-11} y={-5} width={22} height={10} rx={2} fill="#F4D03F" stroke={C.ink} strokeWidth={1} />
                ) : (
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
                )}
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
      <TrackMapKey showDrs={false} showSectors={false} />
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
