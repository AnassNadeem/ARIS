import { useEffect, useRef } from "react";
import { apiGet } from "../api/client";
import type { LiveTimingRow } from "../api/types";
import { C, FALLBACK_TRACK_PATH, T } from "../theme";
import { Chip } from "./atoms";
import { useAsync } from "../hooks/useAsync";

type PathResp = {
  points: { x: number; y: number }[];
  estimated: boolean;
};

function pointsToD(points: { x: number; y: number }[]): string {
  if (points.length < 2) return FALLBACK_TRACK_PATH;
  return points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ") + " Z";
}

export function TrackMap({
  year,
  round,
  sessionType,
  cars,
  focusCode,
  hiddenCars,
  livePositions,
}: {
  year: number;
  round: number;
  sessionType: string;
  cars: LiveTimingRow[];
  focusCode?: string;
  hiddenCars: string[];
  livePositions?: { driver_code: string; x: number; y: number; team_colour?: string | null }[];
}) {
  const pathRef = useRef<SVGPathElement | null>(null);
  const carRefs = useRef<Map<string, SVGGElement>>(new Map());
  const tRef = useRef(0);
  const path = useAsync(
    () =>
      apiGet<PathResp>(`/api/session/${year}/${round}/${sessionType}/circuit-path`, { timeout: 120_000 }),
    [year, round, sessionType],
  );
  const d = path.status === "ok" && path.data.points.length > 2 ? pointsToD(path.data.points) : FALLBACK_TRACK_PATH;
  const estimated = path.status !== "ok" || path.data.estimated || (path.data.points.length < 2);

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const el = pathRef.current;
      if (el) {
        const len = el.getTotalLength();
        tRef.current += 0.002;
        cars.forEach((car, i) => {
          if (hiddenCars.includes(car.driver_code)) return;
          const live = livePositions?.find((p) => p.driver_code === car.driver_code);
          const g = carRefs.current.get(car.driver_code);
          if (!g) return;
          if (live) {
            g.setAttribute("transform", `translate(${live.x}, ${live.y})`);
          } else {
            const frac = (tRef.current * (0.9 - i * 0.02) + i * 0.03) % 1;
            const pt = el.getPointAtLength(frac * len);
            g.setAttribute("transform", `translate(${pt.x}, ${pt.y})`);
          }
        });
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [cars, hiddenCars, livePositions]);

  return (
    <div style={{ height: "100%", position: "relative" }}>
      {estimated && (
        <div style={{ position: "absolute", top: 6, left: 8, zIndex: 2 }}>
          <Chip tone="signal" size="xs">
            ESTIMATED LAYOUT
          </Chip>
        </div>
      )}
      <svg viewBox="0 0 440 280" style={{ width: "100%", height: "100%" }}>
        <path d={d} fill="none" stroke={C.borderHi} strokeWidth={14} ref={pathRef} />
        <path d={d} fill="none" stroke={C.panel2} strokeWidth={8} />
        <path d={d} fill="none" stroke={C.faint} strokeWidth={1} strokeDasharray="4 6" />
        {cars
          .filter((c) => !hiddenCars.includes(c.driver_code))
          .map((car) => (
            <g
              key={car.driver_code}
              ref={(n) => {
                if (n) carRefs.current.set(car.driver_code, n);
                else carRefs.current.delete(car.driver_code);
              }}
            >
              {car.driver_code === focusCode && (
                <circle r={10} fill="none" stroke={C.signal} strokeWidth={1} opacity={0.7} />
              )}
              <circle r={5} fill={car.team_colour || C.signal} />
              <text
                y={-8}
                textAnchor="middle"
                fill={C.paper}
                style={{ fontFamily: T.mono, fontSize: 8, fontWeight: 700 }}
              >
                {car.driver_code}
              </text>
            </g>
          ))}
      </svg>
    </div>
  );
}
