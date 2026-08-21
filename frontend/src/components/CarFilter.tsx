import { useState } from "react";
import type { Driver } from "../api/types";
import { C, T } from "../theme";

export function CarFilter({
  drivers,
  hidden,
  onToggle,
  onSetHidden,
}: {
  drivers: Driver[];
  hidden: string[];
  onToggle: (code: string) => void;
  onSetHidden?: (codes: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const visible = drivers.length - hidden.length;
  return (
    <div
      style={{
        position: "absolute",
        top: 8,
        right: 8,
        zIndex: 4,
        maxWidth: 220,
      }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          background: C.raised,
          border: `1px solid ${C.borderHi}`,
          cursor: "pointer",
          fontFamily: T.mono,
          fontSize: 9,
          color: C.mist,
          letterSpacing: "0.08em",
          padding: "5px 9px",
          borderRadius: 3,
        }}
      >
        {open ? "▾" : "▸"} CARS {visible}/{drivers.length}
      </button>
      {open && (
        <div
          style={{
            marginTop: 6,
            padding: 8,
            background: C.raised,
            border: `1px solid ${C.border}`,
            borderRadius: 4,
            display: "flex",
            flexWrap: "wrap",
            gap: 6,
            maxHeight: 180,
            overflow: "auto",
            boxShadow: "0 8px 24px rgba(0,0,0,0.45)",
          }}
        >
          {drivers.map((d) => {
            const off = hidden.includes(d.driver_code);
            return (
              <button
                key={d.driver_code}
                onClick={() => onToggle(d.driver_code)}
                title={d.full_name}
                style={{
                  display: "inline-flex",
                  gap: 4,
                  alignItems: "center",
                  fontFamily: T.mono,
                  fontSize: 9,
                  color: off ? C.faint : C.paper,
                  cursor: "pointer",
                  background: off ? "transparent" : C.panel2,
                  border: `1px solid ${off ? C.border : d.team_colour || C.border}`,
                  padding: "3px 6px",
                  borderRadius: 3,
                  opacity: off ? 0.45 : 1,
                }}
              >
                <span
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: "50%",
                    background: d.team_colour || C.mist,
                  }}
                />
                {d.driver_code}
              </button>
            );
          })}
          <button
            onClick={() =>
              onSetHidden?.(hidden.length === drivers.length ? [] : drivers.map((d) => d.driver_code))
            }
            style={{
              background: "none",
              border: `1px dashed ${C.border}`,
              color: C.faint,
              fontFamily: T.mono,
              fontSize: 8,
              cursor: "pointer",
              padding: "3px 6px",
            }}
          >
            {hidden.length === drivers.length ? "SHOW ALL" : "HIDE ALL"}
          </button>
        </div>
      )}
    </div>
  );
}
