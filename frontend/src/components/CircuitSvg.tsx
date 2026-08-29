import type { ReactNode } from "react";
import type { CircuitMap } from "../api/types";
import { C, T } from "../theme";

export function polylinePoints(map: CircuitMap): string {
  if (!map.x.length) return "";
  const pts = map.x.map((x, i) => `${x},${map.y[i]}`);
  const last = map.x.length - 1;
  if (map.x[0] !== map.x[last] || map.y[0] !== map.y[last]) {
    pts.push(`${map.x[0]},${map.y[0]}`);
  }
  return pts.join(" ");
}

function slicePath(map: CircuitMap, a: number, b: number): string {
  const lo = Math.min(a, b);
  const hi = Math.max(a, b);
  const slice = map.x.slice(lo, hi + 1);
  const ys = map.y.slice(lo, hi + 1);
  return slice.map((x, j) => `${x},${ys[j]}`).join(" ");
}

function nearestIndex(map: CircuitMap, x: number, y: number): number {
  let best = 0;
  let bestD = Infinity;
  const n = Math.min(map.x.length, map.y.length);
  for (let i = 0; i < n; i++) {
    const dx = map.x[i] - x;
    const dy = map.y[i] - y;
    const d = dx * dx + dy * dy;
    if (d < bestD) {
      bestD = d;
      best = i;
    }
  }
  return best;
}

function sectorSplits(map: CircuitMap): [number, number, number, number] {
  const n = Math.max(1, Math.min(map.x.length, map.y.length) - 1);
  const marks = (map.markers || []).filter((m) => m.kind === "s1" || m.kind === "s2");
  const s1 = marks.find((m) => m.kind === "s1");
  const s2 = marks.find((m) => m.kind === "s2");
  const i1 = s1 ? nearestIndex(map, s1.x, s1.y) : Math.round(n / 3);
  const i2 = s2 ? nearestIndex(map, s2.x, s2.y) : Math.round((2 * n) / 3);
  const a = Math.max(1, Math.min(i1, i2, n - 1));
  const b = Math.max(a + 1, Math.min(Math.max(i1, i2), n));
  return [0, a, b, n];
}

function ChequeredFlag({ map }: { map: CircuitMap }) {
  const sf = (map.markers || []).find((m) => m.kind === "sf");
  const i = sf ? nearestIndex(map, sf.x, sf.y) : 0;
  const x = map.x[i] ?? 0;
  const y = map.y[i] ?? 0;
  const prev = Math.max(0, i - 1);
  const next = Math.min(map.x.length - 1, i + 1);
  let tx = (map.x[next] ?? x) - (map.x[prev] ?? x);
  let ty = (map.y[next] ?? y) - (map.y[prev] ?? y);
  const tlen = Math.hypot(tx, ty) || 1;
  tx /= tlen;
  ty /= tlen;
  const nx = -ty;
  const ny = tx;
  const across = 8;
  const along = 3;
  const cell = 1.85;
  const squares: { key: string; x: number; y: number; fill: string }[] = [];
  for (let r = 0; r < along; r++) {
    for (let c = 0; c < across; c++) {
      const u = (c - (across - 1) / 2) * cell;
      const v = (r - (along - 1) / 2) * cell;
      squares.push({
        key: `${r}-${c}`,
        x: x + nx * u + tx * v - cell / 2,
        y: y + ny * u + ty * v - cell / 2,
        fill: (r + c) % 2 === 0 ? "#F4F6F8" : "#0B0D10",
      });
    }
  }
  return (
    <g>
      {squares.map((s) => (
        <rect key={s.key} x={s.x} y={s.y} width={cell} height={cell} fill={s.fill} />
      ))}
    </g>
  );
}

