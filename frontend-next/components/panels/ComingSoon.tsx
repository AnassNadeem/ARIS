export function ComingSoon({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 bg-carbon p-6 text-center font-mono-data text-[11px] text-muted">
      <div className="w-full max-w-xs border-t border-border pt-3">
        <span className="rounded-[4px] bg-surface px-2 py-1 text-amber">[COMING SOON]</span>{" "}
        <span className="text-white">{title}</span>
      </div>
      <p className="max-w-xs leading-relaxed">{description}</p>
      <div className="w-full max-w-xs border-b border-border pb-3" />
      <p className="text-[10px] text-muted-2">Available in a future update.</p>
    </div>
  );
}
