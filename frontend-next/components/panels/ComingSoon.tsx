export function ComingSoon({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 bg-carbon p-4 text-center">
      <div className="w-full max-w-xs border-t border-border pt-4">
        <span className="rounded bg-surface px-2 py-1 font-sans text-[10px] uppercase text-amber">Coming soon</span>{" "}
        <span className="font-sans text-sm text-white">{title}</span>
      </div>
      <p className="max-w-xs font-sans text-xs leading-relaxed text-muted">{description}</p>
      <div className="w-full max-w-xs border-b border-border pb-4" />
      <p className="font-sans text-[10px] text-muted-2">Available in a future update.</p>
    </div>
  );
}
