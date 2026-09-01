import {
  headingAtFraction,
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

/** Signed along-track delta. S/F wrap stays forward; large forward jumps are not treated as reverse. */
export function wrappedDelta(from: number, to: number): number {
  let d = to - from;
  if (d < -0.5) d += 1;
  return d;
}

export interface PathTickKinematics {
  /** Speed in km/h; unused for motion (kept for API compat). */
  speedKph?: number | null;
  headingRad?: number | null;
  /** Skip SEEK_JUMP snap (ghost grace after lights-out or a pit). */
  skipSeekJump?: boolean;
  /** User scrub / session change — only then may we teleport. */
  seek?: boolean;
  /** Force visFrac onto the target (playback speed change). */
  snap?: boolean;
  playbackSpeed?: number;
}

export const GPS_HOLD_MS = 100;
/** Catch-up cap at high speed (~0.08 lap/s at 1×). Scaled by playbackSpeed. */
export const BASE_MAX_FRAC_PER_MS = 0.00008;
export const SEEK_JUMP = 0.22;
/** 1×: allow a GPS-sized bump per frame, not a hole-teleport. */
export const BUMP_MAX_FRAC = 0.012;

/** Interpolate along a circuit path so dots stay on the racing line. */
export class PathCarAnimator {
  private lastFrac: number;
  private visFrac: number;
  private lastTickAt = 0;
  private lastVisAt = 0;
  private easeMs: number;
  private path: PathData;
  private playbackSpeed = 1;

  constructor(path: PathData, initialFrac = 0, easeMs = 140) {
    this.path = path;
    this.lastFrac = wrap01(initialFrac);
    this.visFrac = this.lastFrac;
    this.easeMs = easeMs;
  }

  setPath(path: PathData) {
    this.path = path;
  }

  onTick(frac: number, now: number, kinematics?: PathTickKinematics) {
    const target = wrap01(frac);
    const nextSpeed =
      kinematics?.playbackSpeed != null && Number.isFinite(kinematics.playbackSpeed)
        ? Math.max(0.25, kinematics.playbackSpeed)
        : this.playbackSpeed;
    const speedDropped = nextSpeed < this.playbackSpeed - 1e-6;
    this.playbackSpeed = nextSpeed;

    if (kinematics?.snap || speedDropped) {
      this.lastFrac = target;
      this.visFrac = target;
      this.lastTickAt = now;
      this.lastVisAt = now;
      return;
    }

    const d = wrappedDelta(this.visFrac, target);
    if (Math.abs(d) < 1e-6 && Math.abs(wrappedDelta(this.lastFrac, target)) < 1e-6) return;

    const jump = Math.abs(d);
    const allowSeek = Boolean(kinematics?.seek) && !kinematics?.skipSeekJump;
    if (jump > SEEK_JUMP && allowSeek) {
      this.lastFrac = target;
      this.visFrac = target;
      this.lastTickAt = now;
      this.lastVisAt = now;
      return;
    }

    this.lastFrac = target;
    this.lastTickAt = now;
  }

  currentFrac(now: number, playing = true): number {
    const frameDt = this.lastVisAt > 0 ? Math.max(1, now - this.lastVisAt) : 16.67;
    this.lastVisAt = now;
    if (!playing) return this.visFrac;

    const speed = Math.max(0.25, this.playbackSpeed);
    const d = wrappedDelta(this.visFrac, this.lastFrac);
    const dt = Math.min(frameDt, 48);
    let step: number;
    if (speed <= 1) {
      // Follow the timing/GPS target closely so 1× reads as small natural bumps,
      // not a lagged ease. Still cap a hole so a bad sample cannot teleport.
      step = d * 0.72;
      const maxBump = BUMP_MAX_FRAC * (dt / 16.67);
      if (Math.abs(step) > maxBump) step = Math.sign(d) * maxBump;
    } else {
      const ease = 1 - Math.pow(1 - 0.18, dt / 16.67);
      step = d * Math.min(1, ease);
      const maxStep = BASE_MAX_FRAC_PER_MS * speed * dt;
      if (frameDt <= 48 && Math.abs(step) > maxStep) {
        step = Math.sign(d) * maxStep;
      }
    }
    this.visFrac = wrap01(this.visFrac + step);
    return this.visFrac;
  }

  currentPosition(now: number, playing = true): Point & { heading: number; frac: number } {
    const frac = this.currentFrac(now, playing);
    const pos = pointAtFraction(this.path, frac);
    return { ...pos, heading: headingAtFraction(this.path, frac), frac };
  }
}
