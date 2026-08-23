"use client";

import { useEffect, useRef, useState } from "react";
import { useRaceStore } from "@/store/raceStore";
import { askARIS } from "@/lib/api";
import { RecommendationCard } from "@/components/aris/RecommendationCard";

const CHIPS = ["Gap to Lando?", "Should we extend?", "What's the undercut window?"];

let commsSeq = 0;
function nextCommsId(prefix: string): string {
  commsSeq += 1;
  return `${prefix}-${commsSeq}`;
}
function nowTimestamp(): number {
  return Date.now();
}

function SourceLabel({ source }: { source: string }) {
  const map: Record<string, { text: string; cls: string }> = {
    ARIS: { text: "◉ [ARIS]", cls: "text-red" },
    USER: { text: "YOU", cls: "text-white" },
    ARIS_ANALYSIS: { text: "[ARIS ANALYSIS]", cls: "text-amber" },
    FIELD: { text: "FIELD", cls: "text-[#4FA8E0]" },
  };
  const cfg = map[source] ?? { text: source, cls: "text-muted" };
  return <span className={`font-mono-data text-[9px] uppercase ${cfg.cls}`}>{cfg.text}</span>;
}

function MainComms() {
  const commsLog = useRaceStore((s) => s.commsLog);
  const pendingRecommendation = useRaceStore((s) => s.pendingRecommendation);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [commsLog, pendingRecommendation]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {commsLog.length === 0 && !pendingRecommendation && (
          <div className="p-4 text-center font-mono-data text-[11px] text-muted">
            No messages yet. Recommendations appear as the race advances.
          </div>
        )}
        {commsLog.map((m) => (
          <div key={m.id} className="mb-2 border-l-2 border-border pl-2">
            <div className="flex items-center gap-2">
              <SourceLabel source={m.source} />
              <span className="font-mono-data text-[9px] text-muted-2">L{m.lap}</span>
            </div>
            <div className="mt-0.5 font-mono-data text-[11px] leading-relaxed text-white/90">{m.text}</div>
            {m.wetHeuristic && (
              <div className="mt-1 inline-block rounded bg-amber/15 px-1.5 py-0.5 font-mono-data text-[9px] text-amber">
                ⚠ HEURISTIC — reduced confidence in wet conditions
              </div>
            )}
          </div>
        ))}
        {pendingRecommendation && <RecommendationCard />}
        <div ref={endRef} />
      </div>
    </div>
  );
}

function AskARIS() {
  const pushComms = useRaceStore((s) => s.pushComms);
  const commsLog = useRaceStore((s) => s.commsLog);
  const currentLap = useRaceStore((s) => s.currentLap);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const askEntries = commsLog.filter((c) => c.source === "USER" || c.source === "ARIS_ANALYSIS");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [askEntries.length]);

  async function send(question: string) {
    if (!question.trim() || pending) return;
    setPending(true);
    pushComms({ id: nextCommsId("ask"), lap: currentLap, source: "USER", text: question, timestamp: nowTimestamp() });
    setInput("");
    const { answer } = await askARIS(question);
    pushComms({ id: nextCommsId("ans"), lap: currentLap, source: "ARIS_ANALYSIS", text: answer, timestamp: nowTimestamp() });
    setPending(false);
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {askEntries.length === 0 && (
          <div className="flex flex-wrap gap-2 p-2">
            {CHIPS.map((c) => (
              <button
                key={c}
                onClick={() => send(c)}
                className="rounded-full border border-border px-2.5 py-1 font-mono-data text-[10px] text-muted hover:border-white hover:text-white"
              >
                {c}
              </button>
            ))}
          </div>
        )}
        {askEntries.map((m) => (
          <div key={m.id} className="mb-2">
            <SourceLabel source={m.source} />
            <div className="mt-0.5 font-mono-data text-[11px] leading-relaxed text-white/90">{m.text}</div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div className="flex shrink-0 gap-2 border-t border-border p-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          placeholder="Ask ARIS a question about this race…"
          className="flex-1 rounded border border-border bg-surface px-2.5 py-1.5 font-mono-data text-[11px] text-white outline-none focus:border-white"
        />
        <button
          onClick={() => send(input)}
          className="rounded bg-red px-3 py-1.5 font-mono-data text-[11px] text-white"
        >
          →
        </button>
      </div>
    </div>
  );
}

export function ARISComms() {
  const [tab, setTab] = useState<"main" | "ask">("main");

  return (
    <div className="flex h-full flex-col bg-carbon">
      <div className="flex shrink-0 border-b border-border">
        {(["main", "ask"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-2 font-mono-data text-[10px] uppercase tracking-wide ${
              tab === t ? "border-b-2 border-red text-white" : "text-muted hover:text-white"
            }`}
          >
            {t === "main" ? "Main Comms" : "Ask ARIS"}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1">{tab === "main" ? <MainComms /> : <AskARIS />}</div>
    </div>
  );
}
