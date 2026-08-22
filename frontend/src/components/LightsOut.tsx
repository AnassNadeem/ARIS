import { useEffect, useRef, useState } from "react";
import { C, T } from "../theme";

const LIGHT_MS = 420;
const HOLD_MS = 700;

/** F1 gantry: five reds in sequence, then lights out. Sits just above the track. */
export function LightsOut({ play, onComplete }: { play: boolean; onComplete?: () => void }) {
  const [lit, setLit] = useState(0);
  const [phase, setPhase] = useState<"idle" | "seq" | "out">(play ? "idle" : "out");
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    if (!play) {
      setLit(0);
      setPhase("out");
      return;
    }
    setPhase("seq");
    setLit(0);
    const timers: number[] = [];
    for (let i = 1; i <= 5; i++) {
      timers.push(window.setTimeout(() => setLit(i), i * LIGHT_MS));
    }
    timers.push(
      window.setTimeout(() => {
        setLit(0);
        setPhase("out");
        onCompleteRef.current?.();
      }, 5 * LIGHT_MS + HOLD_MS),
    );
    return () => timers.forEach((id) => window.clearTimeout(id));
  }, [play]);

  const caption = !play ? "STARTING LIGHTS" : phase === "out" ? "LIGHTS OUT" : lit > 0 ? "LIGHTS" : "STARTING LIGHTS";

  return (
    <div
      style={{
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "8px 12px 4px",
        gap: 6,
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 10,
          padding: "7px 16px",
          background: "#050608",
          border: `1px solid ${C.borderHi}`,
          borderRadius: 3,
          boxShadow: "inset 0 0 0 1px #000",
        }}
      >
        {[1, 2, 3, 4, 5].map((n) => {
          const on = phase === "seq" && lit >= n;
          return (
            <span
              key={n}
              style={{
                width: 16,
                height: 16,
                borderRadius: "50%",
                background: on ? C.soft : "#2a0c10",
                boxShadow: on ? `0 0 10px ${C.soft}, 0 0 2px ${C.soft}` : "inset 0 1px 2px #000",
                border: `1px solid ${on ? C.soft : "#4a1520"}`,
                transition: "background 80ms linear, box-shadow 80ms linear",
              }}
            />
          );
        })}
      </div>
      <div
        style={{
          fontFamily: T.mono,
          fontSize: 9,
          letterSpacing: "0.18em",
          color: phase === "out" && play ? C.signal : C.faint,
          height: 12,
        }}
      >
        {caption}
      </div>
    </div>
  );
}
