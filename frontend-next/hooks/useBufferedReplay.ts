"use client";

import { useRef, useEffect, useState } from "react";

// Same-origin; Next rewrites /static_replays/* to the FastAPI broker.
const STATIC_REPLAYS_BASE = "";
const CHUNK_SIZE_SEC = 60;

export interface CarState {
  x: number;
  y: number;
  s: number;
}
interface FrameData {
  t: number;
  cars: Record<string, CarState>;
}
export interface ReplayManifest {
  session: string;
  start_time: number;
  end_time: number;
  total_chunks: number;
}

export type ReplayFrameCallback = (cars: Record<string, CarState>, time: number) => void;

function indexForTime(frames: FrameData[], t: number): number {
  if (frames.length === 0) return 0;
  let lo = 0;
  let hi = frames.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (frames[mid].t <= t) lo = mid;
    else hi = mid - 1;
  }
  if (lo >= frames.length - 1) return Math.max(0, frames.length - 2);
  return lo;
}

export function useBufferedReplay(
  sessionSlug: string | null,
  isPlaying: boolean,
  playbackSpeed: number = 1,
  onFrame?: ReplayFrameCallback,
) {
  const [manifest, setManifest] = useState<ReplayManifest | null>(null);
  const [isBuffering, setIsBuffering] = useState(false);

  const bufferRef = useRef<FrameData[]>([]);
  const loadedChunksRef = useRef<Set<number>>(new Set());
  const currentIndexRef = useRef(0);
  const lastPrefetchChunkRef = useRef(-1);

  const timeRef = useRef(0);
  const lastRafTimeRef = useRef<number | null>(null);
  const rafIdRef = useRef<number | null>(null);
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;

  useEffect(() => {
    if (!sessionSlug) return;
    bufferRef.current = [];
    loadedChunksRef.current.clear();
    currentIndexRef.current = 0;
    lastPrefetchChunkRef.current = -1;
    const ctrl = new AbortController();
    fetch(`${STATIC_REPLAYS_BASE}/static_replays/${sessionSlug}/manifest.json`, {
      signal: ctrl.signal,
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Manifest HTTP ${res.status}`);
        return res.json();
      })
      .then((data: ReplayManifest) => {
        setManifest(data);
        timeRef.current = data.start_time;
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        console.error("Manifest missing", err);
      });
    return () => ctrl.abort();
  }, [sessionSlug]);

  const getChunkIndex = (time: number, startTime: number) =>
    Math.floor((time - startTime) / CHUNK_SIZE_SEC);

  const fetchChunk = async (chunkIdx: number) => {
    if (
      !sessionSlug ||
      loadedChunksRef.current.has(chunkIdx) ||
      chunkIdx < 0 ||
      (manifest && chunkIdx >= manifest.total_chunks)
    )
      return;

    setIsBuffering(true);
    try {
      const res = await fetch(
        `${STATIC_REPLAYS_BASE}/static_replays/${sessionSlug}/chunk_${chunkIdx}.json`,
      );
      if (res.ok) {
        const chunkData: FrameData[] = await res.json();
        bufferRef.current = [...bufferRef.current, ...chunkData].sort((a, b) => a.t - b.t);
        loadedChunksRef.current.add(chunkIdx);
        currentIndexRef.current = indexForTime(bufferRef.current, timeRef.current);
      }
    } finally {
      setIsBuffering(false);
    }
  };

  useEffect(() => {
    if (!manifest) return;
    const currentChunkIdx = getChunkIndex(timeRef.current, manifest.start_time);
    lastPrefetchChunkRef.current = currentChunkIdx;
    void fetchChunk(currentChunkIdx);
    void fetchChunk(currentChunkIdx + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manifest]);

  useEffect(() => {
    if (!isPlaying || !manifest) {
      lastRafTimeRef.current = null;
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
      return;
    }

    const loop = (performanceNow: number) => {
      if (lastRafTimeRef.current !== null) {
        const deltaSec =
          ((performanceNow - lastRafTimeRef.current) / 1000) * playbackSpeed;
        timeRef.current += deltaSec;

        if (timeRef.current >= manifest.end_time) {
          timeRef.current = manifest.end_time;
          lastRafTimeRef.current = performanceNow;
          return;
        }

        const buf = bufferRef.current;
        if (buf.length >= 2) {
          if (currentIndexRef.current < 0) currentIndexRef.current = 0;
          if (currentIndexRef.current > buf.length - 2) {
            currentIndexRef.current = buf.length - 2;
          }

          while (
            currentIndexRef.current < buf.length - 2 &&
            timeRef.current >= buf[currentIndexRef.current + 1].t
          ) {
            currentIndexRef.current++;
          }
          while (
            currentIndexRef.current > 0 &&
            buf[currentIndexRef.current].t > timeRef.current
          ) {
            currentIndexRef.current--;
          }

          const frame1 = buf[currentIndexRef.current];
          const frame2 = buf[currentIndexRef.current + 1];
          if (frame1 && frame2) {
            const timeSpan = frame2.t - frame1.t;
            const factor = timeSpan === 0 ? 0 : (timeRef.current - frame1.t) / timeSpan;
            const currentCars: Record<string, CarState> = {};
            for (const drv of Object.keys(frame1.cars)) {
              const car1 = frame1.cars[drv];
              const car2 = frame2.cars[drv];
              if (car1 && car2) {
                currentCars[drv] = {
                  x: car1.x + (car2.x - car1.x) * factor,
                  y: car1.y + (car2.y - car1.y) * factor,
                  s: car1.s + (car2.s - car1.s) * factor,
                };
              }
            }
            onFrameRef.current?.(currentCars, timeRef.current);
          }
        }

        const chunkIdx = getChunkIndex(timeRef.current, manifest.start_time);
        if (chunkIdx !== lastPrefetchChunkRef.current) {
          lastPrefetchChunkRef.current = chunkIdx;
          void fetchChunk(chunkIdx);
          void fetchChunk(chunkIdx + 1);
        }
      }
      lastRafTimeRef.current = performanceNow;
      rafIdRef.current = requestAnimationFrame(loop);
    };

    rafIdRef.current = requestAnimationFrame(loop);
    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying, playbackSpeed, manifest]);

  const seekTime = (targetTime: number) => {
    if (!manifest) return;
    const clampedTime = Math.max(
      manifest.start_time,
      Math.min(targetTime, manifest.end_time),
    );
    timeRef.current = clampedTime;
    lastRafTimeRef.current = null;
    currentIndexRef.current = indexForTime(bufferRef.current, clampedTime);
    const chunkIdx = getChunkIndex(clampedTime, manifest.start_time);
    lastPrefetchChunkRef.current = chunkIdx;
    void fetchChunk(chunkIdx);
    void fetchChunk(chunkIdx + 1);
  };

  return { currentTime: timeRef.current, isBuffering, seekTime, manifest };
}
