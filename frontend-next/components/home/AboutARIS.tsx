import Link from "next/link";

const METRICS: { label: string; value: string; warn?: boolean }[] = [
  { label: "Dry match-rate", value: "0.345  (30/87)" },
  { label: "vs never-pit", value: "+0.069 (+25%)" },
  { label: "Lights-out delta", value: "−1.73  (all 48 races)" },
  { label: "Tyre model", value: "G1.5 locked" },
  { label: "Wet heuristic", value: "⚠ uncalibrated", warn: true },
];

export function AboutARIS() {
  return (
    <section className="border-t border-border px-6 py-24">
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-16 sm:grid-cols-2">
        <div>
          <h2 className="mb-4 font-mono-data text-xs uppercase tracking-[0.15em] text-muted">
            About ARIS
          </h2>
          <p className="text-[15px] leading-relaxed text-white/90">
            ARIS is classical decision support stitched with modern ML — not
            end-to-end black-box AI. Every strategy call comes from an
            enumerated shortlist of physics-scored actions (stay out, pit now,
            pit on a target lap) ranked by simulated remaining-race delta, not
            a learned policy making the final call. A conservative Q-learning
            variant was tested as opt-in research and did not clear the gate
            to become the default ranker — physics stays in charge. The
            numbers on this page are pulled straight from the evidence trail,
            including where the model is honestly still weak (wet strategy,
            absolute lap-time calibration).
          </p>
          <div className="mt-8 flex flex-wrap gap-4 font-mono-data text-sm">
            <Link href="/replay" className="text-white underline-offset-4 hover:underline">
              [ Replay ]
            </Link>
            <Link href="/live" className="text-white underline-offset-4 hover:underline">
              [ Live ]
            </Link>
            <a
              href="https://github.com/AnassNadeem/ARIS"
              target="_blank"
              rel="noreferrer"
              className="text-white underline-offset-4 hover:underline"
            >
              [ GitHub → ]
            </a>
          </div>
        </div>

        <div className="font-mono-data text-sm">
          <table className="w-full border-collapse">
            <tbody>
              {METRICS.map((m) => (
                <tr key={m.label}>
                  <td className="py-2 pr-6 text-muted">{m.label}</td>
                  <td className={`py-2 text-right ${m.warn ? "text-amber" : "text-amber"}`}>
                    {m.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
