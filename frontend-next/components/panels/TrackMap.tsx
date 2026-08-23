"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRaceStore } from "@/store/raceStore";
import { getCircuitCoords } from "@/lib/api";
import { CarAnimator } from "@/lib/deadReckoning";
import { viewBoxFor } from "@/lib/trackGeometry";
import { PlaybackControls } from "@/components/ui/PlaybackControls";
import type { CarState } from "@/lib/types";

const GHOST_PREFIX = "A_";

export function TrackMap() {
  const session = useRaceStore((s) => s.session);
  const cars = useRaceStore((s) => s.cars);
  const ghostCar = useRaceStore((s) => s.ghostCar);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const arisDriver = useRaceStore((s) => s.arisDriver);

  const [coords, setCoords] = useState<{ x: number[]; y: number[] } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const groupRefs = useRef<Map<string, SVGGElement>>(new Map());
  const dotRefs = useRef<Map<string, SVGCircleElement>>(new Map());
  const labelRefs = useRef<Map<string, SVGTextElement>>(new Map());
  const animators = useRef<Map<string, CarAnimator>>(new Map());
  const rafRef = useRef(0);

  useEffect(() => {
    let mounted = true;
    getCircuitCoords(session?.year ?? 2025, session?.round ?? 15).then((c) => {
      if (mounted) setCoords(c);
    });
    return () => {
      mounted = false;
    };
  }, [session?.year, session?.round]);

  const viewBox = useMemo(() => (coords ? viewBoxFor(coords.x, coords.y) : "0 0 800 500"), [coords]);
  const polylinePoints = useMemo(() => {
    if (!coords) return "";
    return coords.x.map((x, i) => `${x},${coords.y[i]}`).join(" ");
  }, [coords]);

  const allCars: CarState[] = useMemo(() => {
    const list = Object.values(cars);
    if (isARISOn && ghostCar) list.push(ghostCar);
    return list;
  }, [cars, ghostCar, isARISOn]);

  // Feed real ticks into each car's dead-reckoning animator (no React state
  // writes for position — only refs, so the 60fps loop below never re-renders).
  useEffect(() => {
    const now = performance.now();
    for (const car of allCars) {
      const speedPxPerS = (car.speed_kph / 3.6) * 0.35; // scaled to map units
      let animator = animators.current.get(car.driver_code);
      if (!animator) {
        animator = new CarAnimator({ x: car.x, y: car.y }, 200);
        animators.current.set(car.driver_code, animator);
      }
      animator.onTick({ x: car.x, y: car.y }, speedPxPerS, car.heading_rad, now);
    }
    // Drop animators for cars no longer present.
    const codes = new Set(allCars.map((c) => c.driver_code));
    for (const code of Array.from(animators.current.keys())) {
      if (!codes.has(code)) animators.current.delete(code);
    }
  }, [allCars]);

  useEffect(() => {
    function frame() {
      const now = performance.now();
      animators.current.forEach((animator, code) => {
        const pos = animator.currentPosition(now);
        const g = groupRefs.current.get(code);
        if (g) g.setAttribute("transform", `translate(${pos.x}, ${pos.y})`);
      });
      rafRef.current = requestAnimationFrame(frame);
    }
    rafRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const focusCode = arisDriver ?? "VER";

  return (
    <div className="flex h-full flex-col bg-carbon">
      <div className="relative min-h-0 flex-1">
        <svg
          ref={svgRef}
          viewBox={viewBox}
          preserveAspectRatio="xMidYMid meet"
          className="h-full w-full"
        >
          {coords && (
            <polyline
              points={polylinePoints}
              fill="none"
              stroke="#2a2a2a"
              strokeWidth={14}
              strokeLinejoin="round"
            />
          )}
          {coords && (
            <polyline
              points={polylinePoints}
              fill="none"
              stroke="#3a3a3a"
              strokeWidth={1}
              strokeDasharray="4 6"
            />
          )}
          {allCars.map((car) => {
            const isGhost = car.driver_code.startsWith(GHOST_PREFIX);
            const isFocus = !isGhost && car.driver_code === focusCode;
            const r = isFocus ? 9 : isGhost ? 8 : 6;
            const displayCode = isGhost ? car.driver_code.replace(GHOST_PREFIX, "") : car.driver_code;
            return (
              <g
                key={car.driver_code}
                ref={(el) => {
                  if (el) groupRefs.current.set(car.driver_code, el);
                  else groupRefs.current.delete(car.driver_code);
                }}
              >
                <circle
                  r={r}
                  fill={isGhost ? car.team_colour : car.team_colour}
                  fillOpacity={isGhost ? 0.5 : 1}
                  stroke={isGhost ? "#ffffff" : isFocus ? "#e8002d" : "#0a0a0a"}
                  strokeWidth={isGhost ? 2 : isFocus ? 2 : 1}
                  strokeDasharray={isGhost ? "3 3" : undefined}
                  ref={(el) => {
                    if (el) dotRefs.current.set(car.driver_code, el);
                    else dotRefs.current.delete(car.driver_code);
                  }}
                />
                <text
                  y={-14}
                  textAnchor="middle"
                  fontSize={isFocus || isGhost ? 10 : 8}
                  fontFamily="var(--font-jbmono)"
                  fontWeight={700}
                  fill={isGhost ? "#ffffff" : isFocus ? "#e8002d" : "#ffffff"}
                  ref={(el) => {
                    if (el) labelRefs.current.set(car.driver_code, el);
                    else labelRefs.current.delete(car.driver_code);
                  }}
                >
                  {isGhost ? `[A] ${displayCode}` : displayCode}
                </text>
              </g>
            );
          })}
        </svg>
        {!coords && (
          <div className="absolute inset-0 flex items-center justify-center font-mono-data text-xs text-muted">
            Loading circuit map…
          </div>
        )}
      </div>
      <PlaybackControls />
    </div>
  );
}
