"use client";

import { useEffect, useRef, useState } from "react";
import { chatCopilot, copilotFeatureEnabled, sendARISAction } from "@/lib/api";
import { useRaceStore } from "@/store/raceStore";
import type { Compound, CopilotChatResponse, CopilotRecommendationRow } from "@/lib/types";

const CHIPS = [
  "What's the gap to NOR?",
  "What's the best strategy from here?",
  "What's the undercut window for VER vs NOR?",
  "Do drivers have to use two compounds in a dry race?",
];

type ChatItem = {
  id: string;
  role: "user" | "copilot";
  text: string;
  payload?: CopilotChatResponse;
};

let seq = 0;
function nextId(prefix: string): string {
  seq += 1;
  return `${prefix}-${seq}`;
}

export function CopilotPanel({ threadId = "default" }: { threadId?: string }) {
  const session = useRaceStore((s) => s.session);
  const currentLap = useRaceStore((s) => s.currentLap);
  const arisDriver = useRaceStore((s) => s.arisDriver);
  const copilotEnabled = useRaceStore((s) => s.copilotEnabled);
  const setCopilotEnabled = useRaceStore((s) => s.setCopilotEnabled);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [items, setItems] = useState<ChatItem[]>([]);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const featureOn = copilotFeatureEnabled();

  useEffect(() => {
    setItems([]);
    setInput("");
    setPending(false);
  }, [threadId]);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [items.length, pending]);

  async function send(question: string) {
    if (!question.trim() || pending || !copilotEnabled) return;
    setPending(true);
    setItems((prev) => [...prev, { id: nextId("u"), role: "user", text: question }]);
    setInput("");
    const payload = await chatCopilot({
      message: question,
      session_id: session ? `${session.year}-${session.round}` : undefined,
      year: session?.year,
      round_number: session?.round,
      driver_code: arisDriver ?? session?.driverCode ?? undefined,
      current_lap: currentLap,
    });
    setItems((prev) => [
      ...prev,
      { id: nextId("c"), role: "copilot", text: payload.response, payload },
    ]);
    setPending(false);
  }

  if (!featureOn) {
    return (
      <div className="p-4 font-mono-data text-[11px] text-muted">
        Copilot is off. Set NEXT_PUBLIC_ARIS_COPILOT=1 to enable.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex shrink-0 items-center justify-between border-b border-border px-2 py-1">
        <span className="font-mono-data text-[9px] uppercase tracking-wide text-muted">
          Tool-caller · retrieval
        </span>
        <label className="flex cursor-pointer items-center gap-1.5 font-mono-data text-[9px] uppercase text-muted">
          <input
            type="checkbox"
            checked={copilotEnabled}
            onChange={(e) => setCopilotEnabled(e.target.checked)}
          />
          Dev toggle
        </label>
      </div>
      {!copilotEnabled ? (
        <div className="p-4 font-mono-data text-[11px] text-muted">
          Copilot disabled. Re-enable the dev toggle to ask questions.
        </div>
      ) : (
        <>
          <div ref={scrollerRef} className="min-h-0 flex-1 overflow-y-auto p-2 [overflow-anchor:none]">
            {items.length === 0 && (
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
            {items.map((m) => (
              <div
                key={m.id}
                className={`mb-3 max-w-[92%] ${m.role === "user" ? "ml-auto" : "mr-auto"}`}
              >
                <div
                  className={`font-mono-data text-[9px] uppercase ${
                    m.role === "user" ? "text-right text-white" : "text-red"
                  }`}
                >
                  {m.role === "user" ? "YOU" : "COPILOT"}
                </div>
                <div
                  className={`mt-0.5 rounded-[6px] px-2 py-1.5 font-mono-data text-[11px] leading-relaxed ${
                    m.role === "user"
                      ? "bg-white/10 text-white"
                      : "border border-border bg-surface text-white/90"
                  }`}
                >
                  {m.text}
                </div>
                {m.payload && m.payload.recommendations.length > 0 && (
                  <Top3Table rows={m.payload.recommendations} />
                )}
                {m.payload?.needs_approval && m.payload.recommendations[0] && (
                  <ApprovalBar rec={m.payload.recommendations[0]} lap={currentLap} />
                )}
                {m.payload && m.payload.retrieved_chunks.length > 0 && (
                  <div className="mt-1 font-mono-data text-[9px] text-muted-2">
                    Cite: {m.payload.retrieved_chunks.slice(0, 2).map((c) => c.chunk_id).join(" · ")}
                  </div>
                )}
              </div>
            ))}
            {pending && (
              <div className="font-mono-data text-[10px] text-muted">Copilot calling ARIS tools…</div>
            )}
          </div>
          <div className="flex shrink-0 gap-2 border-t border-border p-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send(input)}
              placeholder="Ask Copilot — it will call ARIS tools, not guess deltas…"
              className="flex-1 rounded border border-border bg-surface px-2.5 py-1.5 font-mono-data text-[11px] text-white outline-none focus:border-white"
            />
            <button
              onClick={() => send(input)}
              className="rounded bg-red px-3 py-1.5 font-mono-data text-[11px] text-white"
            >
              →
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function Top3Table({ rows }: { rows: CopilotRecommendationRow[] }) {
  return (
    <table className="mt-1 w-full border-collapse font-mono-data text-[10px] text-white/90">
      <thead>
        <tr className="text-muted">
          <th className="px-1 py-0.5 text-left font-normal">#</th>
          <th className="px-1 py-0.5 text-left font-normal">Action</th>
          <th className="px-1 py-0.5 text-right font-normal">Δ vs stay</th>
          <th className="px-1 py-0.5 text-right font-normal">P(best)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={`${r.rank}-${r.label}`}>
            <td className="px-1 py-0.5">{r.rank}</td>
            <td className="px-1 py-0.5">{r.label}</td>
            <td className="px-1 py-0.5 text-right">
              {r.delta_vs_stay_out_s == null ? "—" : `${r.delta_vs_stay_out_s.toFixed(1)}s`}
            </td>
            <td className="px-1 py-0.5 text-right">
              {r.p_best == null ? "—" : r.p_best.toFixed(2)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ApprovalBar({ rec, lap }: { rec: CopilotRecommendationRow; lap: number }) {
  const [alterOpen, setAlterOpen] = useState(false);
  const [tyre, setTyre] = useState<Compound>("MEDIUM");
  const [note, setNote] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  async function act(action: "approve" | "deny" | "alter") {
    const out = await sendARISAction({
      action,
      lap,
      tyre: action === "deny" ? undefined : tyre,
      note: note || rec.label,
    });
    setStatus(`${action}: ${out.result}`);
    setAlterOpen(false);
  }

  return (
    <div className="mt-1">
      <div className="flex flex-wrap gap-1.5 font-mono-data text-[9px] uppercase">
        <button onClick={() => act("approve")} className="rounded bg-green px-2 py-0.5 text-carbon">
          ✓ Approve
        </button>
        <button
          onClick={() => act("deny")}
          className="rounded border border-border px-2 py-0.5 text-white hover:border-red"
        >
          ✗ Deny
        </button>
        <button
          onClick={() => setAlterOpen((v) => !v)}
          className="rounded border border-border px-2 py-0.5 text-white hover:border-amber"
        >
          ✎ Alter
        </button>
        <button
          onClick={async () => {
            const out = await chatCopilot({
              message: `Explain the strategy recommendation: ${rec.label}`,
              current_lap: lap,
            });
            setStatus(out.response);
          }}
          className="rounded border border-border px-2 py-0.5 text-white hover:border-white"
        >
          ? Explain
        </button>
      </div>
      {alterOpen && (
        <div className="mt-1 flex items-center gap-2">
          <select
            value={tyre}
            onChange={(e) => setTyre(e.target.value as Compound)}
            className="rounded border border-border bg-carbon px-1.5 py-0.5 font-mono-data text-[10px] text-white"
          >
            {(["SOFT", "MEDIUM", "HARD"] as Compound[]).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Alter note"
            className="flex-1 rounded border border-border bg-carbon px-1.5 py-0.5 font-mono-data text-[10px] text-white"
          />
          <button onClick={() => act("alter")} className="rounded bg-amber px-2 py-0.5 font-mono-data text-[9px] text-carbon">
            Submit
          </button>
        </div>
      )}
      {status && <div className="mt-1 font-mono-data text-[9px] text-muted">{status}</div>}
    </div>
  );
}
