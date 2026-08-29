export interface PathSegment {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  len: number;
  cumFrac: number;
}

export interface PathData {
  segments: PathSegment[];
  totalLength: number;
}

export function buildPath(xs: number[], ys: number[]): PathData {
  const n = Math.min(xs.length, ys.length);
  if (n < 2) return { segments: [], totalLength: 0 };
  const closedX = [...xs.slice(0, n), xs[0]];
  const closedY = [...ys.slice(0, n), ys[0]];
  const lens: number[] = [];
  let total = 0;
  for (let i = 0; i < closedX.length - 1; i++) {
    const len = Math.hypot(closedX[i + 1] - closedX[i], closedY[i + 1] - closedY[i]);
    lens.push(len);
    total += len;
  }
  const segments: PathSegment[] = [];
  let cum = 0;
  for (let i = 0; i < closedX.length - 1; i++) {
    segments.push({
      x1: closedX[i],
      y1: closedY[i],
      x2: closedX[i + 1],
      y2: closedY[i + 1],
      len: lens[i],
      cumFrac: total > 0 ? cum / total : 0,
    });
    cum += lens[i];
  }
  return { segments, totalLength: total };
}

function wrap01(f: number): number {
  return ((f % 1) + 1) % 1;
}

export { wrap01 };

export function pointAtFraction(path: PathData, frac: number): { x: number; y: number } {
  if (!path.segments.length) return { x: 0, y: 0 };
  const f = wrap01(frac);
  let lo = 0;
  let hi = path.segments.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (path.segments[mid].cumFrac <= f) lo = mid;
    else hi = mid - 1;
  }
  const seg = path.segments[lo];
  const next = lo < path.segments.length - 1 ? path.segments[lo + 1].cumFrac : 1;
  const span = next > seg.cumFrac ? next - seg.cumFrac : 1;
  const u = span > 0 ? (f - seg.cumFrac) / span : 0;
  return { x: seg.x1 + u * (seg.x2 - seg.x1), y: seg.y1 + u * (seg.y2 - seg.y1) };
}

export function headingAtFraction(path: PathData, frac: number): number {
  const a = pointAtFraction(path, frac - 0.002);
  const b = pointAtFraction(path, frac + 0.002);
  return Math.atan2(b.y - a.y, b.x - a.x);
}

export function fractionAtPoint(path: PathData, x: number, y: number): number {
  if (!path.segments.length) return 0;
  let bestFrac = 0;
  let bestD = Infinity;
  for (let i = 0; i < path.segments.length; i++) {
    const seg = path.segments[i];
    const dx = seg.x2 - seg.x1;
    const dy = seg.y2 - seg.y1;
    const len2 = dx * dx + dy * dy || 1;
    let u = ((x - seg.x1) * dx + (y - seg.y1) * dy) / len2;
    u = Math.max(0, Math.min(1, u));
    const px = seg.x1 + u * dx;
    const py = seg.y1 + u * dy;
    const d = (px - x) ** 2 + (py - y) ** 2;
    if (d < bestD) {
      bestD = d;
      const next = i + 1 < path.segments.length ? path.segments[i + 1].cumFrac : 1;
      const span = next > seg.cumFrac ? next - seg.cumFrac : 1 - seg.cumFrac;
      bestFrac = wrap01(seg.cumFrac + u * (span > 0 ? span : 0));
    }
  }
  return bestFrac;
}

export function lerpFrac(a: number, b: number, u: number): number {
  let d = b - a;
  if (d > 0.5) d -= 1;
  if (d < -0.5) d += 1;
  return wrap01(a + d * Math.max(0, Math.min(1, u)));
}

export function polylinePoints(xs: number[], ys: number[]): string {
  const n = Math.min(xs.length, ys.length);
  const parts: string[] = [];
  for (let i = 0; i < n; i++) parts.push(`${xs[i]},${ys[i]}`);
  return parts.join(" ");
}

export interface SectorSplit {
  kind: "s1" | "s2" | "s3";
  label: string;
  x: number[];
  y: number[];
}

