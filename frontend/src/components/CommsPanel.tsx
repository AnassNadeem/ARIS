import { useEffect, useRef } from "react";
import { C, T } from "../theme";
import { EmptyState } from "./atoms";

export type CommMsg = { id: number; type: string; text: string };

export function CommsPanel({
  messages,
  input,
  setInput,
  onSend,
}: {
  messages: CommMsg[];
  input: string;
  setInput: (s: string) => void;
  onSend: () => void;
}) {
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
  const border: Record<string, string> = {
    intel: C.mist,
    recommend: C.signal,
    alert: C.caution,
    confirm: C.green,
    user: C.blue,
    aris_response: C.purple,
  };
  const label: Record<string, string> = {
    intel: "◉ INTEL",
    recommend: "⚡ ARIS RECOMMENDS",
    alert: "⚠ ALERT",
    confirm: "✓ CONFIRM",
    user: "YOU",
    aris_response: "ARIS RESPONSE",
  };
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
        {messages.length === 0 && (
          <EmptyState title="No messages yet" body="Recommendations appear as the replay clock advances. Ask ARIS below." />
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              padding: "8px 10px",
              borderRadius: 4,
              background: C.panel2,
              borderLeft: `3px solid ${border[m.type] || C.border}`,
            }}
          >
            <div style={{ fontFamily: T.mono, fontSize: 8, color: C.faint, marginBottom: 3 }}>{label[m.type] || "ARIS"}</div>
            <div style={{ fontFamily: T.body, fontSize: 11.5, color: C.paper, lineHeight: 1.5 }}>{m.text}</div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div style={{ flexShrink: 0, padding: 8, borderTop: `1px solid ${C.border}`, display: "flex", gap: 6 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSend()}
          placeholder="Ask ARIS anything…"
          style={{
            flex: 1,
            background: C.raised,
            border: `1px solid ${C.border}`,
            borderRadius: 3,
            padding: "6px 10px",
            color: C.paper,
            fontFamily: T.body,
            fontSize: 11,
            outline: "none",
          }}
        />
        <button
          onClick={onSend}
          style={{
            padding: "6px 10px",
            background: C.signal,
            border: "none",
            borderRadius: 3,
            cursor: "pointer",
            color: C.ink,
            fontFamily: T.mono,
            fontSize: 10,
          }}
        >
          →
        </button>
      </div>
    </div>
  );
}
