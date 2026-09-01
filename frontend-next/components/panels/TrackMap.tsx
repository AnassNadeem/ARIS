"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRaceStore } from "@/store/raceStore";
import { getCircuitCoords, ghostMapFeatureEnabled } from "@/lib/api";
import { PathCarAnimator, GPS_HOLD_MS } from "@/lib/deadReckoning";
import { PIT_ENTRY_FRAC, ghostPlaybackAt } from "@/lib/ghostCar";
import { replayDisplayFrac } from "@/lib/r2Replay";
import { replayDisplayElapsed } from "@/lib/timingPath";
import { wrappedDelta } from "@/lib/deadReckoning";
import {
  buildPath,
  fractionAtPoint,
  pointAtFraction,
  polylinePoints,
  sectorPathsFromOutline,
  sectorsAreUsable,
  viewBoxFor,
  wrap01,
} from "@/lib/trackGeometry";
import { onTrackCarCodes } from "@/lib/mapCars";
import { chequeredSfFlag, startFinishMarker } from "@/lib/replayFilter";
import { PlaybackControls } from "@/components/ui/PlaybackControls";
import { TrackLightsOut } from "@/components/ui/TrackLightsOut";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import { useFocusDriver } from "@/lib/useFocusDriver";
import type { CarState, CircuitCoords, CircuitSectorPath } from "@/lib/types";

const GHOST_PREFIX = "A_";
const SECTOR_STROKE: Record<string, string> = {
  s1: "#39ff14",
  s2: "#f5a623",
  s3: "#e8002d",
};

/** Glow radius / opacity stops vs replay speed. Capped at 16x. */
const SPEED_GLOW_STOPS: { speed: number; radius: number; opacity: number }[] = [
  { speed: 1, radius: 0, opacity: 0 },
  { speed: 2, radius: 1, opacity: 0.19 },
  { speed: 5, radius: 2, opacity: 0.31 },
  { speed: 10, radius: 3, opacity: 0.44 },
  { speed: 16, radius: 4, opacity: 0.56 },
];

function parseRgb(colour: string): [number, number, number] {
  const hex = (colour.startsWith("#") ? colour.slice(1) : colour).replace(/[^0-9a-fA-F]/g, "").slice(0, 6).padEnd(6, "0");
  const n = Number.parseInt(hex, 16);
  if (!Number.isFinite(n)) return [255, 255, 255];
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** CSS drop-shadow filter for a car dot. Intensifies with playbackSpeed, capped at 16x. */
function speedGlowFilter(speed: number, colour: string): string {
  if (!Number.isFinite(speed) || speed <= 1) return "none";
  let i = 0;
  while (i < SPEED_GLOW_STOPS.length - 1 && speed > SPEED_GLOW_STOPS[i + 1].speed) i++;
  const a = SPEED_GLOW_STOPS[i];
  const b = SPEED_GLOW_STOPS[Math.min(i + 1, SPEED_GLOW_STOPS.length - 1)];
  const span = b.speed - a.speed;
  const t = span <= 0 ? 0 : Math.max(0, Math.min(1, (speed - a.speed) / span));
  const radius = a.radius + t * (b.radius - a.radius);
  const opacity = Math.round((a.opacity + t * (b.opacity - a.opacity)) * 100) / 100;
  if (radius < 0.05) return "none";
  const [r, g, bch] = parseRgb(colour);
  return `drop-shadow(0 0 ${radius}px rgba(${r},${g},${bch},${opacity}))`;
}

function pitBoardAnchor(coords: CircuitCoords): { x: number; y: number } {
  const path = buildPath(coords.x, coords.y);
  const p = pointAtFraction(path, PIT_ENTRY_FRAC);
  const n = coords.x.length;
  if (n < 1) return p;
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < n; i++) {
    cx += coords.x[i];
    cy += coords.y[i];
  }
  cx /= n;
  cy /= n;
  let dx = cx - p.x;
  let dy = cy - p.y;
  const len = Math.hypot(dx, dy) || 1;
  const offset = Math.max(12, (path.totalLength || 400) * 0.012);
  return { x: p.x + (dx / len) * offset, y: p.y + (dy / len) * offset };
}

