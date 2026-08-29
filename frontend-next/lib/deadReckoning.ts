import {
  headingAtFraction,
  lerpFrac,
  pointAtFraction,
  wrap01,
  type PathData,
} from "@/lib/trackGeometry";

// Position interpolation for the track map's 60fps requestAnimationFrame
// loop. Cars stay on the racing line: we interpolate distance-along-track
// (path fraction) between the last two GPS ticks and ease over ~0.9 s to
// match ~1 Hz telemetry. Cartesian dead-reckoning is not used for on-track dots.

export interface Point {
  x: number;
  y: number;
}

/**
 * Dead-reckon a car's position forward by deltaT milliseconds given its
 * last known position, speed (px/s, already scaled to map units), and
 * heading in radians. Kept for tests / off-track overlays — map dots use
 * PathCarAnimator instead.
 */
export function interpolate(
  lastPos: Point,
  speed: number,
  heading: number,
  deltaT: number,
): Point {
  const dtSeconds = deltaT / 1000;
  const dx = speed * Math.cos(heading) * dtSeconds;
  const dy = speed * Math.sin(heading) * dtSeconds;
  return { x: lastPos.x + dx, y: lastPos.y + dy };
}

/** Linear interpolation between two points, u in [0, 1]. */
export function lerpPoint(a: Point, b: Point, u: number): Point {
  const t = Math.max(0, Math.min(1, u));
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
}

export function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

/**
 * Tracks one car's animated position across ticks: dead-reckons between
 * ticks, then eases onto the newly-received true position over
 * `easeMs` milliseconds so the dot never teleports.
 */
export class CarAnimator {
  private lastTickPos: Point;
  private easeFromPos: Point;
  private easeStartedAt = 0;
  private easeMs: number;
  private speed = 0;
  private heading = 0;
  private lastTickAt = 0;

  constructor(initial: Point, easeMs = 200) {
    this.lastTickPos = initial;
    this.easeFromPos = initial;
    this.easeMs = easeMs;
  }

  /** Feed a new real tick (true position + kinematics for future dead-reckoning). */
  onTick(truePos: Point, speed: number, heading: number, now: number) {
    this.easeFromPos = this.currentPosition(now);
    this.easeStartedAt = now;
    this.lastTickPos = truePos;
    this.speed = speed;
    this.heading = heading;
    this.lastTickAt = now;
  }

  /** Call every animation frame to get the position to render right now. */
  currentPosition(now: number): Point {
    const easeElapsed = now - this.easeStartedAt;
    if (this.easeStartedAt > 0 && easeElapsed < this.easeMs) {
      const u = easeInOutCubic(easeElapsed / this.easeMs);
      return lerpPoint(this.easeFromPos, this.deadReckonedTarget(now), u);
    }
    return this.deadReckonedTarget(now);
  }

  private deadReckonedTarget(now: number): Point {
    const dt = now - this.lastTickAt;
    if (dt <= 0) return this.lastTickPos;
    return interpolate(this.lastTickPos, this.speed, this.heading, dt);
  }
}

function wrappedDelta(from: number, to: number): number {
  let d = to - from;
  if (d > 0.5) d -= 1;
  if (d < -0.5) d += 1;
  return d;
}

export interface PathTickKinematics {
  /** Speed in km/h; used only to cap / sign along-track velocity. */
  speedKph?: number | null;
  headingRad?: number | null;
}

const MAX_FRAC_PER_MS = 0.00012; // ~0.12 lap/s — well above race pace, below teleport
const SEEK_JUMP = 0.22;

/** Interpolate along a circuit path so dots stay on the racing line. */
export class PathCarAnimator {
  private lastFrac: number;
  private prevFrac: number;
  private visFrac: number;
  private lastTickAt = 0;
  private lastVisAt = 0;
  private vel = 0;
  private easeMs: number;
  private path: PathData;

  constructor(path: PathData, initialFrac = 0, easeMs = 140) {
    this.path = path;
    this.lastFrac = wrap01(initialFrac);
    this.prevFrac = this.lastFrac;
    this.visFrac = this.lastFrac;
    this.easeMs = easeMs;
  }

  setPath(path: PathData) {
    this.path = path;
  }

  onTick(frac: number, now: number, kinematics?: PathTickKinematics) {
    const target = wrap01(frac);
    const d = wrappedDelta(this.lastFrac, target);
    if (Math.abs(d) < 1e-5) return;

    const jump = Math.abs(d);
    if (jump > SEEK_JUMP) {
      // Seek / new session — snap onto the line instead of interpolating the long way.
      this.lastFrac = target;
      this.prevFrac = target;
      this.visFrac = target;
      this.vel = 0;
      this.lastTickAt = now;
      this.lastVisAt = now;
      return;
    }

    if (this.lastTickAt > 0 && now > this.lastTickAt) {
      let v = d / (now - this.lastTickAt);
      const speed = kinematics?.speedKph;
      if (speed != null && speed < 8) v *= 0.15;
      if (speed != null && speed > 8 && v < 0) v = Math.abs(v);
      this.vel = Math.max(-MAX_FRAC_PER_MS, Math.min(MAX_FRAC_PER_MS, v));
    }
    this.prevFrac = this.lastFrac;
    this.lastFrac = target;
    this.lastTickAt = now;
  }

  currentFrac(now: number, playing = true): number {
    const dt = playing ? Math.min(280, Math.max(0, now - this.lastTickAt)) : 0;
    const step = wrappedDelta(this.prevFrac, this.lastFrac);
    const maxExtra = Math.max(0.004, Math.abs(step) * 1.2);
    const extra = Math.max(-maxExtra, Math.min(maxExtra, this.vel * dt));
    const target = wrap01(this.lastFrac + extra);
    const frameDt = this.lastVisAt > 0 ? Math.max(1, now - this.lastVisAt) : 16.67;
    this.lastVisAt = now;
    // 0.12 per 16.67ms (~8 frames to the target at 60fps). Time-scale so tests with large dt still catch up.
    const ease = 1 - Math.pow(1 - 0.12, Math.min(frameDt, this.easeMs) / 16.67);
    this.visFrac = lerpFrac(this.visFrac, target, Math.min(1, ease));
    return this.visFrac;
  }

  currentPosition(now: number, playing = true): Point & { heading: number; frac: number } {
    const frac = this.currentFrac(now, playing);
    const pos = pointAtFraction(this.path, frac);
    return { ...pos, heading: headingAtFraction(this.path, frac), frac };
  }
}