export function CircuitOutline({
  map,
  width = "100%",
  height = "100%",
  showCorners = false,
  showSectors = false,
  showDrs = false,
  showGrid = false,
  showPit = false,
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
  showGrid?: boolean;
  showPit?: boolean;
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
      <polyline points={pts} fill="none" stroke={C.borderHi} strokeWidth={16} strokeLinejoin="round" strokeLinecap="round" />
      <polyline points={pts} fill="none" stroke="#161C24" strokeWidth={11} strokeLinejoin="round" strokeLinecap="round" />
      <polyline points={pts} fill="none" stroke="#3A4554" strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" opacity={0.95} />
      {showSectors && (() => {
        const [a, b, c, d] = sectorSplits(map);
        const segs: [number, number, string][] = [
          [a, b, C.purple],
          [b, c, C.green],
          [c, d, C.blue],
        ];
        return segs.map(([lo, hi, col], i) =>
          hi > lo ? (
            <polyline
              key={`sec-${i}`}
              points={slicePath(map, lo, hi)}
              fill="none"
              stroke={col}
              strokeWidth={3.2}
              strokeLinejoin="round"
              strokeLinecap="round"
              opacity={0.85}
            />
          ) : null,
        );
      })()}
      {showPit && map.pit_lane_x && map.pit_lane_x.length >= 2 && (
        <>
          <polyline
            points={map.pit_lane_x.map((x, i) => `${x},${map.pit_lane_y?.[i] ?? 0}`).join(" ")}
            fill="none"
            stroke="#C9A227"
            strokeWidth={5}
            strokeLinejoin="round"
            strokeLinecap="round"
            opacity={0.9}
          />
          <polyline
            points={map.pit_lane_x.map((x, i) => `${x},${map.pit_lane_y?.[i] ?? 0}`).join(" ")}
            fill="none"
            stroke={C.ink}
            strokeWidth={1.5}
            strokeDasharray="3 4"
            opacity={0.7}
          />
        </>
      )}
      {showDrs &&
        (map.drs_segments || []).map((seg, i) => {
          const [a, b] = seg;
          if (a <= b) {
            return <polyline key={`drs-${i}`} points={slicePath(map, a, b)} fill="none" stroke={C.green} strokeWidth={5} opacity={0.75} />;
          }
          return (
            <g key={`drs-${i}`}>
              <polyline points={slicePath(map, a, map.x.length - 1)} fill="none" stroke={C.green} strokeWidth={5} opacity={0.75} />
              <polyline points={slicePath(map, 0, b)} fill="none" stroke={C.green} strokeWidth={5} opacity={0.75} />
            </g>
          );
        })}
      {map.x.length >= 2 && <ChequeredFlag map={map} />}
      {showPit &&
        (map.markers || [])
          .filter((m) => m.kind === "pit_in" || m.kind === "pit_out")
          .map((m) => (
            <g key={m.kind}>
              <rect x={m.x - 3} y={m.y - 3} width={6} height={6} fill="#C9A227" />
              <text x={m.x + 7} y={m.y - 6} fill="#C9A227" style={{ fontFamily: T.mono, fontSize: 7 }}>
                {m.label}
              </text>
            </g>
          ))}
      {showDrs &&
        (map.markers || [])
          .filter((m) => m.kind === "drs_detect")
          .map((m, i) => (
            <g key={`det-${i}`}>
              <polygon
                points={`${m.x},${m.y - 7} ${m.x + 6},${m.y} ${m.x},${m.y + 7} ${m.x - 6},${m.y}`}
                fill={C.green}
                stroke={C.ink}
                strokeWidth={0.8}
              />
              <text x={m.x + 8} y={m.y + 3} fill={C.green} style={{ fontFamily: T.mono, fontSize: 7 }}>
                DRS DET
              </text>
            </g>
          ))}
      {showGrid &&
        (map.markers || [])
          .filter((m) => m.kind === "grid")
          .map((m) => (
            <rect
              key={m.label}
              x={m.x - 3}
              y={m.y - 2}
              width={6}
              height={4}
              fill="none"
              stroke={C.faint}
              strokeWidth={0.8}
              opacity={0.55}
            />
          ))}
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
    <svg viewBox="0 0 440 280" preserveAspectRatio="xMidYMid meet" style={{ width, height, display: "block" }}>
      {inner}
    </svg>
  );
}

export function TrackMapKey({ showDrs = false, showSectors = true }: { showDrs?: boolean; showSectors?: boolean }) {
  const item = (swatch: ReactNode, label: string) => (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      {swatch}
      <span>{label}</span>
    </div>
  );
  return (
    <div
      style={{
        position: "absolute",
        right: 8,
        bottom: 8,
        zIndex: 4,
        background: `${C.raised}E6`,
        border: `1px solid ${C.border}`,
        padding: "7px 9px",
        borderRadius: 4,
        fontFamily: T.mono,
        fontSize: 8,
        color: C.mist,
        display: "flex",
        flexDirection: "column",
        gap: 4,
        letterSpacing: "0.04em",
        pointerEvents: "none",
      }}
    >
      {item(
        <span style={{ width: 14, height: 8, background: "repeating-conic-gradient(#F4F6F8 0% 25%, #12151A 0% 50%)", display: "inline-block" }} />,
        "START / FINISH",
      )}
      {showSectors && item(<span style={{ width: 14, height: 3, background: C.purple, display: "inline-block" }} />, "SECTOR 1")}
      {showSectors && item(<span style={{ width: 14, height: 3, background: C.green, display: "inline-block" }} />, "SECTOR 2")}
      {showSectors && item(<span style={{ width: 14, height: 3, background: C.blue, display: "inline-block" }} />, "SECTOR 3")}
      {showDrs &&
        item(
          <span
            style={{
              width: 8,
              height: 8,
              background: C.green,
              display: "inline-block",
              transform: "rotate(45deg)",
            }}
          />,
          "DRS DETECTION",
        )}
      {showDrs && item(<span style={{ width: 14, height: 3, background: C.green, display: "inline-block" }} />, "DRS ZONE")}
    </div>
  );
}
