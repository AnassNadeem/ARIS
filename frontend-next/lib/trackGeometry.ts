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

export function viewBoxFor(xs: number[], ys: number[], pad = 24): string {
  if (!xs.length || !ys.length) return "0 0 800 500";
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return `${minX - pad} ${minY - pad} ${maxX - minX + pad * 2} ${maxY - minY + pad * 2}`;
}