function sliceClosed(xs: number[], ys: number[], i0: number, i1: number): { x: number[]; y: number[] } {
  const n = Math.min(xs.length, ys.length);
  if (n < 2) return { x: [], y: [] };
  if (i1 >= i0) return { x: xs.slice(i0, i1 + 1), y: ys.slice(i0, i1 + 1) };
  return { x: xs.slice(i0).concat(xs.slice(0, i1 + 1)), y: ys.slice(i0).concat(ys.slice(0, i1 + 1)) };
}

function nearestIndex(xs: number[], ys: number[], x: number, y: number): number {
  let best = 0;
  let bestD = Infinity;
  const n = Math.min(xs.length, ys.length);
  for (let i = 0; i < n; i++) {
    const d = (xs[i] - x) ** 2 + (ys[i] - y) ** 2;
    if (d < bestD) {
      bestD = d;
      best = i;
    }
  }
  return best;
}

function indexAtDistanceFrac(path: PathData, frac: number): number {
  if (!path.segments.length) return 0;
  const f = wrap01(frac);
  let lo = 0;
  let hi = path.segments.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (path.segments[mid].cumFrac <= f) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

/**
 * Split a racing-line polyline into S1/S2/S3 by distance along the track.
 * Uses FastF1 marshal markers when they project to a valid order; otherwise
 * equal-distance thirds.
 */
export function sectorPathsFromOutline(
  xs: number[],
  ys: number[],
  markers?: { kind: string; x: number; y: number }[] | null,
): { paths: SectorSplit[]; usedFallback: boolean } {
  const n = Math.min(xs.length, ys.length);
  if (n < 4) return { paths: [], usedFallback: true };
  const path = buildPath(xs, ys);

  const byKind = new Map((markers ?? []).map((m) => [m.kind.toLowerCase(), m]));
  let i1: number | null = null;
  let i2: number | null = null;
  const s1 = byKind.get("s1");
  const s2 = byKind.get("s2");
  if (s1) i1 = nearestIndex(xs, ys, s1.x, s1.y);
  if (s2) i2 = nearestIndex(xs, ys, s2.x, s2.y);

  let usedFallback = false;
  if (i1 == null || i2 == null || !(0 < i1 && i1 < i2 && i2 < n - 1)) {
    usedFallback = true;
    i1 = indexAtDistanceFrac(path, 1 / 3);
    i2 = indexAtDistanceFrac(path, 2 / 3);
    if (!(0 < i1 && i1 < i2 && i2 < n - 1)) {
      i1 = Math.max(1, Math.floor(n / 3));
      i2 = Math.max(i1 + 1, Math.floor((2 * n) / 3));
    }
  }

  const a = sliceClosed(xs, ys, 0, i1);
  const b = sliceClosed(xs, ys, i1, i2);
  const c = sliceClosed(xs, ys, i2, n - 1);
  if (!c.x.length || c.x[c.x.length - 1] !== xs[0] || c.y[c.y.length - 1] !== ys[0]) {
    c.x = [...c.x, xs[0]];
    c.y = [...c.y, ys[0]];
  }
  return {
    usedFallback,
    paths: [
      { kind: "s1", label: "S1", x: a.x, y: a.y },
      { kind: "s2", label: "S2", x: b.x, y: b.y },
      { kind: "s3", label: "S3", x: c.x, y: c.y },
    ],
  };
}

export function sectorsAreUsable(paths: { x: number[]; y: number[] }[] | undefined | null): boolean {
  if (!paths || paths.length < 3) return false;
  return paths.every((p) => p.x.length >= 2 && p.y.length >= 2 && p.x.length === p.y.length);
}

export function viewBoxFor(xs: number[], ys: number[], pad = 24): string {
  if (!xs.length || !ys.length) return "0 0 800 500";
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return `${minX - pad} ${minY - pad} ${maxX - minX + pad * 2} ${maxY - minY + pad * 2}`;
}