function resolveSectors(coords: CircuitCoords): CircuitSectorPath[] {
  if (sectorsAreUsable(coords.sectorPaths)) return coords.sectorPaths as CircuitSectorPath[];
  const { paths, usedFallback } = sectorPathsFromOutline(coords.x, coords.y, coords.markers);
  if (usedFallback && coords.x.length >= 4) {
    console.warn("[ARIS map] Sector markers missing or unordered — using equal-distance S1/S2/S3 thirds.");
  }
  return paths;
}

function readCar(code: string): CarState | null {
  const s = useRaceStore.getState();
  if (s.cars[code]) return s.cars[code];
  if (s.ghostCar?.driver_code === code) return s.ghostCar;
  return null;
}

export function TrackMap() {
  const session = useRaceStore((s) => s.session);
  const setFocusDriver = useRaceStore((s) => s.setFocusDriver);
  const setCircuitOutline = useRaceStore((s) => s.setCircuitOutline);
  const focusCode = useFocusDriver("");
  const circuitOutline = useRaceStore((s) => s.circuitOutline);
  const racePhase = useRaceStore((s) => s.racePhase);
  const isRedFlag = racePhase === "RED_FLAG";
  const showGhostOnMap = ghostMapFeatureEnabled();
  const carCodesKey = useRaceStore((s) =>
    onTrackCarCodes(s.cars, s.isARISOn && s.ghostCar && ghostMapFeatureEnabled() ? s.ghostCar.driver_code : null),
  );
  const playbackSpeed = useRaceStore((s) => s.playbackSpeed);
  const ghostInPits = useRaceStore((s) => Boolean(s.ghostCar?.ghost_in_pits));
  const ghostPitLabel = useRaceStore((s) => {
    const g = s.ghostCar;
    if (!g) return null;
    return g.ghost_pit_compound ?? g.compound;
  });
  const showGhostLegend = useRaceStore((s) => Boolean(s.isARISOn && s.ghostCar && ghostMapFeatureEnabled()));
  const speedRef = useRef(playbackSpeed);
  speedRef.current = playbackSpeed;

  const feedLoading = usePanelFeedLoading();
  const [coords, setCoords] = useState<CircuitCoords | null>(null);
  const [outlineSettled, setOutlineSettled] = useState(false);
  const groupRefs = useRef<Map<string, SVGGElement>>(new Map());
  const animators = useRef<Map<string, PathCarAnimator>>(new Map());
  const rafRef = useRef(0);
  const pathRef = useRef<ReturnType<typeof buildPath> | null>(null);
  const codesRef = useRef<string[]>([]);

  useEffect(() => {
    let mounted = true;
    setOutlineSettled(false);
    getCircuitCoords(session?.year ?? new Date().getUTCFullYear(), session?.round ?? 15)
      .then((c) => {
        if (!mounted) return;
        if (c.x.length) {
          setCoords(c);
          setCircuitOutline(c);
        }
      })
      .finally(() => {
        if (mounted) setOutlineSettled(true);
      });
    return () => {
      mounted = false;
    };
  }, [session?.year, session?.round, setCircuitOutline]);

  useEffect(() => {
    if (!circuitOutline?.x?.length) return;
    setCoords((prev) => {
      if (prev && prev.x.length >= circuitOutline.x.length) return prev;
      return circuitOutline;
    });
  }, [circuitOutline]);

  const path = useMemo(() => (coords ? buildPath(coords.x, coords.y) : null), [coords]);
  const viewBox = useMemo(() => (coords ? viewBoxFor(coords.x, coords.y) : "0 0 800 500"), [coords]);
  const sectors = useMemo(() => (coords ? resolveSectors(coords) : []), [coords]);
  const pitAnchor = useMemo(() => (coords && coords.x.length ? pitBoardAnchor(coords) : null), [coords]);
  pathRef.current = path;

  const carCodes = useMemo(() => (carCodesKey ? carCodesKey.split(",") : []), [carCodesKey]);
  codesRef.current = carCodes;

  // 2A — how positions used to update (before this interpolation pass):
  // 1. A replay-frame poll writes cars into Zustand. TrackMap does not React-snap the SVG;
  //    rAF reads path_frac via getState() and called PathCarAnimator.onTick every frame, which
  //    restarted a 900ms ease so dots lagged then lurched toward each new GPS sample.
  // 2. Between polls rAF WAS moving cars (currentPosition), but the ease never reached the
  //    target before the next 250ms tick, so motion looked stepped especially at 4×.
  // 3. speed_kph comes from timing (FastF1 car samples). heading_rad is not in the replay-frame
  //    payload (mapCars hardcodes 0). Cartesian dead-reckoning (2C) is skipped; along-track
  //    velocity from path_frac deltas is kept.
  const lastFrac = useRef<Map<string, number>>(new Map());
  const displayElapsedRef = useRef(0);
  const lastStoreElapsedRef = useRef(0);
  const lastPacketAtRef = useRef(0);
  const lastSpeedRef = useRef(playbackSpeed);

  useEffect(() => {
    function frame() {
      const now = performance.now();
      const store = useRaceStore.getState();
      const racing = store.consoleMode === "live" || store.consolePlayState === "racing";
      const playing = store.isPlaying && racing && store.racePhase !== "RED_FLAG";
      const storeElapsed = store.replayElapsedS;
      const speedChanged = lastSpeedRef.current !== store.playbackSpeed;
      lastSpeedRef.current = store.playbackSpeed;
      const seek = speedChanged || (racing && Math.abs(storeElapsed - lastStoreElapsedRef.current) > 1);
      lastStoreElapsedRef.current = storeElapsed;
      if (!racing) {
        displayElapsedRef.current = 0;
      } else if (store.consoleMode === "replay") {
        displayElapsedRef.current = replayDisplayElapsed(
          storeElapsed,
          speedChanged ? now : store.lastTickPerfTime,
          now,
          playing,
          store.playbackSpeed,
        );
      } else {
        displayElapsedRef.current = storeElapsed;
      }
      const holdMs = store.playbackSpeed <= 1 ? 0 : GPS_HOLD_MS;
      const packetDue = seek || holdMs <= 0 || now - lastPacketAtRef.current >= holdMs;
      if (packetDue) lastPacketAtRef.current = now;

      const line = pathRef.current;
      if (line) {
        const field = store.r2RaceField;
        for (const code of codesRef.current) {
          const car = readCar(code);
          if (!car) continue;
          if (car.is_pitted || car.is_dnf) continue;
          const prevKnown = lastFrac.current.get(code);
          const isGhost = code.startsWith(GHOST_PREFIX);
          let frac: number;
          if (isGhost && store.ghostLapS.length > 1 && racing) {
            const pb = ghostPlaybackAt({
              elapsedS: displayElapsedRef.current,
              ghostLapS: store.ghostLapS,
              ghostCumulativeS: store.ghostCumulativeS.length > 1 ? store.ghostCumulativeS : [0, 90],
              totalLaps: store.totalLaps || 1,
              pitLaps: [],
              pitLossS: store.pitLossS,
            });
            frac = pb.path_frac;
          } else if (field && store.consoleMode === "replay") {
            frac = replayDisplayFrac(field, code, displayElapsedRef.current);
          } else if (car.path_frac != null && Number.isFinite(car.path_frac)) {
            frac = car.path_frac;
          } else if (prevKnown != null && Number.isFinite(prevKnown)) {
            frac = prevKnown;
          } else {
            frac = fractionAtPoint(line, car.x, car.y);
          }
          if (!isGhost && !seek && prevKnown != null && Number.isFinite(prevKnown)) {
            const d = wrappedDelta(prevKnown, frac);
            if (d > 0.25) frac = wrap01(prevKnown + 0.25);
            else if (d < -0.05) frac = prevKnown;
          }
          let animator = animators.current.get(code);
          if (!animator) {
            animator = new PathCarAnimator(line, frac, 140);
            animators.current.set(code, animator);
            lastFrac.current.set(code, frac);
            animator.onTick(frac, now, { playbackSpeed: store.playbackSpeed, seek: true, skipSeekJump: true });
          } else {
            animator.setPath(line);
            if (packetDue) {
              animator.onTick(frac, now, {
                speedKph: car.speed_kph,
                headingRad: car.heading_rad,
                skipSeekJump: Boolean(car.ghost_skip_seek_jump) || !seek,
                seek,
                snap: speedChanged,
                playbackSpeed: store.playbackSpeed,
              });
              lastFrac.current.set(code, frac);
            }
          }
          const pos = animator.currentPosition(now, playing || !racing);
          const g = groupRefs.current.get(code);
          if (g) {
            g.setAttribute("transform", `translate(${pos.x}, ${pos.y})`);
            g.setAttribute("cx", String(pos.x));
            g.setAttribute("cy", String(pos.y));
            g.setAttribute("data-path-frac", frac.toFixed(4));
            if (!isGhost) {
              const circle = g.querySelector("circle");
              if (circle) {
                (circle as SVGCircleElement).style.filter = speedGlowFilter(
                  speedRef.current,
                  car.team_colour || "#ffffff",
                );
              }
            }
          }
        }
      }
      const live = new Set(codesRef.current);
      for (const code of Array.from(animators.current.keys())) {
        if (!live.has(code)) {
          animators.current.delete(code);
          lastFrac.current.delete(code);
        }
      }
      rafRef.current = requestAnimationFrame(frame);
    }
    rafRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const sf = coords ? startFinishMarker(coords.markers, coords.x, coords.y) : null;
  const flag = coords ? chequeredSfFlag(coords.x, coords.y, sf ?? undefined) : null;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-carbon">
      <div
        className={`relative min-h-0 flex-1 ${isRedFlag ? "outline outline-2 outline-[#E8002D]/70" : ""}`}
        style={isRedFlag ? { boxShadow: "inset 0 0 40px rgba(232,0,45,0.35)" } : undefined}
      >
        <svg viewBox={viewBox} preserveAspectRatio="xMidYMid meet" className="h-full w-full">
          {coords && (
            <polyline
              points={polylinePoints(coords.x, coords.y)}
              fill="none"
              stroke="#1f1f1f"
              strokeWidth={16}
              strokeLinejoin="round"
            />
          )}
          {sectors.map((seg) => (
            <polyline
              key={seg.kind}
              points={polylinePoints(seg.x, seg.y)}
              fill="none"
              stroke={SECTOR_STROKE[seg.kind] ?? "#3a3a3a"}
              strokeWidth={5}
              strokeLinejoin="round"
              opacity={0.95}
            />
          ))}
          {flag && (
            <g transform={`translate(${sf?.x ?? flag.cx}, ${sf?.y ?? flag.cy}) rotate(${flag.angle})`}>
              {Array.from({ length: flag.rows * flag.cols }, (_, n) => {
                const r = Math.floor(n / flag.cols);
                const c = n % flag.cols;
                return (
                  <rect
                    key={`sf-${r}-${c}`}
                    x={r * flag.cell - (flag.rows * flag.cell) / 2}
                    y={c * flag.cell - (flag.cols * flag.cell) / 2}
                    width={flag.cell}
                    height={flag.cell}
                    fill={(r + c) % 2 === 0 ? "#ffffff" : "#111111"}
                    stroke="#111111"
                    strokeWidth={0.15}
                  />
                );
              })}
            </g>
          )}
          {carCodes.map((code) => {
            const car = readCar(code);
            if (!car) return null;
            const isGhost = code.startsWith(GHOST_PREFIX);
            const isFocus = !isGhost && focusCode !== "" && code === focusCode;
            const r = isFocus ? 9 : isGhost ? 8 : 6;
            const hideDot =
              Boolean(car.is_pitted) ||
              Boolean(car.is_dnf) ||
              (isGhost && (ghostInPits || Boolean(car.ghost_in_pits)));
            return (
              <g
                key={code}
                data-testid={isGhost ? "ghost-dot" : `car-dot-${code}`}
                ref={(el) => {
                  if (el) groupRefs.current.set(code, el);
                  else groupRefs.current.delete(code);
                }}
                onClick={() => {
                  if (!isGhost) setFocusDriver(code);
                }}
                style={{ cursor: isGhost ? "default" : "pointer" }}
                opacity={hideDot ? 0 : 1}
                pointerEvents={hideDot ? "none" : undefined}
              >
                <title>{isGhost ? "ARIS Ghost" : car.full_name || code}</title>
                <circle
                  r={r}
                  fill={isGhost ? "#e8eef4" : car.team_colour}
                  fillOpacity={isGhost ? 0.42 : 1}
                  stroke={isGhost ? "#ffffff" : isFocus ? "#e8002d" : "#0a0a0a"}
                  strokeWidth={isGhost ? 2 : isFocus ? 2.5 : 1}
                  strokeDasharray={isGhost ? "3 3" : undefined}
                  filter={isFocus ? "url(#focus-glow)" : undefined}
                />
                {isGhost ? (
                  <text
                    x={12}
                    y={-10}
                    textAnchor="start"
                    fontSize={9}
                    fontFamily="var(--font-jbmono)"
                    fontWeight={700}
                    fill="#ffffff"
                  >
                    ARIS
                  </text>
                ) : (
                  <text
                    y={-14}
                    textAnchor="middle"
                    fontSize={isFocus ? 10 : 8}
                    fontFamily="var(--font-jbmono)"
                    fontWeight={700}
                    fill={isFocus ? "#e8002d" : "#ffffff"}
                  >
                    {code}
                  </text>
                )}
              </g>
            );
          })}
          {showGhostOnMap && ghostInPits && pitAnchor && (
            <g transform={`translate(${pitAnchor.x}, ${pitAnchor.y})`}>
              <rect
                x={-52}
                y={-11}
                width={104}
                height={22}
                rx={3}
                fill="#1a1a1a"
                stroke="#e8eef4"
                strokeWidth={1.2}
              />
              <text
                textAnchor="middle"
                y={4}
                fontSize={8}
                fontFamily="var(--font-jbmono)"
                fontWeight={700}
                fill="#ffffff"
              >
                {`ARIS PIT — ${ghostPitLabel ?? ""}`}
              </text>
            </g>
          )}
          <defs>
            <filter id="focus-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feDropShadow dx="0" dy="0" stdDeviation="2.4" floodColor="#e8002d" floodOpacity="0.9" />
            </filter>
          </defs>
        </svg>
        {sectors.length > 0 && (
          <div className="absolute right-2 top-2 z-10 flex items-center gap-2 rounded border border-border bg-carbon/80 px-2 py-1 font-sans text-[10px] uppercase text-white">
            {(["s1", "s2", "s3"] as const).map((k) => (
              <span key={k} className="flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-sm" style={{ background: SECTOR_STROKE[k] }} />
                {k.toUpperCase()}
              </span>
            ))}
          </div>
        )}
        {!coords && (feedLoading || !outlineSettled) && (
          <div className="absolute inset-0">
            <PanelSkeleton variant="map" />
          </div>
        )}
        {!coords && outlineSettled && !feedLoading && (
          <div className="absolute inset-0">
            <PanelEmpty
              title="Track map"
              detail="Live circuit outline with car positions, dead-reckoned between ticks. Empty until this session's GPS pack loads the circuit path."
            />
          </div>
        )}
        {isRedFlag && (
          <div
            data-testid="track-map-red-flag"
            className="absolute left-1/2 top-2 z-20 -translate-x-1/2 animate-pulse rounded border-2 border-[#E8002D] bg-carbon/90 px-3 py-1 font-mono-data text-[11px] font-bold uppercase tracking-wide text-[#E8002D]"
          >
            🔴 RED FLAG — Field frozen
          </div>
        )}
        {showGhostLegend && (
          <div className="absolute bottom-2 left-2 z-10 rounded border border-white/30 bg-carbon/85 px-2 py-1 font-sans text-[10px] uppercase tracking-wide text-white">
            {ghostInPits
              ? `⬛ ARIS — IN PITS (${ghostPitLabel ?? ""})`
              : "● ARIS Ghost — independent simulated strategy"}
          </div>
        )}
        <TrackLightsOut />
      </div>
      <PlaybackControls />
    </div>
  );
}
