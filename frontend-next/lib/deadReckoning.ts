// Position interpolation for the track map's 60fps requestAnimationFrame
// loop. Cars extrapolate forward from the last known tick using speed +
// heading, then ease onto the next real tick over ~200ms instead of
// teleporting.

export interface Point {
  x: number;
  y: number;
}

/**
 * Dead-reckon a car's position forward by deltaT milliseconds given its
 * last known position, speed (px/s, already scaled to map units), and
 * heading in radians.
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
