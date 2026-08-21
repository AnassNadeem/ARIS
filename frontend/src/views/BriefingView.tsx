import { useEffect, useState } from "react";
import { apiGet, apiPost, peekGet } from "../api/client";
import type { RecommendResponse, SessionConfig, StratPlan } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { C, T, compoundLetter } from "../theme";
import { Chip, ErrorPanel, ReasoningBar, SectionLabel, SkeletonPanel, TyreBadge } from "../components/atoms";
import { RaceBrief } from "../components/RaceBrief";
import { Shell } from "../components/Shell";

const COMPOUNDS = ["S", "M", "H", "I", "W"] as const;

export function BriefingView({
  partial,
  onLock,
}: {
  partial: Omit<SessionConfig, "arisMode" | "planId">;
  onLock: (cfg: SessionConfig) => void;
}) {
  const [picked, setPicked] = useState("A");
  const [arisMode, setArisMode] = useState<"auto" | "assisted">("assisted");
  const [buildOwn, setBuildOwn] = useState(false);
  const [customPits, setCustomPits] = useState<{ lap: number; compound: string }[]>([{ lap: 20, compound: "M" }]);
  const [sc, setSc] = useState(20);
  const [rain, setRain] = useState<number | "None">("None");
  const [deg, setDeg] = useState(1);
  const [simErr, setSimErr] = useState<string | null>(null);
  const [simOut, setSimOut] = useState<{
    projected_finish_position: number | null;
    delta_vs_aris_s: number | null;
    delta_vs_actual_s: number | null;
    pace_gain_s: number | null;
    pit_cost_s: number | null;
  } | null>(null);
  const [rec, setRec] = useState<RecommendResponse | null>(null);

  const plansPath = `/api/aris/plans?year=${partial.year}&round_number=${partial.round.round_number}&driver_code=${partial.driver}`;
  const plans = useAsync(
    () => apiGet<{ plans: StratPlan[]; pit_loss_s: number | null }>(plansPath, { timeout: 60_000 }),
    [partial.year, partial.round.round_number, partial.driver],
    true,
    () => peekGet<{ plans: StratPlan[]; pit_loss_s: number | null }>(plansPath),
  );

  useEffect(() => {
    if (plans.status === "ok") {
      const recPlan = plans.data.plans.find((p) => p.recommended) || plans.data.plans[0];
      if (recPlan) setPicked(recPlan.id);
    }
  }, [plans.status, plans.status === "ok" ? plans.data.plans : null]);

  useEffect(() => {
    let cancelled = false;
    const started = Date.now();
    const poll = () => {
      apiPost<RecommendResponse>(
        "/api/aris/recommend",
        {
          year: partial.year,
          round_number: partial.round.round_number,
          session_type: "R",
          driver_code: partial.driver,
          current_lap: 1,
          mode: "replay",
        },
        { timeout: 60_000 },
      )
        .then((data) => {
          if (cancelled) return;
          setRec(data);
          if (data.data_source === "POSTGRES") return;
          if (Date.now() - started < 120_000) {
            window.setTimeout(poll, 4_000);
          }
        })
        .catch(() => {
          if (!cancelled && Date.now() - started < 120_000) {
            window.setTimeout(poll, 4_000);
          }
        });
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, [partial.year, partial.round.round_number, partial.driver]);

  const simulate = async () => {
    setSimErr(null);
    const laps = customPits.map((p) => p.lap);
    if (laps.some((l, i) => i > 0 && l <= laps[i - 1])) {
      setSimErr("Pit stop laps must be in ascending order.");
      return;
    }
    if (customPits.some((p) => !p.compound)) {
      setSimErr("Select a compound for every pit stop.");
      return;
    }
    try {
      const out = await apiPost<{
        projected_finish_position: number | null;
        delta_vs_aris_s: number | null;
        delta_vs_actual_s: number | null;
        pace_gain_s: number | null;
        pit_cost_s: number | null;
      }>("/api/aris/simulate", {
        year: partial.year,
        round_number: partial.round.round_number,
        driver_code: partial.driver,
        current_lap: 1,
        pit_stops: customPits,
        pit_lap: customPits[0]?.lap,
        compound: customPits[0]?.compound,
        sc_probability: sc / 100,
        rain_lap: rain === "None" ? null : rain,
        deg_factor: deg,
      });
      setSimOut(out);
    } catch (err) {
      setSimErr(String(err));
    }
  };

  return (
    <Shell title="STRATEGY BRIEFING">
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "28px 24px" }}>
        <SectionLabel>TRACK & HISTORICAL BRIEF · FROM 2018</SectionLabel>
        <div style={{ marginBottom: 28 }}>
          <RaceBrief
            circuitKey={partial.round.circuit_key}
            year={partial.year}
            circuitName={partial.round.circuit_name}
            driver={partial.driver}
          />
        </div>
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
          <SkeletonPanel
            rows={8}
            label="Loading strategy plans — this may take a moment on first load as data is being cached..."
          />
        )}
        {plans.status === "error" && (
          <ErrorPanel
            message={
              plans.error.includes("503") || plans.error.toLowerCase().includes("ingest")
                ? "Strategy engine requires ingested session. Retry, or ingest this weekend into Postgres."
                : `Could not load strategy plans. ${plans.error}`
            }
            onRetry={plans.retry}
          />
        )}
        {plans.status === "ok" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12, marginBottom: 16 }}>
            {plans.data.plans.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setPicked(p.id);
                  setBuildOwn(false);
                }}
                style={{
                  padding: 16,
                  borderRadius: 4,
                  cursor: "pointer",
                  textAlign: "left",
                  position: "relative",
                  background: picked === p.id && !buildOwn ? C.signalMid : C.panel,
                  border: `1px solid ${picked === p.id && !buildOwn ? C.signal : C.border}`,
                }}
              >
                {p.recommended && (
                  <span
                    style={{
                      position: "absolute",
                      top: 10,
                      right: 10,
                      fontFamily: T.mono,
                      fontSize: 9,
                      color: C.signal,
                      letterSpacing: "0.06em",
                    }}
                  >
                    ⭐ ARIS RECOMMENDED
                  </span>
                )}
                <div style={{ fontFamily: T.display, fontSize: 24, fontWeight: 900 }}>PLAN {p.id}</div>
                <div style={{ display: "flex", gap: 6, margin: "8px 0" }}>
                  <Chip tone="mist" size="xs">{p.risk.toUpperCase()}</Chip>
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
                <p style={{ fontFamily: T.body, fontSize: 11, color: C.mist }}>
                  {p.recommended ? rec?.reasoning || p.description : p.description}
                </p>
                <ReasoningBar paceGain={p.pace_gain_s ?? rec?.pace_gain_s ?? 0} pitCost={p.pit_cost_s ?? rec?.pit_cost_s ?? 18} label />
              </button>
            ))}
            <div
              style={{
                padding: 16,
                borderRadius: 4,
                background: buildOwn ? C.signalMid : C.panel,
                border: `1px solid ${buildOwn ? C.signal : C.border}`,
              }}
            >
              <button
                onClick={() => {
                  setBuildOwn(true);
                  setPicked("CUSTOM");
                }}
                style={{ background: "none", border: "none", cursor: "pointer", textAlign: "left", width: "100%", color: C.paper }}
              >
                <div style={{ fontFamily: T.display, fontSize: 22, fontWeight: 900 }}>BUILD YOUR OWN</div>
                <p style={{ fontFamily: T.body, fontSize: 12, color: C.mist, marginTop: 8 }}>Custom pit laps, compounds, SC and rain.</p>
              </button>
              {buildOwn && (
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                  {customPits.map((p, i) => (
                    <div key={i}>
                      <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint, marginBottom: 4 }}>PIT STOP {i + 1}</div>
                      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        <span style={{ fontFamily: T.mono, fontSize: 10, color: C.mist }}>Lap</span>
                        <input
                          type="number"
                          min={1}
                          value={p.lap}
                          onChange={(e) => {
                            const next = [...customPits];
                            next[i] = { ...next[i], lap: Number(e.target.value) };
                            setCustomPits(next);
                          }}
                          style={inp}
                        />
                        {COMPOUNDS.map((c) => (
                          <button
                            key={c}
                            onClick={() => {
                              const next = [...customPits];
                              next[i] = { ...next[i], compound: c };
                              setCustomPits(next);
                            }}
                            style={{
                              padding: "4px 8px",
                              cursor: "pointer",
                              fontFamily: T.mono,
                              fontSize: 10,
                              background: p.compound === c ? C.signalMid : "transparent",
                              border: `1px solid ${p.compound === c ? C.signal : C.border}`,
                              color: C.paper,
                            }}
                          >
                            {c}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                  {customPits.length < 3 && (
                    <button
                      onClick={() =>
                        setCustomPits([...customPits, { lap: (customPits.at(-1)?.lap ?? 20) + 10, compound: "H" }])
                      }
                      style={{ background: "none", border: `1px dashed ${C.border}`, color: C.mist, fontFamily: T.mono, fontSize: 10, padding: 6, cursor: "pointer" }}
                    >
                      + ADD PIT STOP
                    </button>
                  )}
                  <label style={{ fontFamily: T.mono, fontSize: 10, color: C.mist }}>
                    Safety Car probability {sc}%
                    <input type="range" min={0} max={100} value={sc} onChange={(e) => setSc(Number(e.target.value))} style={{ width: "100%" }} />
                  </label>
                  <label style={{ fontFamily: T.mono, fontSize: 10, color: C.mist, display: "flex", gap: 8, alignItems: "center" }}>
                    Rain from lap
                    <input
                      value={rain}
                      onChange={(e) => {
                        const v = e.target.value;
                        setRain(v === "" || v.toLowerCase() === "none" ? "None" : Number(v));
                      }}
                      style={inp}
                    />
                  </label>
                  <label style={{ fontFamily: T.mono, fontSize: 10, color: C.mist }}>
                    Tyre deg factor {deg.toFixed(1)}×
                    <input type="range" min={0.5} max={2} step={0.1} value={deg} onChange={(e) => setDeg(Number(e.target.value))} style={{ width: "100%" }} />
                  </label>
                  {simErr && <div style={{ fontFamily: T.mono, fontSize: 10, color: C.caution }}>{simErr}</div>}
                  <button
                    onClick={() => void simulate()}
                    style={{ padding: 10, background: C.signal, border: "none", color: C.ink, fontFamily: T.mono, fontSize: 11, cursor: "pointer" }}
                  >
                    SIMULATE THIS STRATEGY →
                  </button>
                  {simOut && (
                    <div style={{ fontFamily: T.body, fontSize: 12, color: C.paper }}>
                      PROJECTED FINISH: P{simOut.projected_finish_position ?? "—"} ·{" "}
                      {simOut.delta_vs_aris_s != null ? `${simOut.delta_vs_aris_s >= 0 ? "+" : ""}${simOut.delta_vs_aris_s.toFixed(1)} vs ARIS plan` : ""}{" "}
                      · {simOut.delta_vs_actual_s != null ? `${simOut.delta_vs_actual_s >= 0 ? "+" : ""}${simOut.delta_vs_actual_s.toFixed(1)} vs actual` : ""}
                      <ReasoningBar paceGain={simOut.pace_gain_s ?? 0} pitCost={simOut.pit_cost_s ?? 18} label />
                    </div>
                  )}
                </div>
              )}
            </div>
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

const inp = {
  background: C.raised,
  border: `1px solid ${C.border}`,
  color: C.paper,
  padding: "4px 8px",
  width: 72,
  fontFamily: T.mono,
} as const;
