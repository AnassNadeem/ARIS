"use client";

import { useEffect, useRef, useState } from "react";
import { useRaceStore } from "@/store/raceStore";
import { askARIS, copilotFeatureEnabled, getSessionResults } from "@/lib/api";
import { answerFactualLive, classifyIntent, historyLookupHint } from "@/lib/copilotIntent";
import { RecommendationCard } from "@/components/aris/RecommendationCard";
import { CopilotPanel } from "@/components/aris/CopilotPanel";
import { commsTabs } from "@/lib/sessionFlow";
import { useCommsNarration } from "@/lib/useCommsNarration";
import { StrategyPanel } from "@/components/aris/StrategyPanel";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";

const ASK_CHIPS = [
  "Who's leading?",
  "Gap to the leader?",
  "What lap is it?",
  "What tyres are we on?",
  "Is there a safety car?",
  "What's the undercut window?",
  "Should we extend?",
  "What does ARIS think?",
];

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
    ARIS_RESET: { text: "⚑ [ARIS — STRATEGY RESET]", cls: "text-[#E8002D]" },
  };
  const cfg = map[source] ?? { text: source, cls: "text-muted" };
  return <span className={`font-mono-data text-[9px] uppercase ${cfg.cls}`}>{cfg.text}</span>;
}

function MainComms() {
  useCommsNarration();
  const commsLog = useRaceStore((s) => s.commsLog);
  const pendingRecommendation = useRaceStore((s) => s.pendingRecommendation);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const arisDriver = useRaceStore((s) => s.arisDriver);
  const strategyLoading = useRaceStore((s) => s.strategyLoading);
  const requestStrategy = useRaceStore((s) => s.requestStrategy);
  const packStage = useRaceStore((s) => s.packStage);
  const consoleMode = useRaceStore((s) => s.consoleMode);
  const strategyReady = consoleMode !== "replay" || packStage === "minimal" || packStage === "full";
  const loading = usePanelFeedLoading();
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const stickRef = useRef(true);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el || !stickRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [commsLog.length, pendingRecommendation]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      {/* Pinned above the scroller (not inside it) so the current strategy
       * and tyre stay visible no matter how far the comms feed is scrolled. */}
      <div className="shrink-0 px-2 pt-2">
        <StrategyPanel />
      </div>
      <div
        ref={scrollerRef}
        onScroll={() => {
          const el = scrollerRef.current;
          if (!el) return;
          stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 64;
        }}
        className="min-h-0 flex-1 overflow-y-auto p-2 [overflow-anchor:none]"
      >
        {loading && commsLog.length === 0 && !pendingRecommendation ? (
          <PanelSkeleton rows={6} />
        ) : commsLog.length === 0 && !pendingRecommendation ? (
          <PanelEmpty
            title="ARIS comms"
            detail={
              isARISOn
                ? `Radio channel for recommendations and field calls${arisDriver ? ` for ${arisDriver}` : ""}. Empty until ARIS speaks or the race starts.`
                : "ARIS strategy is off. Turn ARIS on from the race selector, or use Copilot to ask about this race."
            }
          />
        ) : null}
        {commsLog.map((m, i) => (
          <div
            key={`${m.id}#${i}`}
            className={`mb-2 border-l-2 pl-2 ${
              m.source === "ARIS_RESET" ? "border-[#E8002D] bg-[#E8002D]/10" : "border-border"
            }`}
          >
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
      </div>
      {isARISOn && (
        <div className="shrink-0 border-t border-border p-2">
          <button
            type="button"
            disabled={strategyLoading || !strategyReady}
            onClick={() => requestStrategy()}
            className="w-full rounded bg-red px-3 py-1.5 font-mono-data text-[10px] uppercase text-white disabled:opacity-50"
          >
            {strategyLoading ? "Analysing…" : !strategyReady ? "Waiting for laps…" : `Get strategy${arisDriver ? ` · ${arisDriver}` : ""}`}
          </button>
        </div>
      )}
    </div>
  );
}

function AskARIS() {
  const pushComms = useRaceStore((s) => s.pushComms);
  const commsLog = useRaceStore((s) => s.commsLog);
  const currentLap = useRaceStore((s) => s.currentLap);
  const session = useRaceStore((s) => s.session);
  const arisDriver = useRaceStore((s) => s.arisDriver);
  const cars = useRaceStore((s) => s.cars);
  const racePhase = useRaceStore((s) => s.racePhase);
  const rainfall = useRaceStore((s) => s.rainfall);
  const totalLaps = useRaceStore((s) => s.totalLaps);
  const lastRecommendation = useRaceStore((s) => s.lastRecommendation);
  const ghostPosition = useRaceStore((s) => s.ghostCar?.position ?? null);
  const [pending, setPending] = useState(false);
  const askEntries = commsLog.filter((c) => c.source === "USER" || c.source === "ARIS_ANALYSIS");
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [askEntries.length]);

  async function send(question: string) {
    if (!question.trim() || pending) return;
    setPending(true);
    pushComms({ id: nextCommsId("ask"), lap: currentLap, source: "USER", text: question, timestamp: nowTimestamp() });
    const local = answerFactualLive(question, {
      cars,
      currentLap,
      totalLaps,
      racePhase,
      rainfall,
      focusDriver: arisDriver,
      session,
      lastRecommendation,
      ghostPosition,
    });
    if (local) {
      pushComms({
        id: nextCommsId("ans"),
        lap: currentLap,
        source: "ARIS_ANALYSIS",
        text: local,
        timestamp: nowTimestamp(),
      });
      setPending(false);
      return;
    }
    if (classifyIntent(question) === "factual_history") {
      const hint = historyLookupHint(question, session);
      if (hint) {
        const rows = await getSessionResults(hint.year, hint.round);
        const winner = rows?.find((r) => r.position === 1);
        if (winner) {
          const circuit = session?.circuitName ?? "this circuit";
          pushComms({
            id: nextCommsId("ans"),
            lap: currentLap,
            source: "ARIS_ANALYSIS",
            text: `${winner.driver_code} won the ${hint.year} ${circuit} race.`,
            timestamp: nowTimestamp(),
          });
          setPending(false);
          return;
        }
      }
    }
    const { answer, offline } = await askARIS(question, undefined, {
      year: session?.year,
      round: session?.round,
      driver: arisDriver ?? undefined,
      currentLap,
    });
    pushComms({
      id: nextCommsId("ans"),
      lap: currentLap,
      source: "ARIS_ANALYSIS",
      text: answer,
      timestamp: nowTimestamp(),
      // Never silently pass a canned fallback off as a live answer.
      offlineAnswer: offline,
    });
    setPending(false);
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div ref={scrollerRef} className="min-h-0 flex-1 overflow-y-auto p-2 [overflow-anchor:none]">
        {askEntries.length === 0 && (
          <PanelEmpty
            title="Ask ARIS"
            detail="Pick a question below. ARIS answers from the live timing board for this race."
          />
        )}
        {askEntries.map((m) => (
          <div key={m.id} className="mb-2">
            <SourceLabel source={m.source} />
            <div className="mt-0.5 font-mono-data text-[11px] leading-relaxed text-white/90">{m.text}</div>
            {m.offlineAnswer && (
              <div className="mt-1 inline-block rounded bg-amber/15 px-1.5 py-0.5 font-mono-data text-[9px] text-amber">
                ⚠ OFFLINE — backend unreachable, showing a cached local answer
              </div>
            )}
          </div>
        ))}
        {pending && <div className="font-mono-data text-[10px] text-muted">Thinking…</div>}
      </div>
      <div className="flex shrink-0 flex-wrap gap-1.5 border-t border-border p-2">
        {ASK_CHIPS.map((c) => (
          <button
            key={c}
            type="button"
            disabled={pending}
            onClick={() => void send(c)}
            className="rounded-full border border-border px-2.5 py-1 font-mono-data text-[10px] text-muted hover:border-white hover:text-white disabled:opacity-40"
          >
            {c}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ARISComms() {
  const [tab, setTab] = useState<"main" | "chat">("main");
  const [threadId, setThreadId] = useState("c1");
  const [threadSeq, setThreadSeq] = useState(1);
  // Canonical chat panel: Copilot (tool-calling, cites retrieved chunks,
  // supports approve/deny/alter) is preferred over the plain Ask ARIS panel.
  // `copilotFeatureEnabled()` is on by default outside production and off in
  // production unless NEXT_PUBLIC_ARIS_COPILOT=1 is set at build time — so a
  // production build shows Ask ARIS unless that flag is set. See
  // docs/ASK_ARIS.md for the full wiring.
  const showCopilot = copilotFeatureEnabled();
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const copilotDocked = useRaceStore((s) => s.copilotDocked);
  const tabs = commsTabs({ arisOn: isARISOn, copilotOn: showCopilot, copilotDocked });

  useEffect(() => {
    if (!tabs.some((t) => t.id === tab)) setTab(tabs[0]?.id ?? "chat");
  }, [tabs, tab]);

  return (
    <div className="flex h-full flex-col bg-carbon">
      <div className="flex shrink-0 items-center border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 font-sans text-[10px] uppercase tracking-wide ${
              tab === t.id ? "border-b-2 border-red text-white" : "text-muted hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
        {tab === "chat" && (
          <button
            onClick={() => {
              const next = threadSeq + 1;
              setThreadSeq(next);
              setThreadId(`c${next}`);
            }}
            className="ml-auto px-2 py-2 font-mono-data text-[9px] uppercase text-muted hover:text-white"
          >
            New chat
          </button>
        )}
      </div>
      <div className="min-h-0 flex-1">
        {tab === "main" && <MainComms />}
        {tab === "chat" && (showCopilot ? <CopilotPanel threadId={threadId} /> : <AskARIS />)}
      </div>
    </div>
  );
}
