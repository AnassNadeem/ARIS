import { useState } from "react";
import type { Driver } from "../api/types";
import { C, T } from "../theme";

export function CarFilter({
  drivers,
  hidden,
  onToggle,
}: {
  drivers: Driver[];
  hidden: string[];
  onToggle: (code: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const teams = new Map<string, Driver[]>();
  for (const d of drivers) {
    const list = teams.get(d.team_name) ?? [];
    list.push(d);
    teams.set(d.team_name, list);
  }
  return (
    <div style={{ padding: 10, borderTop: `1px solid ${C.border}`, flexShrink: 0 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          fontFamily: T.mono,
          fontSize: 9,
          color: C.faint,
          letterSpacing: "0.1em",
          marginBottom: open ? 8 : 0,
        }}
      >
        {open ? "▾" : "▸"} FILTER CARS
      </button>
      {open && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
          {[...teams.entries()].map(([team, pair]) => (
            <div key={team} style={{ display: "flex", gap: 6, alignItems: "center" }}>
              {pair.map((d) => {
                const off = hidden.includes(d.driver_code);
                return (
                  <label
                    key={d.driver_code}
                    style={{
                      display: "flex",
                      gap: 4,
                      alignItems: "center",
                      fontFamily: T.mono,
                      fontSize: 10,
                      color: off ? C.faint : C.paper,
                      cursor: "pointer",
                    }}
                  >
                    <input type="checkbox" checked={!off} onChange={() => onToggle(d.driver_code)} />
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: d.team_colour || C.mist }} />
                    {d.driver_code}
                  </label>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
