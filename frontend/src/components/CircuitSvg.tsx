import type { CircuitMap } from "../api/types";
import { C, T } from "../theme";

export function polylinePoints(map: CircuitMap): string {
  return map.x.map((x, i) => `${x},${map.y[i]}`).join(" ");
}

export function CircuitOutline({
  map,
  width = "100%",
  height = "100%",
  showCorners = false,
  showSectors = false,
  showDrs = false,
  onCornerHover,
  embedded = false,
  quietUnavailable = false,
}: {
  map: CircuitMap;
  width?: string | number;
  height?: string | number;
  showCorners?: boolean;
  showSectors?: boolean;
  showDrs?: boolean;
  onCornerHover?: (text: string | null, x: number, y: number) => void;
  embedded?: boolean;
  quietUnavailable?: boolean;
}) {
  const pts = polylinePoints(map);
  const unavailable = !map.available || map.fallback || map.x.length < 2;
  const inner = unavailable ? (
    <>
      <ellipse cx={220} cy={140} rx={150} ry={80} fill="none" stroke={C.border} strokeWidth={10} />
      <ellipse cx={220} cy={140} rx={150} ry={80} fill="none" stroke={C.faint} strokeWidth={2} strokeDasharray="6 6" />
      <text x={220} y={145} textAnchor="middle" fill={C.mist} style={{ fontFamily: T.mono, fontSize: 12 }}>
        {quietUnavailable ? "Loading…" : "[CIRCUIT MAP UNAVAILABLE]"}
      </text>
    </>
  ) : (
    <>
      <polyline points={pts} fill="none" stroke={C.borderHi} strokeWidth={14} strokeLinejoin="round" />
      <polyline points={pts} fill="none" stroke={C.panel2} strokeWidth={8} strokeLinejoin="round" />
      <polyline points={pts} fill="none" stroke={C.faint} strokeWidth={1} strokeDasharray="4 6" />
      {showDrs &&
        (map.drs_segments || []).map((seg, i) => {
          const [a, b] = seg;
          const slice = map.x.slice(Math.min(a, b), Math.max(a, b) + 1);
          const ys = map.y.slice(Math.min(a, b), Math.max(a, b) + 1);
          const d = slice.map((x, j) => `${x},${ys[j]}`).join(" ");
          return <polyline key={i} points={d} fill="none" stroke={C.green} strokeWidth={4} opacity={0.7} />;
        })}
      {showSectors &&
        (map.markers || [])
          .filter((m) => m.kind === "s1" || m.kind === "s2" || m.kind === "s3")
          .map((m) => (
            <g key={m.kind}>
              <circle
                cx={m.x}
                cy={m.y}
                r={5}
                fill={m.kind === "s1" ? C.purple : m.kind === "s2" ? C.green : C.blue}
              />
              <text x={m.x + 8} y={m.y - 6} fill={C.paper} style={{ fontFamily: T.mono, fontSize: 8 }}>
                {m.label}
              </text>
            </g>
          ))}
      {showCorners &&
        map.corners.map((c) => (
          <g
            key={c.number}
            onMouseEnter={(e) => {
              const r = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
              onCornerHover?.(
                `T${c.number}${c.letter || ""}${c.description ? ` · ${c.description}` : ""}`,
                e.clientX - r.left,
                e.clientY - r.top,
              );
            }}
            onMouseLeave={() => onCornerHover?.(null, 0, 0)}
          >
            <circle cx={c.x} cy={c.y} r={4} fill={C.signal} />
            <text x={c.x + 6} y={c.y - 6} fill={C.paper} style={{ fontFamily: T.mono, fontSize: 8 }}>
              {c.number}
              {c.letter || ""}
            </text>
          </g>
        ))}
    </>
  );
  if (embedded) return inner;
  return (
    <svg viewBox="0 0 440 280" style={{ width, height, display: "block" }}>
      {inner}
    </svg>
  );
}
