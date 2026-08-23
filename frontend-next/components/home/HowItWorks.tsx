const COLUMNS = [
  {
    num: "01",
    title: "INGEST",
    body: "FastF1 historical telemetry and OpenF1 live timing, ingested lap by lap into a race state snapshot.",
    icon: (
      <svg viewBox="0 0 48 48" className="h-10 w-10" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M2 24h6l4-14 6 28 5-20 4 12 4-6h11" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    num: "02",
    title: "RECOMMEND",
    body: "A search-based strategy engine evaluates pit timing, compound choice, and pace targets. Not a black box — every call has a number behind it.",
    icon: (
      <svg viewBox="0 0 48 48" className="h-10 w-10" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="24" cy="8" r="3" />
        <path d="M24 11v8M24 19l-12 8M24 19l12 8" strokeLinecap="round" />
        <circle cx="12" cy="31" r="3" />
        <circle cx="36" cy="31" r="3" />
        <path d="M12 34v6M36 34v6" strokeLinecap="round" />
        <circle cx="12" cy="43" r="2.5" />
        <circle cx="36" cy="43" r="2.5" />
      </svg>
    ),
  },
  {
    num: "03",
    title: "GHOST",
    body: "When ARIS's call differs from what the driver actually did, a ghost car runs the ARIS strategy on the same live grid. You watch who was right.",
    icon: (
      <svg viewBox="0 0 48 48" className="h-10 w-10" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M4 24h20" strokeLinecap="round" />
        <path d="M18 16l6 8-6 8" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M24 24h20" strokeDasharray="3 3" strokeLinecap="round" />
        <path d="M38 18l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
];

export function HowItWorks() {
  return (
    <section className="border-t border-border px-6 py-24">
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-12 sm:grid-cols-3">
        {COLUMNS.map((col) => (
          <div key={col.num} className="flex flex-col gap-4">
            <div className="text-red">{col.icon}</div>
            <h3 className="font-mono-data text-sm uppercase tracking-[0.1em] text-white">
              {col.num} / {col.title}
            </h3>
            <p className="text-[15px] leading-relaxed text-muted">{col.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
