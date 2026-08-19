import { useCallback, useEffect, useState } from "react";

export type AsyncState<T> =
  | { status: "loading"; data: T | undefined; error: undefined }
  | { status: "ok"; data: T; error: undefined }
  | { status: "error"; data: T | undefined; error: string };

export function useAsync<T>(fn: () => Promise<T>, deps: readonly unknown[], enabled = true) {
  const [state, setState] = useState<AsyncState<T>>({
    status: "loading",
    data: undefined,
    error: undefined,
  });
  const [tick, setTick] = useState(0);

  const retry = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setState((prev) =>
      prev.status === "ok"
        ? prev
        : { status: "loading", data: prev.data, error: undefined },
    );
    fn()
      .then((data) => {
        if (!cancelled) setState({ status: "ok", data, error: undefined });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            data: undefined,
            error: err instanceof Error ? err.message : String(err),
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
