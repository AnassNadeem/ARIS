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

/**
 * Signed along-track delta on a 0–1 lap.
 * S/F wrap is forward: wrappedDelta(0.97, 0.03) === +0.06, not −0.94
 * (`d = −0.94 < −0.5` → `d += 1`). A >0.5 forward GPS hole stays forward
 * so cars are not animated backwards across half the circuit.
 */
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
/** Live 1 Hz GPS: interpolate gaps up to ~0.45 lap; snap only beyond that. */
export const SEEK_JUMP_LIVE = 0.45;
/** 1×: allow a GPS-sized bump per frame, not a hole-teleport. */
export const BUMP_MAX_FRAC = 0.012;
/** Live SSE / OpenF1 poll slot — interpolate across the full second. */
export const LIVE_TICK_INTERVAL_MS = 1000;
/** Replay frame poll cadence. */
export const REPLAY_TICK_INTERVAL_MS = 250;
/** Finish ~90% of a tick's travel before the next sample arrives. */
const TRAVEL_FRAC_OF_INTERVAL = 0.85;
/** Live: 90% of the way to the target in 0.9 s (just before the next 1 Hz tick). */
const LIVE_TRAVEL_MS = 900;

function seekJumpThreshold(tickIntervalMs: number): number {
  return tickIntervalMs === LIVE_TICK_INTERVAL_MS ? SEEK_JUMP_LIVE : SEEK_JUMP;
}

/** Interpolate along a circuit path so dots stay on the racing line. */
export class PathCarAnimator {
  private lastFrac: number;
  private visFrac: number;
  private lastTickAt = 0;
  private lastVisAt = 0;
  private easeMs: number;
  private tickIntervalMs: number;
  private path: PathData;
  private playbackSpeed = 1;

  constructor(
    path: PathData,
    initialFrac = 0,
    easeMs = 140,
    tickIntervalMs = REPLAY_TICK_INTERVAL_MS,
  ) {
    this.path = path;
    this.lastFrac = wrap01(initialFrac);
    this.visFrac = this.lastFrac;
    this.easeMs = easeMs;
    this.tickIntervalMs = Math.max(1, tickIntervalMs);
  }

  setPath(path: PathData) {
    this.path = path;
  }

  setTickInterval(ms: number) {
    if (!Number.isFinite(ms) || ms <= 0) return;
    this.tickIntervalMs = ms;
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
    const toLast = wrappedDelta(this.lastFrac, target);
    if (Math.abs(d) < 1e-6 && Math.abs(toLast) < 1e-6) return;

    const jump = Math.abs(d);
    const allowSeek = Boolean(kinematics?.seek) && !kinematics?.skipSeekJump;
    if (jump > seekJumpThreshold(this.tickIntervalMs) && allowSeek) {
      this.lastFrac = target;
      this.visFrac = target;
      this.lastTickAt = now;
      this.lastVisAt = now;
      return;
    }

    // Same GPS sample re-fed every rAF: keep the in-flight glide; do not restart the window.
    if (Math.abs(toLast) < 1e-6) return;

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
      // Live 1Hz: 90% of travel in 0.9s. Replay: ~0.85× the 250ms tick.
      const travelMs =
        this.tickIntervalMs === LIVE_TICK_INTERVAL_MS
          ? LIVE_TRAVEL_MS
          : Math.max(80, this.tickIntervalMs * TRAVEL_FRAC_OF_INTERVAL);
      const k = -Math.log(0.1) / travelMs;
      const ease = 1 - Math.exp(-k * dt);
      step = d * Math.min(1, ease);
      if (Math.abs(d) > seekJumpThreshold(this.tickIntervalMs)) {
        const maxHole = BASE_MAX_FRAC_PER_MS * speed * dt;
        if (Math.abs(step) > maxHole) step = Math.sign(d) * maxHole;
      }
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
