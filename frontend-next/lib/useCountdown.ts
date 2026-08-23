"use client";

import { useEffect, useState } from "react";

export function useCountdown(targetIso: string): string {
  const [label, setLabel] = useState("—");

  useEffect(() => {
    const target = new Date(targetIso).getTime();
    function tick() {
      const diff = Math.max(0, target - Date.now());
      const d = Math.floor(diff / 86_400_000);
      const h = Math.floor((diff % 86_400_000) / 3_600_000);
      const m = Math.floor((diff % 3_600_000) / 60_000);
      const s = Math.floor((diff % 60_000) / 1000);
      setLabel(`${d}d ${h}h ${m}m ${s}s`);
    }
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [targetIso]);

  return label;
}
