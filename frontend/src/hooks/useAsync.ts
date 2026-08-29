import { useCallback, useEffect, useState } from "react";
import { withReload } from "../api/client";

export type AsyncState<T> =
  | { status: "loading"; data: T | undefined; error: undefined }
  | { status: "ok"; data: T; error: undefined }
  | { status: "error"; data: T | undefined; error: string };

export function useAsync<T>(
  fn: () => Promise<T>,
  deps: readonly unknown[],
  enabled = true,
  peek?: () => T | undefined,
) {
  const [state, setState] = useState<AsyncState<T>>(() => {
    if (!enabled) {
      return { status: "loading", data: undefined, error: undefined };
    }
    const hit = peek?.();
    if (hit !== undefined) return { status: "ok", data: hit, error: undefined };
    return { status: "loading", data: undefined, error: undefined };
  });
  const [tick, setTick] = useState(0);

  const retry = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    if (tick === 0) {
      const hit = peek?.();
      if (hit !== undefined) {
        setState({ status: "ok", data: hit, error: undefined });
        return;
      }
    }
    setState((prev) =>
      prev.status === "ok"
        ? prev
        : { status: "loading", data: prev.data, error: undefined },
    );
    const run = tick > 0 ? () => withReload(fn) : fn;
    run()
      .then((data) => {
        if (!cancelled) setState({ status: "ok", data, error: undefined });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState((prev) => {
            const message = err instanceof Error ? err.message : String(err);
            if (prev.data !== undefined) {
              return { status: "ok", data: prev.data, error: undefined };
            }
            return { status: "error", data: undefined, error: message };
          });
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, enabled]);

  return { ...state, retry };
}
