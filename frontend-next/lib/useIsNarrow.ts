import { useEffect, useState } from "react";

/** Viewport is too narrow for flexlayout drag/resize (phones only; iPad stays desktop). */
export const NARROW_MQ = "(max-width: 767px)";

export function useIsNarrow(): boolean {
  const [narrow, setNarrow] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia(NARROW_MQ);
    const apply = () => setNarrow(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  return narrow;
}
