import { useState } from "react";
import { apiGet } from "../api/client";
import type { SessionConfig, StratPlan } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { C, T } from "../theme";
import { Chip, PanelError, ReasoningBar, SectionLabel, Skeleton, TyreBadge } from "../components/atoms";
import { Shell } from "../components/Shell";
import { compoundLetter } from "../theme";

export function BriefingView({
  partial,
  onLock,
}: {
  partial: Omit<SessionConfig, "arisMode" | "planId">;
  onLock: (cfg: SessionConfig) => void;
}) {
  const [picked, setPicked] = useState("A");
  const [arisMode, setArisMode] = useState<"auto" | "assisted">("assisted");
  const plans = useAsync(async () => {
    const data = await apiGet<{ plans: StratPlan[]; pit_loss_s: number | null }>(
      `/api/aris/plans?year=${partial.year}&round_number=${partial.round.round_number}&driver_code=${partial.driver}`,
      { timeout: 60_000 },
    );
    return data;
  }, [partial.year, partial.round.round_number, partial.driver]);

  return (
    <Shell title="STRATEGY BRIEFING">
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "28px 24px" }}>
        <SectionLabel>ARIS CONTROL MODE</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 28 }}>
          {(["auto", "assisted"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setArisMode(m)}
              style={{
                padding: 16,
                borderRadius: 4,
                cursor: "pointer",
                textAlign: "left",
                background: arisMode === m ? (m === "auto" ? C.greenDim : C.signalMid) : C.panel2,
                border: `1px solid ${arisMode === m ? (m === "auto" ? C.green : C.signal) : C.border}`,
              }}
            >
              <div style={{ fontFamily: T.display, fontSize: 18, fontWeight: 800, color: C.paper }}>
                {m.toUpperCase()}
              </div>
              <p style={{ fontFamily: T.body, fontSize: 12, color: C.mist, marginTop: 8 }}>
                {m === "auto"
                  ? "ARIS decides pit timing and compound. Watch the log."
                  : "ARIS recommends; you confirm or override each call."}
              </p>
            </button>
          ))}
        </div>
        <SectionLabel>CANDIDATE STRATEGIES FOR {partial.driver}</SectionLabel>
        {plans.status === "loading" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            <Skeleton height={180} />
            <Skeleton height={180} />
            <Skeleton height={180} />
          </div>
        )}
        {plans.status === "error" && (
          <PanelError
            message={
              plans.error.includes("503") || plans.error.toLowerCase().includes("ingest")
                ? "Strategy engine requires ingested session. Retry, or ingest this weekend into Postgres."
                : `Strategy engine unavailable: ${plans.error}`
            }
            onRetry={plans.retry}
          />
        )}
        {plans.status === "ok" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 28 }}>
            {plans.data.plans.map((p) => (
              <button
                key={p.id}
                onClick={() => setPicked(p.id)}
                style={{
                  padding: 16,
                  borderRadius: 4,
                  cursor: "pointer",
                  textAlign: "left",
                  background: picked === p.id ? C.signalMid : C.panel,
                  border: `1px solid ${picked === p.id ? C.signal : C.border}`,
                }}
              >
                <div style={{ fontFamily: T.display, fontSize: 24, fontWeight: 900 }}>PLAN {p.id}</div>
                <div style={{ display: "flex", gap: 6, margin: "8px 0" }}>
                  <Chip tone="mist" size="xs">{p.risk.toUpperCase()}</Chip>
                  {p.recommended && <Chip tone="green" size="xs">REC</Chip>}
                </div>
                <div style={{ fontFamily: T.body, fontSize: 13, color: C.paper, marginBottom: 8 }}>{p.name}</div>
                <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 8 }}>
                  <TyreBadge compound={compoundLetter(p.start_compound)} size="sm" />
                  {p.pit_compounds.map((c, i) => (
                    <span key={i} style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
                      <span style={{ color: C.faint }}>→</span>
                      <TyreBadge compound={compoundLetter(c)} size="sm" />
                    </span>
                  ))}
                </div>
                <p style={{ fontFamily: T.body, fontSize: 11, color: C.mist }}>{p.description}</p>
                {p.pit_cost_s != null && (
                  <ReasoningBar paceGain={p.pace_gain_s ?? 0} pitCost={p.pit_cost_s} label />
                )}
              </button>
            ))}
          </div>
        )}
        <button
          onClick={() => onLock({ ...partial, arisMode, planId: picked })}
          style={{
            padding: "13px 28px",
            background: C.signal,
            border: "none",
            borderRadius: 4,
            color: C.ink,
            fontFamily: T.display,
            fontSize: 17,
            fontWeight: 800,
            cursor: "pointer",
          }}
        >
          LOCK IN & ENTER RACE CONSOLE →
        </button>
      </div>
    </Shell>
  );
}
