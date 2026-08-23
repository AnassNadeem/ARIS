"use client";

import { useRaceStore } from "@/store/raceStore";

/**
 * The signature 2px red timing beam across the top of the viewport.
 * Animates left-to-right only while ARIS is on; otherwise it's inert.
 */
export function ARISPulse() {
  const isARISOn = useRaceStore((s) => s.isARISOn);

  return (
    <div
      aria-hidden
      className="fixed top-0 left-0 right-0 z-[100] h-[2px] overflow-hidden bg-[var(--color-border)]"
    >
      {isARISOn && (
        <div className="aris-pulse-beam h-full w-1/4 bg-[var(--color-red)] shadow-[0_0_8px_var(--color-red)]" />
      )}
      <style jsx>{`
        .aris-pulse-beam {
          animation: aris-pulse-sweep 1.8s linear infinite;
        }
        @keyframes aris-pulse-sweep {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(400%);
          }
        }
      `}</style>
    </div>
  );
}
