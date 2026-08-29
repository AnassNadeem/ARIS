"use client";

import React, { useCallback, useRef, useState } from "react";
import {
  useBufferedReplay,
  type CarState,
} from "../hooks/useBufferedReplay";

const SVG_NS = "http://www.w3.org/2000/svg";

function ensureCarNode(parent: SVGSVGElement, drv: string): SVGGElement {
  const existing = parent.querySelector<SVGGElement>(`g[data-driver="${drv}"]`);
  if (existing) return existing;

  const g = document.createElementNS(SVG_NS, "g");
  g.setAttribute("data-driver", drv);

  const circle = document.createElementNS(SVG_NS, "circle");
  circle.setAttribute("r", "300");
  circle.setAttribute("fill", "white");

  const text = document.createElementNS(SVG_NS, "text");
  text.setAttribute("y", "700");
  text.setAttribute("font-size", "700");
  text.setAttribute("fill", "white");
  text.setAttribute("text-anchor", "middle");
  text.setAttribute("transform", "scale(1, -1)");
  text.textContent = drv;

  g.appendChild(circle);
  g.appendChild(text);
  parent.appendChild(g);
  return g;
}

export default function BufferedReplayTest() {
  const [isPlaying, setIsPlaying] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const carNodeRefs = useRef<Record<string, SVGGElement>>({});
  const visualStateRef = useRef<Record<string, { x: number; y: number }>>({});
  const clockRef = useRef<HTMLSpanElement | null>(null);
  const startTimeRef = useRef(0);

  const onFrame = useCallback((cars: Record<string, CarState>, time: number) => {
    if (clockRef.current && startTimeRef.current) {
      const elapsed = time - startTimeRef.current;
      clockRef.current.textContent = `Race Time: ${Math.floor(elapsed / 60)}m ${(elapsed % 60).toFixed(1)}s`;
    }

    const svg = svgRef.current;
    if (!svg) return;

    const SMOOTHING = 0.15;

    Object.entries(cars).forEach(([drv, target]) => {
      if (!visualStateRef.current[drv]) {
        visualStateRef.current[drv] = { x: target.x, y: target.y };
      }

      const visual = visualStateRef.current[drv];
      visual.x += (target.x - visual.x) * SMOOTHING;
      visual.y += (target.y - visual.y) * SMOOTHING;

      let node = carNodeRefs.current[drv];
      if (!node) {
        node = ensureCarNode(svg, drv);
        carNodeRefs.current[drv] = node;
      }
      node.setAttribute("transform", `translate(${visual.x}, ${visual.y})`);
    });
  }, []);

  const { isBuffering, seekTime: seekReplayTime, manifest } = useBufferedReplay(
    "2024_zandvoort_r",
    isPlaying,
    1.0,
    onFrame,
  );

  const seekTime = (target: number) => {
    visualStateRef.current = {};
    seekReplayTime(target);
  };

  if (manifest) startTimeRef.current = manifest.start_time;

  if (!manifest) {
    return (
      <div className="p-8 text-white bg-gray-900 min-h-screen">Loading Manifest...</div>
    );
  }

  return (
    <div className="p-8 bg-gray-900 text-white min-h-screen font-mono">
      <h1 className="text-2xl font-bold mb-4">60 FPS Telemetry Engine Test</h1>

      <div className="flex gap-4 mb-4 items-center">
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className="px-4 py-2 bg-red hover:brightness-110 rounded font-bold"
        >
          {isPlaying ? "PAUSE" : "PLAY"}
        </button>

        <button
          onClick={() => seekTime(manifest.start_time + 1800)}
          className="px-4 py-2 bg-gray-700 rounded"
        >
          Seek to +30 Mins
        </button>

        <button
          onClick={() => seekTime(manifest.start_time + 3600)}
          className="px-4 py-2 bg-gray-700 rounded"
        >
          Seek to +60 Mins
        </button>

        <span className="text-yellow-400 font-bold ml-4">
          {isBuffering ? "BUFFERING..." : "READY"}
        </span>

        <span
          ref={clockRef}
          className="ml-auto text-xl bg-gray-800 px-3 py-1 rounded"
        >
          Race Time: 0m 0.0s
        </span>
      </div>

      <div className="relative w-full aspect-video bg-black border border-gray-700 overflow-hidden rounded">
        <svg
          ref={svgRef}
          viewBox="-10000 -10000 20000 20000"
          className="w-full h-full"
          style={{ transform: "scale(1, -1)" }}
        />
      </div>
    </div>
  );
}
